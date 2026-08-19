"""论文查询服务（M3+M6）：列表过滤/排序/分页、详情、个性化标记、相关推荐。

设计（方案 A，DR-019 授权）：api 路由薄、查询逻辑集中在 service；
topic 过滤用 EXISTS 子查询而非 JOIN，避免多标签论文被重复计数且保持排序简单。
M6：marks 用一次批量查询取当前页标记（避免 N+1）；related 同主题池 + 标题 Jaccard 排序。
"""
import re
from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.models import MarkType, Paper, PaperAuthor, PaperTopic, Topic, UserMark, Venue
from app.schemas.paper import Highlights, PaperDetail, PaperListItem, PaperMarks

# 列表/详情共用 eager load，避免 N+1（作者、主题、会议）
_LIST_OPTIONS = (
    selectinload(Paper.author_links).selectinload(PaperAuthor.author),
    selectinload(Paper.topic_links).selectinload(PaperTopic.topic),
    selectinload(Paper.venue),
)


def dblp_url(dblp_key: str | None) -> str | None:
    """DBLP 收录页 URL（双链接之一）；无匹配返回 None。"""
    return f"https://dblp.org/rec/{dblp_key}.html" if dblp_key else None


def _marks_map(db: Session, paper_ids: list[int]) -> dict[int, PaperMarks]:
    """一次查询批量取标记（避免逐篇 N+1）。"""
    marks: dict[int, PaperMarks] = defaultdict(PaperMarks)
    if not paper_ids:
        return {}
    for m in db.query(UserMark).filter(UserMark.paper_id.in_(paper_ids)):
        setattr(marks[m.paper_id], m.mark_type, True)
    return dict(marks)


def _to_item(paper: Paper, marks: PaperMarks | None = None) -> PaperListItem:
    return PaperListItem(
        id=paper.id,
        title=paper.title,
        authors=[link.author.name for link in paper.author_links],
        venue=paper.venue,
        topics=[link.topic for link in paper.topic_links],
        year=paper.year,
        published_at=paper.published_at.date() if paper.published_at else None,
        is_ai4se_confirmed=paper.is_ai4se_confirmed,
        arxiv_url=paper.arxiv_url,
        dblp_url=dblp_url(paper.dblp_key),
        doi=paper.doi,
        marks=marks or PaperMarks(),
    )


def _apply_marks_filter(query, db: Session, marks: str | None):
    """个性化标记过滤（M6）：bookmark/read_later 有标记；unread 无 read 标记。"""
    if not marks:
        return query
    if marks == "unread":
        return query.filter(
            ~db.query(UserMark)
            .filter(UserMark.paper_id == Paper.id, UserMark.mark_type == MarkType.READ.value)
            .exists()
        )
    return query.filter(
        db.query(UserMark)
        .filter(UserMark.paper_id == Paper.id, UserMark.mark_type == marks)
        .exists()
    )


def build_papers_query(
    db: Session,
    q: str | None = None,
    topic: str | None = None,
    venue: str | None = None,
    year: int | None = None,
    is_ai4se: bool | None = None,
    marks: str | None = None,
):
    """公共过滤构建器（M6）：列表与导出共用同一套过滤条件。"""
    query = db.query(Paper)

    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(Paper.title.ilike(like), Paper.abstract.ilike(like))
        )
    if topic:
        # EXISTS 子查询：多标签论文不产生重复行，total 计数与排序天然正确
        query = query.filter(
            db.query(PaperTopic)
            .join(Topic, Topic.id == PaperTopic.topic_id)
            .filter(PaperTopic.paper_id == Paper.id, Topic.slug == topic)
            .exists()
        )
    if venue:
        query = query.join(Venue, Venue.id == Paper.venue_id).filter(
            Venue.short_name == venue
        )
    if year:
        query = query.filter(Paper.year == year)
    if is_ai4se is not None:
        query = query.filter(Paper.is_ai4se_confirmed.is_(is_ai4se))
    return _apply_marks_filter(query, db, marks)


def items_from_query(db: Session, query) -> list[PaperListItem]:
    """执行查询并组装列表项（含批量 marks 标记，避免 N+1）。导出与列表共用。"""
    papers = query.options(*_LIST_OPTIONS).all()
    marks_map = _marks_map(db, [p.id for p in papers])
    return [_to_item(p, marks_map.get(p.id)) for p in papers]


