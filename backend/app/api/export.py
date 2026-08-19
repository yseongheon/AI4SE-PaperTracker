"""数据导出接口（M6）：CSV / JSON / BibTeX，复用列表同一套过滤条件。

带当前筛选条件导出（q/topic/venue/year/is_ai4se/marks），
全量导出（不过滤）即导整个库。
"""
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.services import export_service, paper_service

router = APIRouter(prefix="/export", tags=["export"])


@router.get("")
def export_papers(
    format: str = Query("csv", pattern="^(csv|json|bibtex)$", description="导出格式"),
    q: str | None = Query(None, description="标题/摘要关键词搜索"),
    topic: str | None = Query(None, description="主题 slug（如 code_repair）"),
    venue: str | None = Query(None, description="会议 short_name（如 ICSE）"),
    year: int | None = Query(None, ge=1990, le=2100, description="年份"),
    is_ai4se: bool | None = Query(None, description="是否已确认 AI4SE"),
    marks: str | None = Query(
        None, pattern="^(bookmark|read_later|unread)$", description="个性化标记过滤"
    ),
    db: Session = Depends(get_db),
) -> Response:
    query = paper_service.build_papers_query(db, q, topic, venue, year, is_ai4se, marks)
    items = paper_service.items_from_query(db, query)

    content, content_type, filename = export_service.export(format, items)
    return Response(
        content=content,
        media_type=content_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
