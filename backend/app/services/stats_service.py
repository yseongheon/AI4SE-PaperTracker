"""统计服务（M3+M7）：主题/会议计数、趋势时间序列（DR-020）、词云/作者榜/热力图/合作网络。

趋势设计（用户拍板）：后端按天返回原始计数，聚合粒度（周/月）由前端决定；
group_by=topic|venue 时横轴为连续日期（缺省日补 0），group_by=year 时为年份。
M7 分析端点全部基于本地数据计算（零外部 API 成本）。
"""
import re
from collections import Counter, defaultdict
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models import Author, Paper, PaperAuthor, PaperTopic, Topic, Venue


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


# ---- M7：分析增强（词云 / 作者榜 / 热力图 / 合作网络） ----

# 英文停用词（arXiv 摘要高频无意义词）+ 过滤规则：长度 <3、纯数字
_STOPWORDS = {
    "the", "a", "an", "of", "and", "or", "in", "on", "at", "to", "for", "with",
    "from", "by", "as", "is", "are", "was", "were", "be", "been", "being", "we",
    "our", "us", "their", "its", "this", "that", "these", "those", "it", "they",
    "he", "she", "them", "his", "her", "which", "who", "whom", "whose", "not",
    "no", "but", "however", "while", "although", "though", "can", "could", "may",
    "might", "must", "will", "would", "should", "shall", "than", "then", "there",
    "here", "where", "when", "why", "how", "what", "all", "both", "each", "few",
    "more", "most", "other", "some", "such", "only", "own", "same", "so", "too",
    "very", "just", "also", "often", "even", "well", "one", "two", "first",
    "second", "new", "use", "used", "using", "based", "using", "proposed",
    "propose", "approach", "paper", "results", "result", "show", "shows",
    "shown", "found", "find", "method", "methods", "system", "systems",
    "within", "between", "over", "under", "about", "via", "against", "across",
    "per", "etc", "e.g", "i.e", "et", "al", "doi", "http", "https", "ieee",
    "acm", "arxiv", "cs", "se", "software", "data", "study", "studies",
}
_WORD_RE = re.compile(r"[a-z]{3,}")


def words(db: Session, limit: int = 50, scope: str = "ai4se") -> dict:
    """词云高频词：摘要英文词频（停用词过滤），scope=ai4se 只看已确认论文。"""
    query = db.query(Paper.abstract)
    if scope == "ai4se":
        query = query.filter(Paper.is_ai4se_confirmed.is_(True))
    counter: Counter[str] = Counter()
    for (abstract,) in query.yield_per(500):
        if not abstract:
            continue
        for word in _WORD_RE.findall(abstract.lower()):
            if word not in _STOPWORDS:
                counter[word] += 1
    top = counter.most_common(limit)
    return {
        "scope": scope,
        "words": [{"word": w, "count": c} for w, c in top],
    }


# 单 token 机构白名单：arXiv 机构自由文本常只填缩写/公司名；白名单外的单 token 视为作者名误填
_SINGLE_TOKEN_INSTITUTIONS = {
    "ubc", "sri", "epfl", "rptu", "oracle", "pwc", "sonarsource", "accentrust",
    "novafabric", "irit-traces", "lre", "lsl", "epita", "microsoft", "google",
    "meta", "ibm", "amazon", "huawei", "eth", "mit", "deepmind", "openai", "ntua",
}


def _is_plausible_institution(aff: str | None) -> bool:
    """机构可信度过滤：排除明显非机构项（空、过短、'independent researcher'、单 token 作者名误填）。"""
    a = (aff or "").strip().lower()
    if len(a) < 3:
        return False
    if "independent researcher" in a:
        return False
    tokens = [t for t in a.split() if t]
    if len(tokens) == 1 and a not in _SINGLE_TOKEN_INSTITUTIONS:
        return False
    return True


