"""M6 个性化标记 API 测试：toggle 幂等、过滤参数、列表项 marks 集合（TestClient + 内存库）。"""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models import Base, Paper


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
    db = session()

    papers = [
        Paper(
            title=f"Paper {i}",
            title_normalized=f"paper {i}",
            year=2026,
            published_at=datetime(2026, 1, i + 1),
            status="classified",
        )
        for i in range(1, 4)
    ]
    db.add_all(papers)
    db.commit()
    db.close()

    monkeypatch.setattr("app.db.SessionLocal", session)
    monkeypatch.setattr("app.main.create_scheduler", lambda: _DummyScheduler())
    with TestClient(app) as c:
        yield c


def test_mark_roundtrip(client):
    r = client.post("/api/papers/1/marks", json={"type": "bookmark", "value": True})
    assert r.status_code == 200
    assert r.json()["bookmark"] is True
    assert r.json()["read"] is False

    # 幂等：重复设置不报错
    r2 = client.post("/api/papers/1/marks", json={"type": "bookmark", "value": True})
    assert r2.status_code == 200
    assert r2.json()["bookmark"] is True

    # 取消
    r3 = client.post("/api/papers/1/marks", json={"type": "bookmark", "value": False})
    assert r3.status_code == 200
    assert r3.json()["bookmark"] is False


def test_mark_404(client):
    r = client.post("/api/papers/999/marks", json={"type": "bookmark", "value": True})
    assert r.status_code == 404


def test_mark_invalid_type(client):
    r = client.post("/api/papers/1/marks", json={"type": "star", "value": True})
    assert r.status_code == 422


def test_list_items_include_marks(client):
    client.post("/api/papers/1/marks", json={"type": "bookmark", "value": True})
    client.post("/api/papers/1/marks", json={"type": "read", "value": True})

    r = client.get("/api/papers")
    items = {i["id"]: i for i in r.json()["items"]}
    assert items[1]["marks"] == {"bookmark": True, "read": True, "read_later": False}
    assert items[2]["marks"] == {"bookmark": False, "read": False, "read_later": False}


def test_filter_bookmarked(client):
    client.post("/api/papers/2/marks", json={"type": "bookmark", "value": True})

    r = client.get("/api/papers", params={"marks": "bookmark"})
    body = r.json()
    assert body["total"] == 1
    assert [i["id"] for i in body["items"]] == [2]


def test_filter_unread(client):
    client.post("/api/papers/1/marks", json={"type": "read", "value": True})

    r = client.get("/api/papers", params={"marks": "unread"})
    body = r.json()
    assert body["total"] == 2
    assert {i["id"] for i in body["items"]} == {2, 3}


def test_filter_invalid_marks(client):
    r = client.get("/api/papers", params={"marks": "star"})
    assert r.status_code == 422


def test_detail_includes_marks_and_related(client):
    client.post("/api/papers/1/marks", json={"type": "read_later", "value": True})
    r = client.get("/api/papers/1")
    body = r.json()
    assert body["marks"] == {"bookmark": False, "read": False, "read_later": True}
    assert isinstance(body["related"], list)  # 无同主题时退回同 year 池
    related_ids = {p["id"] for p in body["related"]}
    assert related_ids == {2, 3}
    assert all(p["id"] != 1 for p in body["related"])  # 排除自身
