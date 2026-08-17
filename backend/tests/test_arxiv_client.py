"""arXiv Atom feed 解析测试：离线 fixture，不依赖网络。"""
from datetime import datetime
from pathlib import Path

from app.crawler.arxiv_client import ArxivClient

FIXTURE = Path(__file__).parent / "fixtures" / "arxiv_feed.xml"


def _entries():
    return ArxivClient._parse_feed(FIXTURE.read_text(encoding="utf-8"))


def test_parse_two_entries():
    entries = _entries()
    assert len(entries) == 2


def test_parse_fields():
    e = _entries()[0]
    assert e.arxiv_id == "2502.12345v2"
    assert e.normalized_id == "2502.12345"
    assert e.title == "Repairing Bugs with \\emph{LLM} Agents: An Empirical Study"
    assert e.abstract == "We study how large language models help repair software bugs across real-world projects."
    assert e.authors == ["Xiaoyu Wang", "Alice Zhang"]
    assert e.journal_ref == "Accepted at ICSE 2026"
    assert e.comment == "32 pages, 8 figures"
    assert e.published == datetime(2026, 2, 1, 9, 0)
    assert e.updated == datetime(2026, 2, 5, 10, 0)
    assert e.categories == ["cs.SE"]
    assert e.url == "http://arxiv.org/abs/2502.12345v2"


def test_parse_multiple_categories():
    e = _entries()[1]
    assert e.normalized_id == "2602.99999"
    assert e.categories == ["cs.SE", "cs.PL"]
    assert e.journal_ref is None
