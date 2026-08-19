"""M6 亮点速读 + 相关推荐测试：LlmResult 解析扩展、related_papers 排序（离线，内存 SQLite）。"""
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.crawler.classifier import parse_llm_result
from app.models import Base, Paper, PaperTopic, Topic
from app.services.paper_service import related_papers


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


# ---- parse_llm_result：highlights 解析 ----


def test_parse_highlights_valid():
    r = parse_llm_result(
        '{"is_ai4se": true, "topics": ["code_repair"], "summary_zh": "摘要", '
        '"confidence": 0.9, "highlights": {"contribution": "提出新修复方法", "limitation": "规模小"}}'
    )
    assert r is not None
    assert r.highlights == {"contribution": "提出新修复方法", "limitation": "规模小"}


def test_parse_highlights_absent_ok():
    """旧格式输出（无 highlights）不破坏解析：highlights=None。"""
    r = parse_llm_result(
        '{"is_ai4se": true, "topics": ["testing"], "summary_zh": "摘要", "confidence": 0.8}'
    )
    assert r is not None
    assert r.highlights is None


def test_parse_highlights_not_dict_tolerated():
    r = parse_llm_result(
        '{"is_ai4se": true, "topics": ["testing"], "summary_zh": "摘要", '
        '"confidence": 0.8, "highlights": "oops"}'
    )
    assert r is not None
    assert r.highlights is None


def test_parse_highlights_partial_fields():
    """只给 contribution 也给 highlights；字段为空串时 None。"""
    r = parse_llm_result(
        '{"is_ai4se": true, "topics": ["testing"], "summary_zh": "摘要", '
        '"confidence": 0.8, "highlights": {"contribution": "   "}}'
    )
    assert r is not None
    assert r.highlights is None


def test_parse_highlights_strips_whitespace():
    r = parse_llm_result(
        '{"is_ai4se": true, "topics": ["testing"], "summary_zh": "摘要", '
        '"confidence": 0.8, "highlights": {"contribution": " 亮点  ", "limitation": null}}'
    )
    assert r is not None
    assert r.highlights["contribution"] == "亮点"
    assert r.highlights["limitation"] == ""


# ---- related_papers：同主题 + 标题相似度排序 ----


def make_paper(db, title, year=2026, topics=(), published=None):
    p = Paper(
        title=title,
        title_normalized=title.lower(),
        year=year,
        published_at=published or datetime(2026, 1, 1),
        status="classified",
    )
    db.add(p)
    db.flush()
    for slug in topics:
        t = db.query(Topic).filter_by(slug=slug).first()
        if t is None:
            t = Topic(slug=slug, name_zh=slug)
            db.add(t)
            db.flush()
        db.add(PaperTopic(paper_id=p.id, topic_id=t.id, method="llm"))
    return p


def test_related_prefers_same_topic_and_title_similarity(db):
    """同主题池按标题 Jaccard 排序：标题相近者排前，不同主题者不出现。"""
    repair = Topic(slug="code_repair", name_zh="代码修复")
    testing = Topic(slug="testing", name_zh="自动化测试")
    db.add_all([repair, testing])
    db.flush()
    target = make_paper(db, "Repairing Bugs with LLM Agents", topics=("code_repair",))
    close = make_paper(db, "Repairing Bugs with LLM Agents at Scale", topics=("code_repair",))
    far = make_paper(db, "Bugs with Agents", topics=("code_repair",))
    # 不同主题 + 不同年份：不进同主题池，也不进同 year 保底池
    other_topic = make_paper(
        db, "Repairing Bugs with LLM Agents II", topics=("testing",), year=2025
    )
    db.commit()

    related = related_papers(db, target, limit=5)

    ids = [p.id for p in related]
    assert close.id in ids and far.id in ids
    assert other_topic.id not in ids  # 不同主题不进池
    assert related[0].id == close.id  # 标题最相近的排第一


def test_related_falls_back_to_year_pool(db):
    """无同主题时退回同 year 池（保底不为空）。"""
    make_paper(db, "A completely different title", year=2026)
    make_paper(db, "Another different paper", year=2025)  # 不同年份不进池
    target = make_paper(db, "Solo Paper With No Topics", year=2026)
    db.commit()

    related = related_papers(db, target, limit=5)

    assert len(related) == 1
    assert "different" in related[0].title


def test_related_excludes_self(db):
    make_paper(db, "Repairing Bugs with LLM Agents", year=2026)
    target = make_paper(db, "Repairing Bugs with LLM Agents", year=2026)
    db.commit()

    related = related_papers(db, target, limit=5)

    assert all(p.id != target.id for p in related)
