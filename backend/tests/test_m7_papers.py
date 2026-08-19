"""M7 论文接口扩展测试：author/field/年份区间过滤、pdf_url、单篇 BibTeX、export ids、deep-summary 缓存。"""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models import Author, Base, Paper, PaperAuthor


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
            title="LLM Bug Repair with Agents",
            title_normalized="llm bug repair with agents",
            abstract="we repair software defects using large language models",
            year=2026,
            published_at=datetime(2026, 3, 1),
            status="classified",
            arxiv_url="https://arxiv.org/abs/2601.11111",
            is_ai4se_confirmed=True,
        ),
        Paper(
            title="Compiler Optimization Survey",
            title_normalized="compiler optimization survey",
            abstract="a survey of compiler optimizations",
            year=2025,
            published_at=datetime(2025, 6, 1),
            status="classified",
            arxiv_url=None,
        ),
    ]
    db.add_all(papers)
    db.flush()
    db.add(Author(name="Xiaoyu Wang", name_normalized="xiaoyu wang"))
    db.flush()
    alice = Author(name="Alice Zhang", name_normalized="alice zhang")
    db.add(alice)
    db.flush()
    db.add(PaperAuthor(paper_id=papers[0].id, author_id=1, position=0))
    db.add(PaperAuthor(paper_id=papers[0].id, author_id=alice.id, position=1))
    db.add(PaperAuthor(paper_id=papers[1].id, author_id=alice.id, position=0))
    db.commit()
    db.close()

    monkeypatch.setattr("app.db.SessionLocal", session)
    monkeypatch.setattr("app.main.create_scheduler", lambda: _DummyScheduler())
    with TestClient(app) as c:
        yield c


# ---- 过滤扩展 ----


def test_filter_by_author(client):
    r = client.get("/api/papers", params={"author": "alice"})
    assert r.status_code == 200
    assert r.json()["total"] == 2

    r2 = client.get("/api/papers", params={"author": "xiaoyu"})
    assert r2.json()["total"] == 1
    assert r2.json()["items"][0]["title"].startswith("LLM Bug Repair")


def test_search_field_title_only(client):
    r = client.get("/api/papers", params={"q": "survey", "field": "title"})
    assert r.status_code == 200
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["title"].startswith("Compiler")


def test_search_field_abstract_only(client):
    # "defects" 只在摘要里；field=title 搜不到
    r = client.get("/api/papers", params={"q": "defects", "field": "title"})
    assert r.json()["total"] == 0
    r2 = client.get("/api/papers", params={"q": "defects", "field": "abstract"})
    assert r2.json()["total"] == 1


def test_year_range_filter(client):
    r = client.get("/api/papers", params={"year_from": 2026})
    assert r.json()["total"] == 1
    r2 = client.get("/api/papers", params={"year_from": 2020, "year_to": 2025})
    assert r2.json()["total"] == 1
    assert r2.json()["items"][0]["year"] == 2025


# ---- pdf_url / 单篇 BibTeX ----


def test_detail_includes_pdf_url(client):
    r = client.get("/api/papers/1")
    assert r.json()["pdf_url"] == "https://arxiv.org/pdf/2601.11111"
    r2 = client.get("/api/papers/2")
    assert r2.json()["pdf_url"] is None


def test_single_paper_bibtex(client):
    r = client.get("/api/papers/1/bibtex")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/x-bibtex")
    assert "attachment" in r.headers["content-disposition"]
    assert r.content.startswith(b"@misc{260111111,")


def test_bibtex_404(client):
    assert client.get("/api/papers/999/bibtex").status_code == 404


# ---- export ids ----


def test_export_ids(client):
    r = client.get("/api/export", params={"format": "csv", "ids": "1,2"})
    assert r.status_code == 200
    assert b"LLM Bug Repair" in r.content
    assert b"Compiler Optimization" in r.content

    r2 = client.get("/api/export", params={"format": "csv", "ids": "2"})
    assert b"LLM Bug Repair" not in r2.content
    assert b"Compiler Optimization" in r2.content


# ---- deep-summary：缓存语义 ----


def test_deep_summary_generates_and_caches(client, monkeypatch):
    calls = {"n": 0}

    def fake_generate(title, abstract, year):
        calls["n"] += 1
        return {
            "background": "背景", "problem": "问题", "method": "方法",
            "results": "结果", "conclusion": "结论",
        }

    monkeypatch.setattr(
        "app.crawler.classifier.generate_deep_summary", fake_generate
    )

    r1 = client.post("/api/papers/1/deep-summary")
    assert r1.status_code == 200
    assert r1.json()["background"] == "背景"
    assert calls["n"] == 1

    # 第二次：缓存命中，不再调 LLM
    r2 = client.post("/api/papers/1/deep-summary")
    assert r2.status_code == 200
    assert r2.json()["method"] == "方法"
    assert calls["n"] == 1


def test_deep_summary_404_and_failure(client, monkeypatch):
    assert client.post("/api/papers/999/deep-summary").status_code == 404

    monkeypatch.setattr(
        "app.crawler.classifier.generate_deep_summary",
        lambda title, abstract, year: None,
    )
    r = client.post("/api/papers/1/deep-summary")
    assert r.status_code == 503
