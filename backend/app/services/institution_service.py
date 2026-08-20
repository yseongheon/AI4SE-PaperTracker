"""机构服务（M12 机构功能）：别名合并加载 + 机构详情聚合。

别名库是数据驱动（institution_aliases 表），写库时套用 canonical（见
pipeline/_replace_authors 与各回填脚本）；详情聚合供 /api/stats/institution 用。
"""
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.models import InstitutionAlias, Paper, PaperAuthor, PaperTopic, Topic
from app.services.stats_service import _is_plausible_institution

_ALIAS_CHAIN_DEPTH = 10  # 链式映射解析深度上限（alias→canonical→canonical2）


def load_institution_alias_map(db: Session) -> dict[str, str]:
    """加载启用的机构别名映射 {alias: canonical}，链式映射解析到终值。"""
    rows = db.query(InstitutionAlias).filter(InstitutionAlias.is_active.is_(True)).all()
    raw = {r.alias: r.canonical for r in rows}
    resolved: dict[str, str] = {}
    for alias, canonical in raw.items():
        cur = canonical
        depth = 0
        while cur in raw and depth < _ALIAS_CHAIN_DEPTH:
            cur = raw[cur]
            depth += 1
        resolved[alias] = cur
    return resolved


def institution_detail(db: Session, name: str, co_limit: int = 10) -> dict:
    """机构详情聚合：论文数/AI4SE 数/主题分布/合作机构（计数一律 COUNT DISTINCT）。

    未知名（作者卡片可能点到垃圾机构如 "peter"）返回零值 200，不 404。
    """
    paper_count, ai4se_count = (
        db.query(
            func.count(func.distinct(Paper.id)),
            func.count(
                func.distinct(case((Paper.is_ai4se_confirmed.is_(True), Paper.id), else_=None))
            ),
        )
        .join(PaperAuthor, PaperAuthor.paper_id == Paper.id)
        .filter(PaperAuthor.affiliation == name)
        .one()
    )

    # 主题分布：按机构论文的 LLM/关键词标签聚合（DISTINCT 论文计数）
    topic_rows = (
        db.query(Topic.slug, Topic.name_zh, func.count(func.distinct(PaperTopic.paper_id)))
        .select_from(PaperAuthor)  # FROM paper_authors 起，再 join，避免 topics 重复
        .join(PaperTopic, PaperTopic.paper_id == PaperAuthor.paper_id)
        .join(Topic, Topic.id == PaperTopic.topic_id)
        .filter(PaperAuthor.affiliation == name)
        .group_by(Topic.slug, Topic.name_zh)
        .order_by(func.count(func.distinct(PaperTopic.paper_id)).desc(), Topic.slug)
        .all()
    )
    topics = [
        {"slug": slug, "name_zh": name_zh, "count": int(cnt)} for slug, name_zh, cnt in topic_rows
    ]

    # 合作机构：本机构论文上出现的其它机构（同论文多作者同机构只算 1 篇）
    paper_ids = db.query(func.distinct(PaperAuthor.paper_id)).filter(PaperAuthor.affiliation == name)
    co_rows = (
        db.query(PaperAuthor.affiliation, func.count(func.distinct(PaperAuthor.paper_id)))
        .filter(
            PaperAuthor.paper_id.in_(paper_ids),
            PaperAuthor.affiliation.isnot(None),
            PaperAuthor.affiliation != name,
        )
        .group_by(PaperAuthor.affiliation)
        .order_by(func.count(func.distinct(PaperAuthor.paper_id)).desc())
        .all()
    )
    co_institutions = [
        {"name": aff, "count": int(cnt)}
        for aff, cnt in co_rows
        if _is_plausible_institution(aff)
    ][:co_limit]

    return {
        "name": name,
        "paper_count": int(paper_count or 0),
        "ai4se_count": int(ai4se_count or 0),
        "topics": topics,
        "co_institutions": co_institutions,
    }
