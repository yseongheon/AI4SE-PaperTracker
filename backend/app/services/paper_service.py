"""论文查询服务（M3）：列表过滤/排序/分页、详情。

设计（方案 A，DR-019 授权）：api 路由薄、查询逻辑集中在 service；
topic 过滤用 EXISTS 子查询而非 JOIN，避免多标签论文被重复计数且保持排序简单。
"""
from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from app.models import Paper, PaperAuthor, PaperTopic, Topic, Venue
from app.schemas.paper import PaperDetail, PaperListItem

# 列表/详情共用 eager load，避免 N+1（作者、主题、会议）
_LIST_OPTIONS = (
    selectinload(Paper.author_links).selectinload(PaperAuthor.author),
    selectinload(Paper.topic_links).selectinload(PaperTopic.topic),
    selectinload(Paper.venue),
)


def dblp_url(dblp_key: str | None) -> str | None:
    """DBLP 收录页 URL（双链接之一）；无匹配返回 None。"""
    return f"https://dblp.org/rec/{dblp_key}.html" if dblp_key else None


def _to_item(paper: Paper) -> PaperListItem:
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
    )


def list_papers(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    q: str | None = None,
    topic: str | None = None,
    venue: str | None = None,
    year: int | None = None,
    is_ai4se: bool | None = None,
    sort: str = "newest",
) -> tuple[list[PaperListItem], int]:
    """论文列表：过滤 + 排序 + 分页，返回 (items, total)。"""
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
    papers = (
        query.options(*_LIST_OPTIONS)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return [_to_item(p) for p in papers], total


def get_paper(db: Session, paper_id: int) -> PaperDetail:
    paper = db.get(Paper, paper_id, options=_LIST_OPTIONS)
    if paper is None:
        raise HTTPException(status_code=404, detail=f"paper {paper_id} not found")
    item = _to_item(paper)
    return PaperDetail(
        **item.model_dump(),
        abstract=paper.abstract,
        summary_zh=paper.summary_zh,
        is_ai4se_candidate=paper.is_ai4se_candidate,
        match_status=paper.match_status,
        status=paper.status,
    )
