"""M6 导出测试：CSV（BOM/字段）、JSON、BibTeX（条目类型/转义/作者格式）+ API 端点。"""
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models import Base, Paper, Venue
from app.schemas.paper import PaperListItem, PaperMarks
from app.services import export_service


def make_item(
    title="Repairing Bugs with LLM & LLMs",
    authors=("Xiaoyu Wang", "Alice Zhang"),
    venue=None,
    year=2026,
    doi="10.1145/1234",
    arxiv_url="https://arxiv.org/abs/2601.12345",
) -> PaperListItem:
    return PaperListItem(
        id=1,
        title=title,
        authors=list(authors),
        venue=venue,
        topics=[],
        year=year,
        published_at=None,
        is_ai4se_confirmed=True,
        arxiv_url=arxiv_url,
        dblp_url=None,
        doi=doi,
        marks=PaperMarks(bookmark=True),
    )


def make_venue(short="ICSE", type="conference"):
    return Venue(id=1, short_name=short, full_name="Intl Conf on Software Engineering", type=type)


# ---- CSV ----


def test_csv_has_bom_and_header():
    data = export_service.to_csv([make_item()])
    assert data.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM（Excel 兼容）
    text = data.decode("utf-8-sig")
    lines = text.strip().splitlines()
    assert lines[0].startswith("id,title,authors,venue")
    row = lines[1]
    assert "Repairing Bugs with LLM & LLMs" in row
    assert "Xiaoyu Wang; Alice Zhang" in row
    assert ",yes," in row  # 收藏状态列（bookmarked=yes）


# ---- JSON ----


def test_json_roundtrip():
    items = [make_item()]
    parsed = json.loads(export_service.to_json(items).decode("utf-8"))
    assert parsed[0]["title"] == "Repairing Bugs with LLM & LLMs"
    assert parsed[0]["marks"]["bookmark"] is True


# ---- BibTeX ----


def test_bibtex_conference_entry():
    item = make_item(venue=make_venue())
    text = export_service.to_bibtex([item]).decode("utf-8")
    assert text.startswith("@inproceedings{260112345,")
    assert "booktitle = {Intl Conf on Software Engineering}" in text
    assert "author = {Wang, Xiaoyu and Zhang, Alice}" in text
    assert "doi = {10.1145/1234}" in text
    assert "url = {https://arxiv.org/abs/2601.12345}" in text


def test_bibtex_journal_entry():
    item = make_item(venue=make_venue(short="TSE", type="journal"))
    text = export_service.to_bibtex([item]).decode("utf-8")
    assert text.startswith("@article{")
    assert "journal = {Intl Conf on Software Engineering}" in text


def test_bibtex_preprint_fallback():
    item = make_item(venue=None)
    text = export_service.to_bibtex([item]).decode("utf-8")
    assert text.startswith("@misc{")
    assert "howpublished = {arXiv preprint}" in text


def test_bibtex_escapes_special_chars():
    """BibTeX 特殊字符 & % # _ 需转义，否则编译报错。"""
    text = export_service.to_bibtex([make_item()]).decode("utf-8")
    assert "\\&" in text  # & 被转义
    assert "LLM \\& LLMs" in text


def test_bibtex_author_formatting():
    item = make_item(authors=("Wang, Xiaoyu",))
    text = export_service.to_bibtex([item]).decode("utf-8")
    assert "author = {Wang, Xiaoyu}" in text


# ---- export() 分发 ----


def test_export_unsupported_format():
    with pytest.raises(ValueError):
        export_service.export("xml", [make_item()])


# ---- API 端点 ----


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
    db.add(
        Paper(
            title="Test Paper", title_normalized="test paper", year=2026,
            status="classified", arxiv_url="https://arxiv.org/abs/2601.99999",
        )
    )
    db.commit()
    db.close()
    monkeypatch.setattr("app.db.SessionLocal", session)
    monkeypatch.setattr("app.main.create_scheduler", lambda: _DummyScheduler())
    with TestClient(app) as c:
        yield c


def test_export_csv_endpoint(client):
    r = client.get("/api/export", params={"format": "csv"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"]
    assert r.content.startswith(b"\xef\xbb\xbf")


def test_export_bibtex_endpoint_with_filter(client):
    r = client.get("/api/export", params={"format": "bibtex", "year": 2026})
    assert r.status_code == 200
    assert r.content.startswith(b"@misc{")
