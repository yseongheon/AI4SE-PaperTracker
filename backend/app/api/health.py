"""健康检查接口（前后端联通验证用）。"""
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "ai4se-papertracker", "version": "0.1.0"}
