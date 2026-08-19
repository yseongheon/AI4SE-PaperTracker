"""M6 周报测试：collect_stats 统计 + render_report 渲染（离线，内存 SQLite）。

用可控的 created_at/updated_at（手工赋值而非 server_default）构造近 7 天数据。
"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Paper, PaperTopic, Topic, Venue
from scripts.weekly_report import collect_stats, render_report

NOW = datetime(2026, 8, 19, 0, 0, 0)


@pytest.fixture()
def db(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def add_paper(db, title, *, created_days_ago=1, topics=(), venue=None, confirmed=True,
              highlights=None, updated_days_ago=None, year=2026, match_status="none"):
    p = Paper(
        title=title,
        title_normalized=title.lower(),
        year=year,
        created_at=NOW - timedelta(days=created_days_ago),
        updated_at=NOW - timedelta(days=updated_days_ago) if updated_days_ago else NOW,
        is_ai4se_confirmed=confirmed,
        status="classified",
        venue=venue,
        highlights=highlights,
        match_status=match_status,
        arxiv_url=f"https://arxiv.org/abs/2601.{abs(hash(title)) % 99999:05d}",
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


def test_collect_stats_counts_new_ai4se_and_old(db):
    db.add(Venue(short_name="ICSE", full_name="ICSE", type="conference", rank="A"))
    db.commit()
    add_paper(db, "New AI4SE Paper", topics=("code_repair",),
              highlights={"contribution": "新方法", "limitation": "规模小"})
    add_paper(db, "Old Non-AI4SE", created_days_ago=10, confirmed=False)
    add_paper(db, "Old AI4SE", created_days_ago=10)
    db.commit()

    stats = collect_stats(db, days=7)

    assert stats["total"] == 1  # 只算近 7 天新增
    assert stats["ai4se"] == 1
    assert stats["topic_counts"] == [("code_repair", "code_repair", 1)]
    assert len(stats["highlights"]) == 1


def test_collect_stats_matched_within_window(db):
    icse = Venue(short_name="ICSE", full_name="ICSE", type="conference", rank="A")
    db.add(icse)
    db.flush()
    add_paper(db, "Newly Matched", created_days_ago=2, venue=icse,
              updated_days_ago=1, match_status="matched")
    p = Paper(
        title="Old Matched", title_normalized="old matched", year=2025,
        created_at=NOW - timedelta(days=30), updated_at=NOW - timedelta(days=20),
        match_status="matched", venue=icse, status="matched",
    )
    db.add(p)
    db.commit()

    stats = collect_stats(db, days=7)

    assert len(stats["matched"]) == 1
    assert stats["matched"][0].title == "Newly Matched"  # 30 天前的匹配不在窗口内


def test_render_report_markdown(db):
    add_paper(db, "Highlight Paper", topics=("testing",),
              highlights={"contribution": "贡献一句话", "limitation": "局限一句话"})
    db.commit()

    content = render_report(collect_stats(db), "08-12 ~ 08-19")

    assert "# AI4SE PaperTracker 周报（08-12 ~ 08-19）" in content
    assert "新增入库论文：**1** 篇" in content
    assert "| testing（testing） | 1 |" in content
    assert "### 1. Highlight Paper" in content
    assert "贡献：贡献一句话" in content
    assert "局限：局限一句话" in content


def test_render_report_empty_state(db):
    content = render_report(collect_stats(db), "08-12 ~ 08-19")

    assert "本周无新增 AI4SE 论文" in content
    assert "本周无新匹配" in content
    assert "本周无亮点速读论文" in content
