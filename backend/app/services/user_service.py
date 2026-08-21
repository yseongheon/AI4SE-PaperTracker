"""用户画像服务（M9）：个人统计 / 收藏主题分布 / 最近收藏 / 最近已读。"""
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import MarkType, Paper, PaperTopic, Topic, User, UserMark
from app.services.paper_service import _LIST_OPTIONS, _marks_map, _to_item


def _recent_marked(db: Session, user: User, mark_type: str, limit: int = 10) -> list:
    """某类标记的最近论文（按标记时间倒序），复用列表项组装（含 marks 集合）。"""
    papers = (
        db.query(Paper)
        .join(UserMark, UserMark.paper_id == Paper.id)
        .filter(UserMark.user_id == user.id, UserMark.mark_type == mark_type)
        .order_by(UserMark.created_at.desc())
        .options(*_LIST_OPTIONS)
        .limit(limit)
        .all()
    )
    marks_map = _marks_map(db, [p.id for p in papers], user.id)
    return [_to_item(p, marks_map.get(p.id)) for p in papers]


def profile(db: Session, user: User) -> dict:
    """个人画像：标记统计 + 收藏论文主题分布 + 最近收藏 / 最近已读列表。"""
    counts = {"bookmark": 0, "read": 0, "read_later": 0}
    for mark_type, cnt in (
        db.query(UserMark.mark_type, func.count(UserMark.paper_id))
        .filter(UserMark.user_id == user.id)
        .group_by(UserMark.mark_type)
        .all()
    ):
        counts[mark_type] = cnt

    # 收藏论文的主题分布（llm 标签）
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

    # 最近收藏 / 最近已读（按标记时间倒序取 10）
    return {
        "username": user.username,
        "email": user.email,
        "counts": counts,
        "topic_dist": [
            {"slug": s, "name_zh": n, "count": c} for s, n, c in topic_dist
        ],
        "recent": _recent_marked(db, user, MarkType.BOOKMARK.value),
        "recent_read": _recent_marked(db, user, MarkType.READ.value),
    }
