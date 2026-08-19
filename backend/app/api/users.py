"""用户画像接口（M9）：/users/me/profile（需登录）。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.services import auth_service, user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me/profile")
def my_profile(
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """个人画像：标记统计 / 收藏主题分布 / 最近收藏（需登录）。"""
    return user_service.profile(db, user)
