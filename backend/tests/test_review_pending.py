"""M5 复核脚本测试：accept/reject 逻辑（离线，内存 SQLite，不触真实数据）。"""
import pytest
from sqlalchemy import create_engine, exc as sa_exc
from sqlalchemy.orm import sessionmaker

from app.models import Base, MatchStatus, Paper, Venue
from scripts.review_pending import accept_candidate, list_pending, reject_paper


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def make_pending(db, title="Ambiguous Paper", candidates=None) -> Paper:
    paper = Paper(
        title=title,
        title_normalized=title.lower(),
        year=2026,
        match_status=MatchStatus.PENDING.value,
        status="fetched",
        match_candidates=candidates
        or [
            {"key": "conf/icse/a", "venue_short_name": "ICSE", "year": 2026, "doi": "10.1/1"},
            {"key": "conf/fse/b", "venue_short_name": "FSE", "year": 2026, "doi": None},
        ],
    )
    db.add(paper)
    db.flush()
    return paper


def test_accept_by_index_backfills(db):
    db.add(Venue(short_name="ICSE", full_name="ICSE", rank="A", dblp_key="conf/icse"))
    db.add(Venue(short_name="FSE", full_name="FSE", rank="A", dblp_key="conf/fse"))
    db.commit()
    paper = make_pending(db)

    accept_candidate(db, paper.id, index=2)

    assert paper.match_status == MatchStatus.MATCHED.value
    assert paper.dblp_key == "conf/fse/b"
    assert paper.doi is None
    assert paper.venue is not None and paper.venue.short_name == "FSE"
    assert paper.year == 2026
    assert paper.status == "matched"  # fetched → matched
    assert paper.match_candidates is None


def test_accept_by_key_resolves_venue_by_prefix(db):
    db.add(Venue(short_name="ICSE", full_name="ICSE", rank="A", dblp_key="conf/icse"))
    db.commit()
    paper = make_pending(db)

    accept_candidate(db, paper.id, key="conf/icse/2026/xyz")

    assert paper.match_status == MatchStatus.MATCHED.value
    assert paper.dblp_key == "conf/icse/2026/xyz"
    assert paper.venue.short_name == "ICSE"


def test_accept_by_key_unknown_venue(db):
    """key 前缀不在 venues 表时 venue 留空，但回填照常（展示为无 venue 论文）。"""
    paper = make_pending(db)
    accept_candidate(db, paper.id, key="conf/unknown/2026/x")
    assert paper.match_status == MatchStatus.MATCHED.value
    assert paper.venue is None


def test_accept_requires_exactly_one_of_idx_key(db):
    paper = make_pending(db)
    with pytest.raises(ValueError):
        accept_candidate(db, paper.id)
    with pytest.raises(ValueError):
        accept_candidate(db, paper.id, index=1, key="conf/icse/x")


def test_accept_index_out_of_range(db):
    paper = make_pending(db)
    with pytest.raises(ValueError):
        accept_candidate(db, paper.id, index=3)


def test_accept_invalid_key(db):
    paper = make_pending(db)
    with pytest.raises(ValueError):
        accept_candidate(db, paper.id, key="not-a-key")


def test_accept_non_pending_raises(db):
    paper = Paper(title="t", title_normalized="t", match_status="none")
    db.add(paper)
    db.flush()
    with pytest.raises(ValueError):
        accept_candidate(db, paper.id, index=1)


def test_accept_duplicate_key_raises(db):
    paper = make_pending(db)
    other = Paper(title="other", title_normalized="other", match_status="none",
                  dblp_key="conf/icse/a")
    db.add(other)
    db.commit()
    with pytest.raises(sa_exc.IntegrityError):
        accept_candidate(db, paper.id, index=1)  # conf/icse/a 已被占用


def test_reject(db):
    paper = make_pending(db)
    reject_paper(db, paper.id)
    assert paper.match_status == MatchStatus.REJECTED.value
    assert list_pending(db) == []


def test_list_pending_only_pending(db):
    make_pending(db)
    other = Paper(title="none", title_normalized="none", match_status="none")
    db.add(other)
    db.commit()
    assert len(list_pending(db)) == 1