def list_papers(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    q: str | None = None,
    topic: str | None = None,
    venue: str | None = None,
    year: int | None = None,
    is_ai4se: bool | None = None,
    marks: str | None = None,
    sort: str = "newest",
) -> tuple[list[PaperListItem], int]:
    """论文列表：过滤 + 排序 + 分页，返回 (items, total)。"""
    query = build_papers_query(db, q, topic, venue, year, is_ai4se, marks)

    if sort == "venue":
        # A 会正式版优先（venue 非空），再按年份倒序
        query = query.order_by(
            Paper.venue_id.is_(None), Paper.year.desc().nullslast(), Paper.id.desc()
        )
    else:  # newest
        query = query.order_by(
            Paper.published_at.desc().nullslast(), Paper.id.desc()
        )

    total = query.count()
    items = items_from_query(db, query.offset((page - 1) * page_size).limit(page_size))
    return items, total


def get_paper(db: Session, paper_id: int) -> PaperDetail:
    paper = db.get(Paper, paper_id, options=_LIST_OPTIONS)
    if paper is None:
        raise HTTPException(status_code=404, detail=f"paper {paper_id} not found")
    marks_map = _marks_map(db, [paper_id])
    item = _to_item(paper, marks_map.get(paper_id))
    return PaperDetail(
        **item.model_dump(),
        abstract=paper.abstract,
        summary_zh=paper.summary_zh,
        highlights=(
            Highlights(**paper.highlights) if isinstance(paper.highlights, dict) else None
        ),
        is_ai4se_candidate=paper.is_ai4se_candidate,
        match_status=paper.match_status,
        status=paper.status,
        related=related_papers(db, paper),
    )


# ---- M6：个性化标记 ----

def set_mark(db: Session, paper_id: int, mark_type: str, value: bool) -> PaperMarks:
    """设置/取消标记（幂等）：value=True 插入、False 删除。"""
    paper = db.get(Paper, paper_id)
    if paper is None:
        raise HTTPException(status_code=404, detail=f"paper {paper_id} not found")
    existing = db.query(UserMark).filter_by(paper_id=paper_id, mark_type=mark_type).first()
    if value and existing is None:
        db.add(UserMark(paper_id=paper_id, mark_type=mark_type))
    elif not value and existing is not None:
        db.delete(existing)
    db.commit()
    # 全部标记被取消时 _marks_map 无该论文 key，用 get 兜底
    return _marks_map(db, [paper_id]).get(paper_id, PaperMarks())


# ---- M6：相关论文推荐 ----

def _title_tokens(title: str) -> set[str]:
    """标题小写 token 集（Jaccard 相似度用）。"""
    return set(re.findall(r"[a-z0-9]+", (title or "").lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def related_papers(db: Session, paper: Paper, limit: int = 5) -> list[PaperListItem]:
    """相关论文推荐：同主题论文池 → 标题 token Jaccard 相似度排序 → Top N。

    无同主题时退回同 venue 池；再退回同 year 池（保底不空）。
    """
    def pool_query(base_ids: list[int]) -> list[Paper]:
        if not base_ids:
            return []
        return (
            db.query(Paper)
            .filter(Paper.id.in_(base_ids), Paper.id != paper.id)
            .options(*_LIST_OPTIONS)
            .all()
        )

    candidate_ids: set[int] = set()
    # 1) 同主题（共享 ≥1 个 topic_id）
    if paper.topic_links:
        topic_ids = [t.topic_id for t in paper.topic_links]
        rows = (
            db.query(PaperTopic.paper_id)
            .filter(PaperTopic.topic_id.in_(topic_ids), PaperTopic.paper_id != paper.id)
            .all()
        )
        candidate_ids.update(r[0] for r in rows)
    # 2) 同 venue
    if paper.venue_id and len(candidate_ids) < 20:
        rows = db.query(Paper.id).filter(Paper.venue_id == paper.venue_id, Paper.id != paper.id).all()
        candidate_ids.update(r[0] for r in rows)
    # 3) 同 year 保底
    if paper.year and len(candidate_ids) < 20:
        rows = db.query(Paper.id).filter(Paper.year == paper.year, Paper.id != paper.id).all()
        candidate_ids.update(r[0] for r in rows)

    pool = pool_query(sorted(candidate_ids))
    self_tokens = _title_tokens(paper.title)
    ranked = sorted(
        pool,
        key=lambda p: (
            _jaccard(self_tokens, _title_tokens(p.title)),
            p.published_at or p.created_at,
        ),
        reverse=True,
    )
    marks_map = _marks_map(db, [p.id for p in ranked[:limit]])
    return [_to_item(p, marks_map.get(p.id)) for p in ranked[:limit]]
