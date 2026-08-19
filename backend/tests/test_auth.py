"""M9 认证测试：密码哈希 / HMAC token / 注册登录 API（TestClient + 内存库）。"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models import Base
from app.services import auth_service


class _DummyScheduler:
    def start(self):
        pass

    def shutdown(self, *args, **kwargs):
        pass


@pytest.fixture()
def client(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr("app.db.SessionLocal", session)
    monkeypatch.setattr("app.main.create_scheduler", lambda: _DummyScheduler())
    with TestClient(app) as c:
        yield c


# ---- 密码哈希 ----


def test_password_hash_and_verify():
    h = auth_service.hash_password("secret123")
    assert h.startswith("pbkdf2$sha256$")
    assert auth_service.verify_password("secret123", h)
    assert not auth_service.verify_password("wrong", h)
    assert not auth_service.verify_password("secret123", "garbage")


def test_hash_is_salted():
    assert auth_service.hash_password("same") != auth_service.hash_password("same")


# ---- token ----


def test_token_roundtrip():
    token = auth_service.create_token(42)
    assert auth_service.verify_token(token) == 42


def test_token_tampered():
    token = auth_service.create_token(42)
    tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
    assert auth_service.verify_token(tampered) is None


def test_token_garbage():
    assert auth_service.verify_token("not-a-token") is None


# ---- 注册 / 登录 API ----


def test_register_and_login(client):
    r = client.post("/api/auth/register", json={
        "username": "alice", "email": "alice@test.com", "password": "secret123",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["username"] == "alice"
    assert "token" in body

    r2 = client.post("/api/auth/login", json={"username": "alice", "password": "secret123"})
    assert r2.status_code == 200
    assert r2.json()["token"]


def test_login_by_email(client):
    client.post("/api/auth/register", json={
        "username": "alice", "email": "alice@test.com", "password": "secret123",
    })
    r = client.post("/api/auth/login", json={"username": "alice@test.com", "password": "secret123"})
    assert r.status_code == 200


def test_login_wrong_password(client):
    client.post("/api/auth/register", json={
        "username": "alice", "password": "secret123",
    })
    r = client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
    assert r.status_code == 401


def test_register_duplicate_username(client):
    client.post("/api/auth/register", json={"username": "alice", "password": "secret123"})
    r = client.post("/api/auth/register", json={"username": "alice", "password": "other456"})
    assert r.status_code == 409


def test_register_short_password(client):
    r = client.post("/api/auth/register", json={"username": "bob", "password": "123"})
    assert r.status_code == 422


def test_profile_requires_auth(client):
    r = client.get("/api/users/me/profile")
    assert r.status_code == 401


def test_profile_with_token(client):
    reg = client.post("/api/auth/register", json={
        "username": "alice", "password": "secret123",
    })
    r = client.get(
        "/api/users/me/profile",
        headers={"Authorization": f"Bearer {reg.json()['token']}"},
    )
    assert r.status_code == 200
    assert r.json()["username"] == "alice"
    assert r.json()["counts"] == {"bookmark": 0, "read": 0, "read_later": 0}


# ---- M9 反馈：资料修改 ----


def _auth_headers(reg_resp):
    return {"Authorization": f"Bearer {reg_resp.json()['token']}"}


def test_update_profile_username_and_email(client):
    reg = client.post("/api/auth/register", json={
        "username": "alice", "password": "secret123",
    })
    h = _auth_headers(reg)

    r = client.patch("/api/users/me", json={"username": "alice2", "email": "new@test.com"}, headers=h)
    assert r.status_code == 200
    assert r.json() == {"id": 1, "username": "alice2", "email": "new@test.com"}

    # 新用户名可登录
    r2 = client.post("/api/auth/login", json={"username": "alice2", "password": "secret123"})
    assert r2.status_code == 200


def test_update_profile_username_conflict(client):
    reg1 = client.post("/api/auth/register", json={"username": "alice", "password": "secret123"})
    client.post("/api/auth/register", json={"username": "bob", "password": "secret123"})

    # alice 想改成 bob（已被占用）→ 409
    r = client.patch("/api/users/me", json={"username": "bob"}, headers=_auth_headers(reg1))
    assert r.status_code == 409


def test_update_password_requires_old(client):
    reg = client.post("/api/auth/register", json={
        "username": "alice", "password": "secret123",
    })
    h = _auth_headers(reg)

    r = client.post("/api/users/me/password",
                    json={"old_password": "wrong", "new_password": "newpass123"}, headers=h)
    assert r.status_code == 401

    r2 = client.post("/api/users/me/password",
                     json={"old_password": "secret123", "new_password": "newpass123"}, headers=h)
    assert r2.status_code == 200
    assert r2.json() == {"ok": True}

    # 旧密码失效、新密码可登录
    assert client.post("/api/auth/login",
                       json={"username": "alice", "password": "secret123"}).status_code == 401
    assert client.post("/api/auth/login",
                       json={"username": "alice", "password": "newpass123"}).status_code == 200