def authors_top(db: Session, page: int = 1, page_size: int = 20,
                q: str | None = None) -> tuple[list[dict], int]:
    """作者榜：论文数 + AI4SE 论文数 + 主要主题 + 机构（按论文数降序）。

    M13 服务端分页：先 count 组数得 total，再按当前页 offset/limit；
    ai4se_count 用 DISTINCT 计数（与机构榜口径一致，避免同作者同篇重复计）。
    q：作者名模糊搜索（不区分大小写，匹配 name_normalized）。
    """
    paper_count = func.count(func.distinct(PaperAuthor.paper_id))
    ai4se_count = func.count(
        func.distinct(case((Paper.is_ai4se_confirmed.is_(True), Paper.id), else_=None))
    )
    base = (
        db.query(
            Author.id,
            Author.name,
            paper_count.label("paper_count"),
            ai4se_count.label("ai4se_count"),
        )
        .join(PaperAuthor, PaperAuthor.author_id == Author.id)
        .join(Paper, Paper.id == PaperAuthor.paper_id)
        .group_by(Author.id, Author.name)
    )
    if q:
        q = q.strip().lower()
        base = base.filter(Author.name_normalized.ilike(f"%{q}%"))
    total = base.count()
    rows = (
        base.order_by(paper_count.desc(), Author.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    author_ids = [r[0] for r in rows]
    # 一次查询取这批作者的论文主题分布（Python 分组，避免 N+1）
    topic_rows = (
        db.query(PaperAuthor.author_id, Topic.slug, Topic.name_zh, func.count(PaperTopic.paper_id))
        .join(PaperTopic, PaperTopic.paper_id == PaperAuthor.paper_id)
        .join(Topic, Topic.id == PaperTopic.topic_id)
        .filter(PaperAuthor.author_id.in_(author_ids))
        .group_by(PaperAuthor.author_id, Topic.slug, Topic.name_zh)
        .order_by(PaperAuthor.author_id, func.count(PaperTopic.paper_id).desc())
        .all()
    )
    by_author: dict[int, list[dict]] = defaultdict(list)
    for aid, slug, name_zh, cnt in topic_rows:
        by_author[aid].append({"slug": slug, "name_zh": name_zh, "count": cnt})
    # 机构：每作者取出现次数最多的非空 affiliation
    aff_rows = (
        db.query(PaperAuthor.author_id, PaperAuthor.affiliation, func.count(PaperAuthor.paper_id))
        .filter(PaperAuthor.author_id.in_(author_ids), PaperAuthor.affiliation.isnot(None))
        .group_by(PaperAuthor.author_id, PaperAuthor.affiliation)
        .all()
    )
    per_author_aff: dict[int, Counter[str]] = defaultdict(Counter)
    for aid, aff, cnt in aff_rows:
        per_author_aff[aid][aff] = cnt

    def top_plausible_aff(counter: Counter[str]) -> str | None:
        """取出现最多的可信机构（arXiv 机构自由文本含作者名误填，先过滤）。"""
        plausible = {k: v for k, v in counter.items() if _is_plausible_institution(k)}
        if not plausible:
            return None
        return max(plausible, key=plausible.get)

    items = [
        {
            "id": aid,
            "name": name,
            "paper_count": cnt,
            "ai4se_count": int(ai4se or 0),
            "top_topics": by_author.get(aid, [])[:3],
            "affiliation": top_plausible_aff(per_author_aff[aid]),
        }
        for aid, name, cnt, ai4se in rows
    ]
    return items, total


def institutions_top(db: Session, page: int = 1, page_size: int = 20,
                     q: str | None = None) -> tuple[list[dict], int]:
    """机构榜：论文数（去重）+ AI4SE 论文数 + 主要主题（按论文数降序）。

    M13 服务端分页：主查询全量取组（机构数极少），Python 层过滤垃圾项后切片；
    计数一律 COUNT(DISTINCT)：同一论文有多个同机构作者时只能算 1 篇。
    q：机构名模糊搜索（不区分大小写，匹配 affiliation）。
    """
    paper_count = func.count(func.distinct(Paper.id))
    ai4se_count = func.count(
        func.distinct(case((Paper.is_ai4se_confirmed.is_(True), Paper.id), else_=None))
    )
    query = (
        db.query(
            PaperAuthor.affiliation.label("name"),
            paper_count.label("paper_count"),
            ai4se_count.label("ai4se_count"),
        )
        .join(Paper, Paper.id == PaperAuthor.paper_id)
        .filter(PaperAuthor.affiliation.isnot(None))
    )
    if q:
        q = q.strip().lower()
        query = query.filter(PaperAuthor.affiliation.ilike(f"%{q}%"))
    rows = (
        query.group_by(PaperAuthor.affiliation)
        .order_by(paper_count.desc(), PaperAuthor.affiliation)
        .all()
    )
    # 过滤明显非机构项（作者名误填等）后再切片分页（total 为过滤后的可信机构数）
    plausible = [r for r in rows if _is_plausible_institution(r.name)]
    total = len(plausible)
    filtered = plausible[(page - 1) * page_size : page * page_size]
    names = [r.name for r in filtered]
    # 主要主题：按机构分组，count(distinct paper_id)（镜像 authors_top 第二查询）
    topic_rows = (
        db.query(
            PaperAuthor.affiliation,
            Topic.slug,
            Topic.name_zh,
            func.count(func.distinct(PaperTopic.paper_id)),
        )
        .join(PaperTopic, PaperTopic.paper_id == PaperAuthor.paper_id)
        .join(Topic, Topic.id == PaperTopic.topic_id)
        .filter(PaperAuthor.affiliation.in_(names))
        .group_by(PaperAuthor.affiliation, Topic.slug, Topic.name_zh)
        .order_by(
            PaperAuthor.affiliation,
            func.count(func.distinct(PaperTopic.paper_id)).desc(),
        )
        .all()
    )
    by_inst: dict[str, list[dict]] = defaultdict(list)
    for aff, slug, name_zh, cnt in topic_rows:
        by_inst[aff].append({"slug": slug, "name_zh": name_zh, "count": cnt})
    items = [
        {
            "name": r.name,
            "paper_count": r.paper_count,
            "ai4se_count": int(r.ai4se_count or 0),
            "top_topics": by_inst.get(r.name, [])[:3],
        }
        for r in filtered
    ]
    return items, total


def cross(db: Session) -> dict:
    """会议×主题交叉矩阵（热力图）：venues 行 × topics 列。"""
    rows = (
        db.query(Venue.short_name, Topic.slug, func.count(Paper.id))
        .join(Paper, Paper.venue_id == Venue.id)
        .join(PaperTopic, PaperTopic.paper_id == Paper.id)
        .join(Topic, Topic.id == PaperTopic.topic_id)
        .group_by(Venue.short_name, Topic.slug)
        .all()
    )
    venues = sorted({r[0] for r in rows})
    topics = sorted({r[1] for r in rows})
    matrix = [[0] * len(topics) for _ in venues]
    for v, t, cnt in rows:
        matrix[venues.index(v)][topics.index(t)] = cnt
    return {"venues": venues, "topics": topics, "matrix": matrix}


def coauthor(db: Session, limit: int = 100) -> dict:
    """作者合作网络：TOP N 活跃作者共著边（weight=共著论文数）。"""
    # TOP N 活跃作者（按论文数）
    top = (
        db.query(Author.id, Author.name, func.count(func.distinct(PaperAuthor.paper_id)).label("c"))
        .join(PaperAuthor, PaperAuthor.author_id == Author.id)
        .group_by(Author.id, Author.name)
        .order_by(func.count(func.distinct(PaperAuthor.paper_id)).desc(), Author.id)
        .limit(limit)
        .all()
    )
    nodes = [{"id": aid, "name": name, "paper_count": c} for aid, name, c in top]
    ids = [aid for aid, _, _ in top]
    if not ids:
        return {"nodes": [], "links": []}

    # 每作者的论文 id 集
    rows = (
        db.query(PaperAuthor.author_id, PaperAuthor.paper_id)
        .filter(PaperAuthor.author_id.in_(ids))
        .all()
    )
    papers_of: dict[int, set[int]] = defaultdict(set)
    for aid, pid in rows:
        papers_of[aid].add(pid)
    # 两两交集 → 共著权重（只保留有共著的边）
    links = []
    for i, aid in enumerate(ids):
        for bid in ids[i + 1:]:
            w = len(papers_of[aid] & papers_of[bid])
            if w:
                links.append({"source": aid, "target": bid, "weight": w})
    links.sort(key=lambda e: e["weight"], reverse=True)
    return {"nodes": nodes, "links": links}
