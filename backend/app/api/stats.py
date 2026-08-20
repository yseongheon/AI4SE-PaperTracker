"""统计接口（M3+M7，DR-020）：趋势时间序列 + 词云/作者榜/热力图/合作网络。"""
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


@router.get("/words")
def words(
    limit: int = Query(50, ge=10, le=200, description="词云词数上限"),
    scope: str = Query("ai4se", pattern="^(all|ai4se)$", description="统计范围"),
    db: Session = Depends(get_db),
) -> dict:
    return stats_service.words(db, limit, scope)


@router.get("/authors")
def authors_top(
    limit: int = Query(50, ge=10, le=100, description="榜单人数上限"),
    db: Session = Depends(get_db),
) -> dict:
    return stats_service.authors_top(db, limit)


@router.get("/institutions")
def institutions_top(
    limit: int = Query(50, ge=10, le=100, description="榜单机构数上限"),
    db: Session = Depends(get_db),
) -> dict:
    return stats_service.institutions_top(db, limit)


@router.get("/cross")
def cross(db: Session = Depends(get_db)) -> dict:
    """会议×主题交叉矩阵（热力图）。"""
    return stats_service.cross(db)


@router.get("/coauthor")
def coauthor(
    limit: int = Query(100, ge=20, le=300, description="合作网络节点（活跃作者）上限"),
    db: Session = Depends(get_db),
) -> dict:
    return stats_service.coauthor(db, limit)
