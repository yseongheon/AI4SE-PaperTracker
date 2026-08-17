"""主题接口（M3）：列表 + 计数，供前端筛选侧栏。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.topic import TopicWithCount
from app.services import stats_service

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("", response_model=list[TopicWithCount])
def list_topics(db: Session = Depends(get_db)) -> list[dict]:
    return stats_service.topic_counts(db)
