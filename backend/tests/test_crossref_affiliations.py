"""M12 机构功能测试：Crossref 回填脚本（离线 stub）+ 别名改写脚本。

离线：注入 _StubClient 代替真实网络；SessionLocal monkeypatch 为内存库工厂。
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Author, Base, InstitutionAlias, Paper, PaperAuthor
from scripts.canonicalize_affiliations import canonicalize_affiliations
from scripts.run_backfill_affiliations_crossref import run_crossref_affiliations


@pytest.fixture()
def Session(monkeypatch):
    """内存库会话工厂；脚本内部 SessionLocal() 每次开新会话、用完自关。

    注意：脚本在模块顶部 `from app.db import SessionLocal` 已绑定真实名，
    需同时改脚本模块级名（app.db 上的改动不会传播到已导入绑定）。
    """
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    monkeypatch.setattr("app.db.SessionLocal", Session)
    monkeypatch.setattr("scripts.run_backfill_affiliations_crossref.SessionLocal", Session)
    monkeypatch.setattr("scripts.canonicalize_affiliations.SessionLocal", Session)
    yield Session


def _seed_paper(db, doi="10.1145/123", authors=("Alice Zhang", "Bob Li"), affiliations=None):
    p = Paper(title="LLM Bug Repair", title_normalized="llm bug repair", year=2025,
              doi=doi, status="classified")
    db.add(p)
    db.flush()
    for i, name in enumerate(authors):
        a = Author(name=name, name_normalized=name.lower())
        db.add(a)
        db.flush()
        db.add(PaperAuthor(
            paper_id=p.id, author_id=a.id, position=i,
            affiliation=affiliations[i] if affiliations and i < len(affiliations) else None,
        ))
    return p


class _StubClient:
    """注入的 Crossref 客户端：按 DOI 返回预设作者列表。"""

    def __init__(self, by_doi: dict[str, list[dict] | None]):
        self.by_doi = by_doi
        self.calls: list[str] = []

    def lookup_authors(self, doi: str):
        self.calls.append(doi)
        return self.by_doi.get(doi)

    def close(self):
        pass


def test_crossref_backfill_writes_affiliations(Session):
    db = Session()
    _seed_paper(db)
    db.commit()
    db.close()
    client = _StubClient({
        "10.1145/123": [
            {"name": "Alice Zhang", "affiliations": ["Pennsylvania State University"]},
            {"name": "Bob Li", "affiliations": ["MIT"]},
        ],
    })

    stats = run_crossref_affiliations(client=client)

    assert stats["processed"] == 1
    assert stats["with_affiliation"] == 1
    assert client.calls == ["10.1145/123"]
    check = Session()
    links = sorted(check.query(PaperAuthor).all(), key=lambda l: l.position)
    assert links[0].affiliation == "pennsylvania state university"
    assert links[1].affiliation == "mit"
    check.close()


def test_crossref_backfill_order_independent(Session):
    """Crossref 作者顺序与本库不同：P1 精确名匹配，各归各位。"""
    db = Session()
    _seed_paper(db)
    db.commit()
    db.close()
    client = _StubClient({
        "10.1145/123": [
            {"name": "Bob Li", "affiliations": ["MIT"]},  # 反序
            {"name": "Alice Zhang", "affiliations": ["Penn State"]},
        ],
    })

    run_crossref_affiliations(client=client)

    check = Session()
    links = sorted(check.query(PaperAuthor).all(), key=lambda l: l.position)
    assert links[0].affiliation == "penn state"  # Alice 在位置 0
    assert links[1].affiliation == "mit"         # Bob 在位置 1
    check.close()


def test_crossref_backfill_applies_alias(Session):
    db = Session()
    db.add(InstitutionAlias(alias="the university of warwick", canonical="university of warwick"))
    db.commit()
    _seed_paper(db, doi="10.1145/456", authors=("Carol Wu",))
    db.commit()
    db.close()
    client = _StubClient({
        "10.1145/456": [{"name": "Carol Wu", "affiliations": ["The University of Warwick"]}],
    })

    run_crossref_affiliations(client=client)

    check = Session()
    link = check.query(PaperAuthor).first()
    assert link.affiliation == "university of warwick"
    check.close()


def test_crossref_backfill_no_authors_skipped(Session):
    db = Session()
    _seed_paper(db, doi="10.1145/789", authors=("Dave",))
    db.commit()
    db.close()
    client = _StubClient({"10.1145/789": None})

    stats = run_crossref_affiliations(client=client)

    assert stats["no_crossref"] == 1
    assert stats["with_affiliation"] == 0
    check = Session()
    assert check.query(PaperAuthor).first().affiliation is None
    check.close()


def test_canonicalize_affiliations_rewrites(Session):
    db = Session()
    db.add_all([
        InstitutionAlias(alias="the university of warwick", canonical="university of warwick"),
        InstitutionAlias(alias="lre", canonical="lre, epita"),
    ])
    db.commit()
    _seed_paper(db, doi="10.1145/100", authors=("Eve",), affiliations=("the university of warwick",))
    db.commit()
    db.close()

    stats = canonicalize_affiliations()

    assert stats == {"scanned": 1, "changed": 1}
    check = Session()
    assert check.query(PaperAuthor).first().affiliation == "university of warwick"
    check.close()


def test_canonicalize_affiliations_noop(Session):
    db = Session()
    _seed_paper(db, doi="10.1145/101", authors=("Frank",),
                affiliations=("university of edinburgh",))  # 无别名
    db.commit()
    db.close()

    stats = canonicalize_affiliations()

    assert stats == {"scanned": 1, "changed": 0}
