"""统计接口（M3+M7，DR-020）：趋势时间序列 + 词云/作者榜/热力图/合作网络。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.stats import (
    AuthorPage,
    InstitutionDetailResponse,
    InstitutionPage,
    TrendResponse,
)
from app.services import institution_service, stats_service

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


@router.get("/authors", response_model=AuthorPage)
def authors_top(
    page: int = Query(1, ge=1, description="页码（从 1 起）"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    q: str | None = Query(None, description="按作者名模糊搜索（不区分大小写）"),
    db: Session = Depends(get_db),
) -> dict:
    items, total = stats_service.authors_top(db, page, page_size, q)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/institutions", response_model=InstitutionPage)
def institutions_top(
    page: int = Query(1, ge=1, description="页码（从 1 起）"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    q: str | None = Query(None, description="按机构名模糊搜索（不区分大小写）"),
    db: Session = Depends(get_db),
) -> dict:
    items, total = stats_service.institutions_top(db, page, page_size, q)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/institution", response_model=InstitutionDetailResponse)
def institution_detail(
    name: str = Query(..., min_length=1, description="机构名（归一化后的完整机构串）"),
    db: Session = Depends(get_db),
) -> dict:
    """机构详情（M12）：统计 + 主题分布 + 合作机构。未知名返回零值（不 404）。"""
    return institution_service.institution_detail(db, name)


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
