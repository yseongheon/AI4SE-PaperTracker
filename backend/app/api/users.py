"""用户画像与资料接口（M9）：/users/me/*（需登录）。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import exc as sa_exc
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


class UpdateProfileRequest(BaseModel):
    username: str | None = Field(default=None, min_length=2, max_length=64, pattern=r"^[\w.-]+$")
    email: str | None = Field(default=None, max_length=128)


class UpdatePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=128)


@router.patch("/me")
def update_profile(
    req: UpdateProfileRequest,
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """修改用户名 / 邮箱（M9 反馈）；用户名唯一冲突 409。"""
    if req.username is not None:
        conflict = db.query(User).filter(
            User.username == req.username, User.id != user.id
        ).first()
        if conflict is not None:
            raise HTTPException(status_code=409, detail="用户名已被占用")
        user.username = req.username
    if req.email is not None:
        conflict = db.query(User).filter(
            User.email == req.email, User.id != user.id
        ).first()
        if conflict is not None:
            raise HTTPException(status_code=409, detail="邮箱已被占用")
        user.email = req.email or None
    try:
        db.commit()
    except sa_exc.IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="用户名或邮箱已被占用")
    db.refresh(user)
    return {"id": user.id, "username": user.username, "email": user.email}


@router.post("/me/password")
def update_password(
    req: UpdatePasswordRequest,
    user: User = Depends(auth_service.get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """修改密码（M9 反馈）：需验证旧密码。"""
    if not auth_service.verify_password(req.old_password, user.password_hash):
        raise HTTPException(status_code=401, detail="旧密码不正确")
    user.password_hash = auth_service.hash_password(req.new_password)
    db.commit()
    return {"ok": True}
