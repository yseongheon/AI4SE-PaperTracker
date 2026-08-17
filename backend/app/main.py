"""FastAPI 入口：路由挂载与生命周期管理。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # M1 起在此挂载 APScheduler 定时任务；M0 仅占位
    yield


app = FastAPI(
    title="AI4SE PaperTracker API",
    description="自动跟踪 AI4SE（AI for Software Engineering）论文：arXiv 爬取、A 会匹配、主题分类",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router, prefix="/api")


@app.get("/")
def root() -> dict:
    return {"service": "ai4se-papertracker", "docs": "/docs", "health": "/api/health"}
