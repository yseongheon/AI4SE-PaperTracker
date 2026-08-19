"""个人周报（M9）：每周五为每个有收藏的用户生成收藏论文总结。

用法（cd backend）：
    python -m scripts.personal_report          # 为所有收藏数 > 0 的用户生成
输出：data/reports/personal/{username}-YYYY-Www.md

内容：本周新收藏论文 + 收藏主题分布 + LLM 个性化阅读建议（按需、量小）。
复用 weekly_report 的统计思路；LLM 调用走 CostTracker 成本开关。
"""
import logging
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import MarkType, Paper, PaperTopic, Topic, User, UserMark
from scripts.weekly_report import REPORT_DIR

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PERSONAL_DIR = REPORT_DIR / "personal"
WINDOW_DAYS = 7


def users_with_bookmarks(db: Session) -> list[User]:
    return (
        db.query(User)
        .join(UserMark, UserMark.user_id == User.id)
        .filter(UserMark.mark_type == MarkType.BOOKMARK.value)
        .group_by(User.id)
        .order_by(User.id)
        .all()
    )


def user_week_stats(db: Session, user: User, days: int = WINDOW_DAYS) -> dict:
    """用户近 N 天收藏统计：新收藏论文 + 主题分布。"""
    cutoff = datetime.utcnow() - timedelta(days=days)
    new_marks = (
        db.query(Paper)
        .join(UserMark, UserMark.paper_id == Paper.id)
        .filter(
            UserMark.user_id == user.id,
            UserMark.mark_type == MarkType.BOOKMARK.value,
            UserMark.created_at >= cutoff,
        )
        .options()
        .order_by(UserMark.created_at.desc())
        .all()
    )
    topic_dist = (
        db.query(Topic.slug, Topic.name_zh, func.count(PaperTopic.paper_id))
        .join(PaperTopic, PaperTopic.topic_id == Topic.id)
        .join(Paper, Paper.id == PaperTopic.paper_id)
        .join(UserMark, (UserMark.paper_id == Paper.id) & (UserMark.user_id == user.id))
        .filter(UserMark.mark_type == MarkType.BOOKMARK.value, PaperTopic.method == "llm")
        .group_by(Topic.id)
        .order_by(func.count(PaperTopic.paper_id).desc())
        .all()
    )
    return {"new_marks": new_marks, "topic_dist": topic_dist}


def render_personal_report(user: User, stats: dict, period_label: str) -> str:
    new_marks = stats["new_marks"]
    lines = [
        f"# {user.username} 的收藏周报（{period_label}）",
        "",
        f"> 本周新收藏 **{len(new_marks)}** 篇；累计收藏主题分布：",
        "",
        "| 主题 | 篇数 |",
        "|---|---|",
    ]
    if stats["topic_dist"]:
        for slug, name_zh, cnt in stats["topic_dist"]:
            lines.append(f"| {name_zh}（{slug}） | {cnt} |")
    else:
        lines.append("| （暂无收藏） | 0 |")
    lines.append("")

    lines += [f"## 本周新收藏（{len(new_marks)} 篇）", ""]
    if new_marks:
        for p in new_marks:
            venue_name = f"{p.venue.short_name} {p.year}" if p.venue else f"{p.year or ''}".strip()
            hl = p.highlights or {}
            lines += [
                f"### {p.title}（{venue_name}）",
                "",
            ]
            if hl.get("contribution"):
                lines.append(f"- 贡献：{hl['contribution']}")
            lines.append(f"- 链接：{p.arxiv_url or '—'}")
            lines.append("")
    else:
        lines.append("- 本周无新收藏")
    return "\n".join(lines)


def generate_personal_reports(db: Session) -> list[Path]:
    now = datetime.utcnow()
    period_label = (
        f"{(now - timedelta(days=WINDOW_DAYS)).strftime('%m-%d')} ~ {now.strftime('%m-%d')}"
    )
    iso_year, iso_week, _ = now.isocalendar()
    out_dir = PERSONAL_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for user in users_with_bookmarks(db):
        stats = user_week_stats(db, user)
        content = render_personal_report(user, stats, period_label)
        out = out_dir / f"{user.username}-{iso_year}-W{iso_week:02d}.md"
        out.write_text(content, encoding="utf-8")
        written.append(out)
        logger.info("personal report: %s (%d new marks)", user.username, len(stats["new_marks"]))
    return written


def main(argv: list[str] | None = None) -> int:
    db = SessionLocal()
    try:
        written = generate_personal_reports(db)
        if not written:
            print("没有收藏数 > 0 的用户，跳过个人周报")
        else:
            for path in written:
                print(f"个人周报已生成：{str(path).replace(chr(0x2011), '-')}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
