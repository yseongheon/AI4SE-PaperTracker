"""论文列表/详情接口（M3）。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.paper import PaperDetail, PaperPage
from app.services import paper_service

router = APIRouter(prefix="/papers", tags=["papers"])


@router.get("", response_model=PaperPage)
def list_papers(
    page: int = Query(1, ge=1, description="页码（从 1 起）"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    q: str | None = Query(None, description="标题/摘要关键词搜索"),
    topic: str | None = Query(None, description="主题 slug（如 code_repair）"),
    venue: str | None = Query(None, description="会议 short_name（如 ICSE）"),
    year: int | None = Query(None, ge=1990, le=2100, description="年份"),
    is_ai4se: bool | None = Query(None, description="是否已确认 AI4SE"),
    sort: str = Query("newest", pattern="^(newest|venue)$", description="newest=按时间倒序；venue=会议版优先"),
    db: Session = Depends(get_db),
) -> PaperPage:
    items, total = paper_service.list_papers(
        db, page, page_size, q, topic, venue, year, is_ai4se, sort
    )
    return PaperPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/{paper_id}", response_model=PaperDetail)
def get_paper(paper_id: int, db: Session = Depends(get_db)) -> PaperDetail:
    return paper_service.get_paper(db, paper_id)
