"""M3 API 集成测试：TestClient + 内存 SQLite（不触真实数据/网络/调度器）。

覆盖：列表分页/搜索/过滤/排序、详情/404、主题与会议计数、趋势三种分组 + 日期过滤。
"""
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models import Base, Author, Paper, PaperAuthor, PaperTopic, Topic, Venue


class _DummyScheduler:
    def start(self):
        pass

    def shutdown(self, *args, **kwargs):
        pass


@pytest.fixture()
def client(monkeypatch):
    # StaticPool：内存库所有会话共享同一连接（否则每连接独立空库）
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    db = session()
    icse = Venue(short_name="ICSE", full_name="Intl Conf on Software Engineering", rank="A")
    fse = Venue(short_name="FSE", full_name="Foundations of Software Engineering", rank="A")
    db.add_all([icse, fse])
    repair = Topic(slug="code_repair", name_zh="代码修复")
    testing = Topic(slug="testing", name_zh="自动化测试")
    llm = Topic(slug="llm4se_general", name_zh="综合与综述")
    db.add_all([repair, testing, llm])
    db.commit()

    seq = [0]

    def _paper(title, abstract, published, *, venue=None, confirmed=False,
               candidate=False, topics=(), year=2026, authors=(), affiliations=()):
        seq[0] += 1
        n = seq[0]
        p = Paper(
            title=title, title_normalized=title.lower(),
            abstract=abstract, published_at=published, year=year,
            venue=venue, is_ai4se_confirmed=confirmed,
            is_ai4se_candidate=candidate, status="classified",
            arxiv_url=f"https://arxiv.org/abs/2601.{n:05d}",
            dblp_key=f"conf/icse/{n:05d}" if venue else None,
        )
        db.add(p)
        db.flush()
        for slug in topics:
            tid = db.query(Topic.id).filter_by(slug=slug).scalar()
            db.add(PaperTopic(paper_id=p.id, topic_id=tid, confidence=0.9, method="llm"))
        for i, name in enumerate(authors):
            a = Author(name=name, name_normalized=name.lower())
            db.add(a)
            db.flush()
            db.add(PaperAuthor(
                paper_id=p.id, author_id=a.id, position=i,
                affiliation=affiliations[i] if affiliations and i < len(affiliations) else None,
            ))
        return p

    _paper("Bug Fixing with LLM", "we repair defects using llm", datetime(2026, 3, 1),
           venue=icse, confirmed=True, candidate=True, topics=("code_repair",),
           authors=("Alice", "Bob"),
           affiliations=("university of copenhagen", "university of copenhagen"))
    _paper("Test Generation Survey", "survey of llm test generation", datetime(2026, 4, 15),
           venue=fse, confirmed=True, candidate=True, topics=("testing", "llm4se_general"),
           authors=("Carol",), affiliations=("kth royal institute of technology",))
    _paper("Unrelated Compiler Paper", "we optimize compilers", datetime(2026, 5, 1),
           topics=(), authors=("Dave",))
    _paper("LLM Candidate Only", "keyword hit but not confirmed", datetime(2026, 2, 1),
           candidate=True, topics=("llm4se_general",), year=2025, authors=("Eve",))
    db.commit()
    db.close()

    monkeypatch.setattr("app.db.SessionLocal", session)
    monkeypatch.setattr("app.main.create_scheduler", lambda: _DummyScheduler())
    with TestClient(app) as c:
        yield c


# ---- 列表 ----

def test_list_papers_default_newest(client):
    r = client.get("/api/papers")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 4
    assert len(body["items"]) == 4
    assert body["page"] == 1 and body["page_size"] == 20
    assert body["items"][0]["title"] == "Unrelated Compiler Paper"  # 2026-05-01 最新


def test_list_papers_pagination(client):
    r = client.get("/api/papers", params={"page": 2, "page_size": 2})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 4 and len(body["items"]) == 2
    assert body["page"] == 2 and body["page_size"] == 2


def test_list_papers_search_q(client):
    r = client.get("/api/papers", params={"q": "repair"})
    assert r.json()["total"] == 1  # 标题命中
    r = client.get("/api/papers", params={"q": "survey"})
    assert r.json()["total"] == 1  # 摘要命中


def test_list_papers_filter_topic(client):
    r = client.get("/api/papers", params={"topic": "code_repair"})
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["topics"][0]["slug"] == "code_repair"
    # 多标签主题不重复计数
    assert client.get("/api/papers", params={"topic": "llm4se_general"}).json()["total"] == 2


def test_list_papers_filter_venue_and_year(client):
    assert client.get("/api/papers", params={"venue": "ICSE"}).json()["total"] == 1
    assert client.get("/api/papers", params={"year": 2025}).json()["total"] == 1
    assert client.get("/api/papers", params={"venue": "FSE"}).json()["total"] == 1


def test_list_papers_filter_ai4se(client):
    r = client.get("/api/papers", params={"is_ai4se": True})
    assert r.json()["total"] == 2  # 2 篇确认 AI4SE


def test_list_papers_sort_venue(client):
    r = client.get("/api/papers", params={"sort": "venue"})
    items = r.json()["items"]
    # 会议版优先：两篇 venue 论文（同 2026 年按 id 倒序 → FSE id=2 在前），其后才是非 venue
    assert [i["venue"]["short_name"] for i in items[:2]] == ["FSE", "ICSE"]
    assert items[0]["dblp_url"] is not None  # 双链接
    assert items[0]["arxiv_url"].startswith("https://arxiv.org/")
    assert items[2]["venue"] is None


