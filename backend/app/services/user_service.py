"""用户画像服务（M9）：个人统计 / 收藏主题分布 / 最近收藏。"""
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app.models import MarkType, Paper, PaperAuthor, PaperTopic, Topic, User, UserMark
from app.services.paper_service import _LIST_OPTIONS, _marks_map, _to_item


def profile(db: Session, user: User) -> dict:
    """个人画像：标记统计 + 收藏论文主题分布 + 最近收藏列表。"""
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

    # 最近收藏（按收藏时间倒序取 10）
    recent = (
        db.query(Paper)
        .join(UserMark, UserMark.paper_id == Paper.id)
        .filter(UserMark.user_id == user.id, UserMark.mark_type == MarkType.BOOKMARK.value)
        .order_by(UserMark.created_at.desc())
        .options(*_LIST_OPTIONS)
        .limit(10)
        .all()
    )
    marks_map = _marks_map(db, [p.id for p in recent], user.id)
    return {
        "username": user.username,
        "email": user.email,
        "counts": counts,
        "topic_dist": [
            {"slug": s, "name_zh": n, "count": c} for s, n, c in topic_dist
        ],
        "recent": [_to_item(p, marks_map.get(p.id)) for p in recent],
    }
