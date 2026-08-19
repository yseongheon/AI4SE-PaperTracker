"""M8 引用数测试：客户端解析/缓存、回填逻辑、API 排序筛选、导出（离线 mock，不触真实网络）。"""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.crawler.citation_client import CitationClient
from app.main import app
from app.models import Base, Paper


# ---- 客户端：缓存语义 ----


class _FakeHTTPX:
    """模拟 httpx.Client：按 URL 返回预设响应。"""

    def __init__(self, responses: dict[str, int | None]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get(self, url: str):
        self.calls.append(url)
        value = self.responses.get(url)
        if value is None:
            from httpx import Response
            return Response(404, request=httpx_request())
        from httpx import Response
        return Response(200, json=value, request=httpx_request())


def httpx_request():
    import httpx
    return httpx.Request("GET", "http://test")


def make_client(responses: dict[str, int | None], tmp_path) -> CitationClient:
    client = CitationClient(cache_dir=tmp_path / "cache")
    client.client = _FakeHTTPX(responses)  # type: ignore[assignment]
    return client


def test_citation_lookup_doi_preferred(tmp_path):
    """有 DOI：走 Crossref，不查 S2。"""
    url = "https://api.crossref.org/works/10.1145%2F123"
    client = make_client({url: {"message": {"is-referenced-by-count": 42}}}, tmp_path)

    assert client.lookup("10.1145/123", "2501.11111") == 42
    assert len(client.client.calls) == 1
    assert "crossref" in client.client.calls[0]


def test_citation_lookup_doi_missing_falls_back_to_s2(tmp_path):
    """Crossref 404 → 兜底 Semantic Scholar。"""
    crossref = "https://api.crossref.org/works/10.1145%2F123"
    s2 = "https://api.semanticscholar.org/graph/v1/paper/arXiv:2501.11111?fields=citationCount"
    client = make_client(
        {crossref: None, s2: {"citationCount": 7}}, tmp_path
    )

    assert client.lookup("10.1145/123", "2501.11111") == 7
    assert len(client.client.calls) == 2


def test_citation_lookup_arxiv_only(tmp_path):
    s2 = "https://api.semanticscholar.org/graph/v1/paper/arXiv:2501.22222?fields=citationCount"
    client = make_client({s2: {"citationCount": 3}}, tmp_path)

    assert client.lookup(None, "2501.22222") == 3


def test_citation_cache_short_circuits(tmp_path):
    """缓存命中后不再发请求（断点续跑语义）。"""
    s2 = "https://api.semanticscholar.org/graph/v1/paper/arXiv:2501.11111?fields=citationCount"
    client = make_client({s2: {"citationCount": 5}}, tmp_path)

    assert client.lookup(None, "2501.11111") == 5
    assert client.lookup(None, "2501.11111") == 5  # 第二次走缓存
    assert len(client.client.calls) == 1


def test_citation_cache_miss_persists(tmp_path):
    """404 也缓存（避免每次重查）。"""
    s2 = "https://api.semanticscholar.org/graph/v1/paper/arXiv:2501.33333?fields=citationCount"
    client = make_client({s2: None}, tmp_path)

    assert client.lookup(None, "2501.33333") is None
    assert client.lookup(None, "2501.33333") is None
    assert len(client.client.calls) == 1


# ---- API：排序 / 筛选 / 字段 ----


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
    db.add_all([
        Paper(title="High Cited", title_normalized="high cited", year=2025,
              citation_count=100, published_at=datetime(2025, 1, 1), status="classified"),
        Paper(title="Low Cited", title_normalized="low cited", year=2026,
              citation_count=2, published_at=datetime(2026, 1, 1), status="classified"),
        Paper(title="No Data", title_normalized="no data", year=2026,
              citation_count=None, published_at=datetime(2026, 2, 1), status="classified"),
    ])
    db.commit()
    db.close()
    monkeypatch.setattr("app.db.SessionLocal", session)
    monkeypatch.setattr("app.main.create_scheduler", lambda: _DummyScheduler())
    with TestClient(app) as c:
        yield c


def test_list_sorted_by_citations(client):
    r = client.get("/api/papers", params={"sort": "citations"})
    items = r.json()["items"]
    assert [i["title"] for i in items] == ["High Cited", "Low Cited", "No Data"]


def test_min_citations_filter(client):
    r = client.get("/api/papers", params={"min_citations": 10})
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "High Cited"


def test_item_includes_citation_count(client):
    r = client.get("/api/papers/1")
    assert r.json()["citation_count"] == 100


def test_export_csv_includes_cited_by(client):
    r = client.get("/api/export", params={"format": "csv"})
    assert b"cited_by" in r.content.splitlines()[0]
    assert b"100" in r.content


def test_export_bibtex_includes_note(client):
    r = client.get("/api/export", params={"format": "bibtex", "min_citations": 10})
    assert b"note = {Cited by 100}" in r.content
