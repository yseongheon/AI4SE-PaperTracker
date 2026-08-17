"""关键词初筛测试：字段匹配、大小写、多词、多主题、幂等。"""
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.crawler.keyword_rules import load_rules, match_paper, run_keyword_screen
from app.models import Base, KeywordRule, Paper, PaperTopic, Topic


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    yield session
    session.close()


def _seed(db: Session) -> None:
    db.add(Topic(slug="code_repair", name_zh="代码修复"))
    db.add(Topic(slug="testing", name_zh="自动化测试"))
    db.add(Topic(slug="llm4se_general", name_zh="LLM4SE 通用"))
    db.commit()


def _rule(db: Session, slug: str, pattern: str, field: str = "any") -> None:
    tid = db.query(Topic.id).filter_by(slug=slug).scalar()
    db.add(KeywordRule(topic_id=tid, pattern=pattern, field=field))
    db.commit()


def test_match_case_insensitive(db: Session):
    _seed(db)
    _rule(db, "code_repair", "Program Repair")
    rules = load_rules(db)
    hits = match_paper("Using LLM for PROGRAM REPAIR", "abstract text", rules)
    assert set(hits) == {db.query(Topic.id).filter_by(slug="code_repair").scalar()}


def test_match_field_title_only(db: Session):
    _seed(db)
    _rule(db, "testing", "fuzz", field="title")
    rules = load_rules(db)
    assert match_paper("Fuzzing compilers", "we fuzz inputs", rules)
    assert match_paper("unrelated title", "we use fuzzing here", rules) == {}


def test_match_multi_word_or(db: Session):
    _seed(db)
    _rule(db, "testing", "test case generation | metamorphic testing")
    rules = load_rules(db)
    assert match_paper("Metamorphic testing of DNN", "", rules)
    assert match_paper("Test case generation for APIs", "", rules)
    assert match_paper("nothing relevant", "no tests here", rules) == {}


def test_multi_topic_hits(db: Session):
    _seed(db)
    _rule(db, "code_repair", "bug fix")
    _rule(db, "llm4se_general", "llm")
    rules = load_rules(db)
    hits = match_paper("LLM-based bug fixing", "", rules)
    assert len(hits) == 2


def test_run_keyword_screen_idempotent(db: Session):
    _seed(db)
    _rule(db, "code_repair", "bug fix")
    db.add(
        Paper(
            title="Bug fixing with LLM agents",
            title_normalized="bug fixing with llm agents",
            abstract="a bug fix study",
            status="fetched",
        )
    )
    db.add(Paper(title="Unrelated", title_normalized="unrelated", status="fetched"))
    db.commit()

    stats = run_keyword_screen(db)
    assert stats["candidates"] == 1
    paper = db.query(Paper).filter_by(title="Bug fixing with LLM agents").one()
    assert paper.is_ai4se_candidate is True
    assert db.query(PaperTopic).count() == 1

    # 重跑：标签不重复、候选不重复计数
    stats2 = run_keyword_screen(db)
    assert stats2["candidates"] == 1
    assert db.query(PaperTopic).count() == 1
    assert db.query(PaperTopic).filter_by(method="keyword").one().confidence == 0.6
