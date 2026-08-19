"""认证接口（M9）：注册 / 登录（HMAC token，DR-027）。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import exc as sa_exc
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str = Field(min_length=2, max_length=64, pattern=r"^[\w.-]+$")
    email: str | None = Field(default=None, max_length=128)
    password: str = Field(min_length=6, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str | None


class AuthResponse(BaseModel):
    token: str
    user: UserOut


@router.post("/register", response_model=AuthResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db)) -> AuthResponse:
    existing = db.query(User).filter(
        (User.username == req.username)
        | ((User.email == req.email) if req.email else False)
    ).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="用户名或邮箱已被注册")
    user = User(
        username=req.username,
        email=req.email,
        password_hash=auth_service.hash_password(req.password),
    )
    db.add(user)
    try:
        db.commit()
    except sa_exc.IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="用户名或邮箱已被注册")
    db.refresh(user)
    return AuthResponse(token=auth_service.create_token(user.id), user=UserOut.model_validate(user))


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.query(User).filter(
        (User.username == req.username) | ((User.email == req.username) if "@" in req.username else False)
    ).first()
    if user is None or not auth_service.verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return AuthResponse(token=auth_service.create_token(user.id), user=UserOut.model_validate(user))
