"""DBLP 匹配器测试：预印本↔正式版关联的正确性与歧义处理（离线，内存 SQLite）。"""
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.crawler.dblp_client import DblpClient, DblpHit
from app.crawler.matcher import match_papers
from app.crawler.normalize import normalize_author, normalize_title
from app.models import Author, Base, MatchStatus, Paper, PaperAuthor, Venue

FIXTURE_DBLP = Path(__file__).parent / "fixtures" / "dblp_page.json"


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def make_venue(db, short="ICSE", dblp_key="conf/icse") -> Venue:
    venue = Venue(
        short_name=short, full_name=short, type="conference", rank="A", dblp_key=dblp_key
    )
    db.add(venue)
    db.flush()
    return venue


def make_paper(
    db,
    title: str,
    year: int = 2026,
    first_author: str = "Xiaoyu Wang",
    match_status: str = "none",
) -> Paper:
    paper = Paper(
        title=title,
        title_normalized=normalize_title(title),
        year=year,
        match_status=match_status,
        status="fetched",
    )
    db.add(paper)
    db.flush()
    norm = normalize_author(first_author)
    author = db.query(Author).filter_by(name_normalized=norm).first()
    if author is None:
        author = Author(name=first_author, name_normalized=norm)
        db.add(author)
        db.flush()
    db.add(PaperAuthor(paper_id=paper.id, author_id=author.id, position=0))
    db.flush()
    return paper


def make_hit(
    title: str,
    year: int = 2026,
    venue: str = "ICSE",
    authors: tuple[str, ...] = ("Xiaoyu Wang",),
    key: str = "conf/icse/xyz",
    doi: str | None = "10.1145/1",
) -> DblpHit:
    return DblpHit(
        key=key,
        title=title,
        title_normalized=normalize_title(title),
        authors=list(authors),
        year=year,
        venue_short_name=venue,
        doi=doi,
        url=None,
    )


def venues_map(db) -> dict[str, Venue]:
    return {v.short_name: v for v in db.query(Venue).all()}


# ---------- 匹配器 ----------


def test_single_hit_matches_and_backfills(db):
    make_venue(db)
    paper = make_paper(db, "Repairing Bugs with LLM Agents")
    hit = make_hit("Repairing Bugs with LLM Agents")

    stats = match_papers(db, [paper], [hit], venues_map(db))

    assert stats.matched == 1 and stats.pending == 0
    assert paper.match_status == MatchStatus.MATCHED.value
    assert paper.dblp_key == "conf/icse/xyz"
    assert paper.doi == "10.1145/1"
    assert paper.venue is not None and paper.venue.short_name == "ICSE"
    assert paper.year == 2026
    assert paper.status == "matched"  # fetched → matched 提升


def test_ambiguous_hits_go_pending(db):
    make_venue(db, "ICSE")
    make_venue(db, "FSE", "conf/fse")
    paper = make_paper(db, "Same Title Both Venues")
    hit_a = make_hit("Same Title Both Venues", venue="ICSE", key="conf/icse/a")
    hit_b = make_hit("Same Title Both Venues", venue="FSE", key="conf/fse/b")

    stats = match_papers(db, [paper], [hit_a, hit_b], venues_map(db))

    assert stats.pending == 1 and stats.matched == 0
    assert paper.match_status == MatchStatus.PENDING.value
    assert paper.dblp_key is None  # 不自动关联


def test_clue_disambiguates_ambiguous(db):
    make_venue(db, "ICSE")
    make_venue(db, "FSE", "conf/fse")
    paper = make_paper(db, "Same Title Both Venues")
    paper.comment = "Accepted at FSE 2026"  # arXiv 线索
    hit_a = make_hit("Same Title Both Venues", venue="ICSE", key="conf/icse/a")
    hit_b = make_hit("Same Title Both Venues", venue="FSE", key="conf/fse/b")

    stats = match_papers(db, [paper], [hit_a, hit_b], venues_map(db))

    assert stats.matched == 1
    assert paper.venue.short_name == "FSE"
    assert paper.dblp_key == "conf/fse/b"


def test_year_outside_window_not_matched(db):
    make_venue(db)
    paper = make_paper(db, "Old Paper", year=2026)
    hit = make_hit("Old Paper", year=2024)  # 差 2 年，超出 ±1 窗口

    stats = match_papers(db, [paper], [hit], venues_map(db))

    assert stats.none == 1
    assert paper.match_status == MatchStatus.NONE.value


def test_author_mismatch_not_matched(db):
    make_venue(db)
    paper = make_paper(db, "Whose Paper", first_author="Xiaoyu Wang")
    hit = make_hit("Whose Paper", authors=("Alice Zhang",))

    stats = match_papers(db, [paper], [hit], venues_map(db))

    assert stats.none == 1
    assert paper.match_status == MatchStatus.NONE.value


def test_already_matched_paper_skipped(db):
    make_venue(db)
    paper = make_paper(db, "Already Done", match_status="matched")
    hit = make_hit("Already Done")

    stats = match_papers(db, [paper], [hit], venues_map(db))

    assert stats.matched == 0 and stats.pending == 0 and stats.none == 0


def test_arxiv_vs_dblp_title_variants_match(db):
    """arXiv 标题带 LaTeX 排版、DBLP 已排版 → 归一化后仍应命中。"""
    make_venue(db)
    paper = make_paper(db, r"Towards Robust \emph{LLM}-based Program Repair at Scale")
    hit = make_hit("Towards Robust LLM-based Program Repair at Scale")

    stats = match_papers(db, [paper], [hit], venues_map(db))

    assert stats.matched == 1


# ---------- DBLP 响应解析 ----------


def test_dblp_parse_hits():
    hits = DblpClient._parse_hits(FIXTURE_DBLP.read_text(encoding="utf-8"), "ICSE")

    assert len(hits) == 2
    h = hits[0]
    assert h.key == "conf/icse/Wang2025Repairing"
    assert h.title_normalized == "repairing bugs with llm agents an empirical study"
    assert h.authors == ["Xiaoyu Wang", "Alice Zhang"]
    assert h.year == 2025
    assert h.doi == "10.1145/1234567"
    assert hits[1].venue_short_name == "ICSE"  # 传入的短名原样标记


def test_dblp_parse_page_returns_total():
    """分页终止依赖 @total：字符串数字也能解析（DBLP 返回 "21840"）。"""
    hits, total = DblpClient._parse_page(FIXTURE_DBLP.read_text(encoding="utf-8"), "ICSE")

    assert total == 21840
    assert len(hits) == 2


def test_dblp_parse_page_total_missing():
    """@total 缺失时返回 None（循环检测兜底生效，不会崩溃）。"""
    hits, total = DblpClient._parse_page("{}", "ICSE")

    assert total is None
    assert hits == []
