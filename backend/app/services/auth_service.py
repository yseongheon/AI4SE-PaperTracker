"""认证服务（M9，DR-027 拍板：自建 HMAC token，零新依赖）。

- 密码哈希：标准库 hashlib.pbkdf2_hmac（sha256，10 万次迭代，随机盐）
- token：HMAC-SHA256 签名 "uid.expiry.signature"（base64url），无状态、零依赖
- 依赖注入 get_current_user：Authorization: Bearer <token> → User，失效/缺失 → 401
"""
import base64
import hashlib
import hmac
import json
import secrets
import time

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import User

PBKDF2_ITERATIONS = 100_000
TOKEN_TTL_SECONDS = 30 * 24 * 3600  # 30 天免登录


# ---- 密码哈希 ----

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return "pbkdf2$sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.b64encode(salt).decode(),
        base64.b64encode(digest).decode(),
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        _, _, iterations_s, salt_s, hash_s = stored.split("$")
        salt = base64.b64decode(salt_s)
        expected = base64.b64decode(hash_s)
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt, int(iterations_s)
        )
        return hmac.compare_digest(digest, expected)
    except (ValueError, TypeError):
        return False


# ---- HMAC token ----

def _sign(uid: int, expiry: int) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"uid": uid, "exp": expiry}).encode()).rstrip(b"=").decode()
    signature = hmac.new(settings.auth_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def create_token(user_id: int) -> str:
    return _sign(user_id, int(time.time()) + TOKEN_TTL_SECONDS)


def verify_token(token: str) -> int | None:
    """校验 token → user_id；签名错误/过期返回 None。"""
    try:
        payload_s, signature = token.split(".")
        expected = hmac.new(
            settings.auth_secret.encode(), payload_s.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        data = json.loads(
            base64.urlsafe_b64decode(payload_s + "=" * (-len(payload_s) % 4))
        )
        if int(data["exp"]) < time.time():
            return None
        return int(data["uid"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None


# ---- FastAPI 依赖 ----

def get_current_user(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """Authorization: Bearer <token> → User；缺失/无效 → 401。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录：请先登录")
    uid = verify_token(authorization.removeprefix("Bearer ").strip())
    if uid is None:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    user = db.get(User, uid)
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


def get_optional_user(
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> User | None:
    """可选用户（浏览接口用）：未登录返回 None，不抛 401。"""
    if not authorization or not authorization.startswith("Bearer "):
        return None
    uid = verify_token(authorization.removeprefix("Bearer ").strip())
    if uid is None:
        return None
    return db.get(User, uid)
