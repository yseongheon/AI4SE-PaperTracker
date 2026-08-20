"""论文列表/详情/个性化标记/单篇 BibTeX/AI 深度摘要接口（M3 + M6 + M7 + M9）。"""
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.schemas.paper import MarkRequest, PaperDetail, PaperMarks, PaperPage
from app.services import auth_service, export_service, paper_service

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
    marks: str | None = Query(
        None, pattern="^(bookmark|read_later|unread)$",
        description="个性化标记过滤：bookmark 只看收藏 / read_later 只看稍后读 / unread 只看未读",
    ),
    author: str | None = Query(None, description="按作者姓名过滤（模糊匹配）"),
    institution: str | None = Query(None, description="按作者机构过滤（精确匹配，规则归一化）"),
    field: str = Query("any", pattern="^(any|title|abstract)$", description="q 搜索范围：any=标题+摘要 / title / abstract"),
    year_from: int | None = Query(None, ge=1990, le=2100, description="年份区间起"),
    year_to: int | None = Query(None, ge=1990, le=2100, description="年份区间止"),
    min_citations: int | None = Query(None, ge=0, description="M8 只看引用数 ≥ N 的论文"),
    sort: str = Query("newest", pattern="^(newest|venue|citations)$", description="newest=按时间倒序；venue=会议版优先；citations=按被引量"),
    db: Session = Depends(get_db),
    user: User | None = Depends(auth_service.get_optional_user),  # M9 标记按用户隔离
) -> PaperPage:
    items, total = paper_service.list_papers(
        db,
        page=page,
        page_size=page_size,
        q=q,
        topic=topic,
        venue=venue,
        year=year,
        is_ai4se=is_ai4se,
        marks=marks,
        sort=sort,
        author=author,
        field=field,
        year_from=year_from,
        year_to=year_to,
        min_citations=min_citations,
        institution=institution,
        user_id=user.id if user else None,
    )
    return PaperPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/{paper_id}", response_model=PaperDetail)
def get_paper(
    paper_id: int,
    db: Session = Depends(get_db),
    user: User | None = Depends(auth_service.get_optional_user),
) -> PaperDetail:
    return paper_service.get_paper(db, paper_id, user.id if user else None)


@router.post("/{paper_id}/marks", response_model=PaperMarks)
def toggle_mark(
    paper_id: int,
    req: MarkRequest,
    db: Session = Depends(get_db),
    user: User = Depends(auth_service.get_current_user),  # M9 标记需登录
) -> PaperMarks:
    """设置/取消个性化标记（幂等，需登录）：收藏 / 已读 / 稍后读。"""
    return paper_service.set_mark(db, paper_id, req.type, req.value, user.id)


@router.get("/{paper_id}/bibtex")
def paper_bibtex(paper_id: int, db: Session = Depends(get_db)) -> Response:
    """单篇 BibTeX（M7，科研引用一键下载）。"""
    item = paper_service.paper_item(db, paper_id)
    content, _, _ = export_service.export("bibtex", [item])
    return Response(
        content=content,
        media_type="application/x-bibtex; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="paper-{paper_id}.bib"'},
    )


@router.post("/{paper_id}/deep-summary")
def deep_summary(paper_id: int, db: Session = Depends(get_db)) -> dict:
    """AI 深度摘要（M7，DR-024）：按需生成 + 缓存复用（背景/问题/方法/实验/结论）。"""
    return paper_service.get_deep_summary(db, paper_id)
