"""统计接口（M3，DR-020）：主题/会议趋势时间序列。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.stats import TrendResponse
from app.services import stats_service

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/trends", response_model=TrendResponse)
def trends(
    group_by: str = Query("topic", pattern="^(topic|venue|year)$", description="分组维度"),
    start: str | None = Query(None, description="起始日期 YYYY-MM-DD（默认数据最早日）"),
    end: str | None = Query(None, description="结束日期 YYYY-MM-DD（默认数据最晚日）"),
    db: Session = Depends(get_db),
) -> dict:
    return stats_service.trends(db, group_by, start, end)
