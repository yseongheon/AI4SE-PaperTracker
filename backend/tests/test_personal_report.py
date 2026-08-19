"""M9 个人周报测试：收藏统计 + 渲染（离线，内存 SQLite）。"""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, Paper, PaperTopic, Topic, User, UserMark
from scripts.personal_report import render_personal_report, user_week_stats, users_with_bookmarks

NOW = datetime(2026, 8, 19, 0, 0, 0)


@pytest.fixture()
def db(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def make_user(db, username="alice"):
    user = User(username=username, password_hash="x")
    db.add(user)
    db.flush()
    return user


def make_paper(db, title, topics=(), created_days_ago=1, highlights=None):
    p = Paper(
        title=title, title_normalized=title.lower(), year=2026,
        created_at=NOW - timedelta(days=created_days_ago),
        status="classified", is_ai4se_confirmed=True,
        highlights=highlights, arxiv_url=f"https://arxiv.org/abs/2601.{abs(hash(title)) % 99999:05d}",
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


def test_users_with_bookmarks_filters(db):
    alice = make_user(db)
    bob = make_user(db, "bob")
    p = make_paper(db, "Paper A")
    db.add(UserMark(user_id=alice.id, paper_id=p.id, mark_type="bookmark"))
    db.commit()

    users = users_with_bookmarks(db)
    assert [u.username for u in users] == ["alice"]


def test_user_week_stats_counts_new_marks(db):
    alice = make_user(db)
    new_paper = make_paper(db, "New Paper", topics=("code_repair",))
    old_paper = make_paper(db, "Old Paper", created_days_ago=10)
    db.add_all([
        UserMark(user_id=alice.id, paper_id=new_paper.id, mark_type="bookmark",
                 created_at=NOW - timedelta(days=1)),
        UserMark(user_id=alice.id, paper_id=old_paper.id, mark_type="bookmark",
                 created_at=NOW - timedelta(days=10)),
    ])
    db.commit()

    stats = user_week_stats(db, alice)

    assert [p.title for p in stats["new_marks"]] == ["New Paper"]  # 只算近 7 天
    assert stats["topic_dist"] == [("code_repair", "code_repair", 1)]


def test_render_personal_report(db):
    alice = make_user(db)
    p = make_paper(db, "Highlight Paper", topics=("testing",),
                   highlights={"contribution": "贡献一句话"})
    db.add(UserMark(user_id=alice.id, paper_id=p.id, mark_type="bookmark"))
    db.commit()

    content = render_personal_report(alice, user_week_stats(db, alice), "08-12 ~ 08-19")

    assert "# alice 的收藏周报（08-12 ~ 08-19）" in content
    assert "本周新收藏 **1** 篇" in content
    assert "### Highlight Paper" in content
    assert "贡献：贡献一句话" in content


def test_render_personal_report_empty(db):
    alice = make_user(db)
    content = render_personal_report(alice, user_week_stats(db, alice), "08-12 ~ 08-19")
    assert "本周新收藏 **0** 篇" in content
    assert "本周无新收藏" in content