def test_list_papers_invalid_params(client):
    assert client.get("/api/papers", params={"sort": "bogus"}).status_code == 422
    assert client.get("/api/papers", params={"page_size": 1000}).status_code == 422


# ---- 详情 ----

def test_get_paper_detail(client):
    r = client.get("/api/papers/1")
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Bug Fixing with LLM"
    # M12：详情作者为带机构的对象（列表仍是 string[]）
    assert body["authors"] == [
        {"name": "Alice", "affiliation": "university of copenhagen"},
        {"name": "Bob", "affiliation": "university of copenhagen"},
    ]
    assert body["summary_zh"] is None
    assert body["venue"]["short_name"] == "ICSE"
    assert body["topics"][0]["slug"] == "code_repair"
    assert body["is_ai4se_confirmed"] is True
    assert body["status"] == "classified"


def test_get_paper_404(client):
    assert client.get("/api/papers/999").status_code == 404


# ---- 主题 / 会议计数 ----

def test_list_topics_with_counts(client):
    r = client.get("/api/topics")
    assert r.status_code == 200
    counts = {t["slug"]: t["paper_count"] for t in r.json()}
    assert counts["code_repair"] == 1
    assert counts["testing"] == 1
    assert counts["llm4se_general"] == 2


def test_list_venues_with_counts(client):
    r = client.get("/api/venues")
    counts = {v["short_name"]: v["paper_count"] for v in r.json()}
    assert counts == {"FSE": 1, "ICSE": 1}


# ---- 趋势 ----

def test_trends_by_topic_daily(client):
    r = client.get("/api/stats/trends", params={"group_by": "topic"})
    assert r.status_code == 200
    body = r.json()
    # 2026-02-01 ~ 2026-05-01 连续日期（缺省日补 0）
    assert body["labels"][0] == "2026-02-01"
    assert body["labels"][-1] == "2026-05-01"
    assert len(body["labels"]) == 90
    by_key = {s["key"]: s for s in body["series"]}
    assert by_key["code_repair"]["values"][body["labels"].index("2026-03-01")] == 1
    assert by_key["code_repair"]["values"][body["labels"].index("2026-04-01")] == 0  # 缺省日补 0
    assert sum(by_key["llm4se_general"]["values"]) == 2


def test_trends_by_topic_date_range(client):
    r = client.get("/api/stats/trends",
                   params={"group_by": "topic", "start": "2026-04-01", "end": "2026-04-30"})
    body = r.json()
    assert body["labels"][0] == "2026-04-01" and body["labels"][-1] == "2026-04-30"
    assert len(body["labels"]) == 30
    assert body["start"] == "2026-04-01" and body["end"] == "2026-04-30"


def test_trends_by_venue(client):
    r = client.get("/api/stats/trends", params={"group_by": "venue"})
    body = r.json()
    keys = {s["key"] for s in body["series"]}
    assert keys == {"FSE", "ICSE"}
    icse = next(s for s in body["series"] if s["key"] == "ICSE")
    assert sum(icse["values"]) == 1


def test_trends_by_year(client):
    r = client.get("/api/stats/trends", params={"group_by": "year"})
    body = r.json()
    assert body["labels"] == ["2025", "2026"]
    assert body["series"][0]["key"] == "all"
    assert body["series"][0]["values"] == [1, 3]


def test_trends_invalid_params(client):
    assert client.get("/api/stats/trends", params={"group_by": "bogus"}).status_code == 422
    assert client.get("/api/stats/trends", params={"start": "not-a-date"}).status_code == 400
    assert client.get("/api/stats/trends",
                      params={"start": "2026-05-01", "end": "2026-04-01"}).status_code == 400


# ---- 作者/机构榜分页（M13） ----


def test_stats_authors_pagination(client):
    r = client.get("/api/stats/authors", params={"page": 1, "page_size": 2})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"items", "total", "page", "page_size"}
    assert body["total"] == 5  # Alice/Bob/Carol/Dave/Eve 各 1 篇
    assert body["page"] == 1 and body["page_size"] == 2
    assert len(body["items"]) == 2
    # 论文数相同按 Author.id 升序 → 前两位 Alice, Bob
    assert [i["name"] for i in body["items"]] == ["Alice", "Bob"]


def test_stats_authors_invalid_params(client):
    assert client.get("/api/stats/authors", params={"page_size": 1000}).status_code == 422
    assert client.get("/api/stats/authors", params={"page": 0}).status_code == 422


def test_stats_authors_search(client):
    r = client.get("/api/stats/authors", params={"q": "ali"})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "Alice"
    # 无匹配 → 空列表，total=0
    assert client.get("/api/stats/authors", params={"q": "zzz"}).json()["total"] == 0
    # 搜索 + 分页组合
    r2 = client.get("/api/stats/authors", params={"q": "ali", "page_size": 100})
    assert r2.json()["total"] == 1 and len(r2.json()["items"]) == 1


def test_stats_institutions_pagination(client):
    r = client.get("/api/stats/institutions", params={"page": 1, "page_size": 1})
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"items", "total", "page", "page_size"}
    assert body["total"] == 2  # copenhagen + kth（去重后）
    assert len(body["items"]) == 1
    # 论文数相同按机构名升序 → 第一页是 kth
    assert body["items"][0]["name"] == "kth royal institute of technology"


def test_stats_institutions_search(client):
    r = client.get("/api/stats/institutions", params={"q": "copenhagen"})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["name"] == "university of copenhagen"
    # 无匹配 → 空列表，total=0
    assert client.get("/api/stats/institutions", params={"q": "zzz"}).json()["total"] == 0
