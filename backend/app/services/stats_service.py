"""统计服务（M3）：主题/会议计数、趋势时间序列（DR-020）。

趋势设计（用户拍板）：后端按天返回原始计数，聚合粒度（周/月）由前端决定；
group_by=topic|venue 时横轴为连续日期（缺省日补 0），group_by=year 时为年份。
"""
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Paper, PaperTopic, Topic, Venue


def topic_counts(db: Session) -> list[dict]:
    """主题列表（含该主题标签的论文数），按论文数降序。"""
    rows = (
        db.query(
            Topic.id, Topic.slug, Topic.name_zh, Topic.description,
            func.count(PaperTopic.paper_id),
        )
        .outerjoin(PaperTopic, PaperTopic.topic_id == Topic.id)
        .filter(Topic.is_active.is_(True))
        .group_by(Topic.id)
        .order_by(func.count(PaperTopic.paper_id).desc(), Topic.id)
        .all()
    )
    return [
        {"id": r[0], "slug": r[1], "name_zh": r[2], "description": r[3], "paper_count": r[4]}
        for r in rows
    ]


def venue_counts(db: Session) -> list[dict]:
    """A 会列表（含已匹配论文数），按论文数降序。"""
    rows = (
        db.query(
            Venue.id, Venue.short_name, Venue.full_name, Venue.rank,
            func.count(Paper.id),
        )
        .outerjoin(Paper, Paper.venue_id == Venue.id)
        .filter(Venue.is_active.is_(True))
        .group_by(Venue.id)
        .order_by(func.count(Paper.id).desc(), Venue.id)
        .all()
    )
    return [
        {"id": r[0], "short_name": r[1], "full_name": r[2], "rank": r[3], "paper_count": r[4]}
        for r in rows
    ]


def _parse_date(value: str | None, field: str) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"invalid {field}: {value} (expected YYYY-MM-DD)")


def _date_range(start: date, end: date) -> list[str]:
    days, d = [], start
    while d <= end:
        days.append(d.isoformat())
        d += timedelta(days=1)
    return days


def _bounds(db: Session) -> tuple[date, date]:
    """published_at 最小/最大日期；空库回退今天。"""
    lo, hi = db.query(
        func.min(func.date(Paper.published_at)),
        func.max(func.date(Paper.published_at)),
    ).first()
    today = date.today()
    return date.fromisoformat(lo) if lo else today, date.fromisoformat(hi) if hi else today


def trends(
    db: Session,
    group_by: str = "topic",
    start: str | None = None,
    end: str | None = None,
) -> dict:
    """趋势时间序列：labels（按天/年）+ series（多条线，缺省日补 0）。"""
    if group_by not in ("topic", "venue", "year"):
        raise HTTPException(status_code=400, detail=f"invalid group_by: {group_by} (topic|venue|year)")

    if group_by == "year":
        rows = (
            db.query(Paper.year, func.count(Paper.id))
            .filter(Paper.year.isnot(None))
            .group_by(Paper.year)
            .order_by(Paper.year)
            .all()
        )
        return {
            "group_by": "year",
            "start": None,
            "end": None,
            "labels": [str(y) for y, _ in rows],
            "series": [{"key": "all", "name": "全部论文", "values": [c for _, c in rows]}],
        }

    start_d = _parse_date(start, "start")
    end_d = _parse_date(end, "end")
    lo, hi = _bounds(db)
    start_d = start_d or lo
    end_d = end_d or hi
    if start_d > end_d:
        raise HTTPException(status_code=400, detail="start must be <= end")
    start_s, end_s = start_d.isoformat(), end_d.isoformat()

    day = func.date(Paper.published_at)
    if group_by == "topic":
        label, name = Topic.slug, Topic.name_zh
        rows = (
            db.query(day.label("day"), Topic.slug, Topic.name_zh, func.count(Paper.id))
            .join(PaperTopic, PaperTopic.paper_id == Paper.id)
            .join(Topic, Topic.id == PaperTopic.topic_id)
            .filter(Paper.published_at.isnot(None), day >= start_s, day <= end_s)
            .group_by(day, Topic.slug, Topic.name_zh)
            .all()
        )
    else:  # venue
        label, name = Venue.short_name, Venue.full_name
        rows = (
            db.query(day.label("day"), Venue.short_name, Venue.full_name, func.count(Paper.id))
            .join(Venue, Venue.id == Paper.venue_id)
            .filter(Paper.published_at.isnot(None), day >= start_s, day <= end_s)
            .group_by(day, Venue.short_name, Venue.full_name)
            .all()
        )

    # 行 → {key: {day: count}}，再填成对齐的零填充序列
    per_key: dict[str, dict[str, int]] = {}
    names: dict[str, str] = {}
    for day_s, key, display, count in rows:
        per_key.setdefault(key, {})[day_s] = count
        names[key] = display
    labels = _date_range(start_d, end_d)
    series = [
        {"key": k, "name": names[k], "values": [per_key[k].get(d, 0) for d in labels]}
        for k in sorted(per_key)
    ]
    return {
        "group_by": group_by,
        "start": start_s,
        "end": end_s,
        "labels": labels,
        "series": series,
    }
