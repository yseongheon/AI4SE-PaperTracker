"""FastAPI 入口：路由挂载与生命周期管理（M10：生产模式托管前端静态文件）。"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.auth import router as auth_router
from app.api.export import router as export_router
from app.api.health import router as health_router
from app.api.papers import router as papers_router
from app.api.stats import router as stats_router
from app.api.topics import router as topics_router
from app.api.users import router as users_router
from app.api.venues import router as venues_router
from app.crawler.scheduler import create_scheduler

# 生产模式（M10）：frontend/dist 存在时由后端托管前端（单端口访问）
DIST_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 每日定时爬取（DR-008：APScheduler 进程内调度，手动 CLI 兜底）
    scheduler = create_scheduler()
    scheduler.start()
    app.state.scheduler = scheduler
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="AI4SE PaperTracker API",
    description="自动跟踪 AI4SE（AI for Software Engineering）论文：arXiv 爬取、A 会匹配、主题分类",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth_router, prefix="/api")
app.include_router(health_router, prefix="/api")
app.include_router(papers_router, prefix="/api")
app.include_router(topics_router, prefix="/api")
app.include_router(venues_router, prefix="/api")
app.include_router(stats_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(export_router, prefix="/api")


@app.get("/", response_model=None)
def root():
    """生产模式（dist 存在）时首页直接给前端页面；否则返回服务信息。"""
    if DIST_DIR.exists():
        return FileResponse(DIST_DIR / "index.html")
    return {"service": "ai4se-papertracker", "docs": "/docs", "health": "/api/health"}


# ---- M10 生产模式：托管前端静态文件（SPA history 路由 fallback） ----

if DIST_DIR.exists():
    _assets = DIST_DIR / "assets"
    if _assets.exists():
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        """非 API 路径：静态文件存在则直接返回，否则回退 index.html（Vue history 路由）。"""
        file = DIST_DIR / full_path
        if full_path and file.is_file():
            return FileResponse(file)
        return FileResponse(DIST_DIR / "index.html")
