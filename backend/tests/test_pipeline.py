"""upsert 幂等性测试：批次去重、重复运行无重复数据。"""
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.crawler.arxiv_client import ArxivEntry
from app.crawler.pipeline import upsert_papers
from app.models import Base, Paper


@pytest.fixture()
def db():
    """每个测试独立的内存库；与 app/db.py 一致 autoflush=False（批次去重依赖该行为）。"""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    yield session
    session.close()


def _entry(arxiv_id: str, title: str) -> ArxivEntry:
    return ArxivEntry(
        arxiv_id=arxiv_id,
        title=title,
        abstract="abstract",
        authors=["Alice Zhang"],
        published=datetime(2026, 8, 1),
        updated=datetime(2026, 8, 2),
        journal_ref=None,
        comment=None,
        categories=["cs.SE"],
        url=f"https://arxiv.org/abs/{arxiv_id}",
    )


def test_upsert_batch_duplicate_id(db: Session):
    """同批次 v1/v2 双 entry（normalized_id 相同）不重复插入、不违反唯一约束。"""
    entries = [
        _entry("2607.26451v1", "ExplainBench: Evaluating Code Explanations from Agents"),
        _entry("2607.26451v2", "ExplainBench: Evaluating Code Explanations from Agents"),
    ]
    new_count, updated_count = upsert_papers(db, entries)

    assert new_count == 1
    assert updated_count == 0
    assert db.query(Paper).count() == 1


def test_upsert_idempotent_rerun(db: Session):
    """重跑同一批：不新增、只更新。"""
    entries = [
        _entry("2607.11111", "First Paper Title"),
        _entry("2607.22222", "Second Paper Title"),
    ]
    new_count, updated_count = upsert_papers(db, entries)
    assert (new_count, updated_count) == (2, 0)

    new_count, updated_count = upsert_papers(db, entries)
    assert (new_count, updated_count) == (0, 2)
    assert db.query(Paper).count() == 2
