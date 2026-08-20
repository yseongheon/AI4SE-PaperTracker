"""M7 分析端点测试：词云/作者榜/交叉矩阵/合作网络（离线，内存 SQLite）。"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Author, Base, Paper, PaperAuthor, PaperTopic, Topic, Venue
from app.services import institution_service, stats_service


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def add_paper(db, title, abstract, *, topics=(), venue=None, confirmed=True, year=2026,
              authors=(), affiliations=()):
    p = Paper(
        title=title, title_normalized=title.lower(), abstract=abstract,
        year=year, is_ai4se_confirmed=confirmed, venue=venue, status="classified",
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
    for i, name in enumerate(authors):
        a = db.query(Author).filter_by(name_normalized=name.lower()).first()
        if a is None:
            a = Author(name=name, name_normalized=name.lower())
            db.add(a)
            db.flush()
        db.add(PaperAuthor(
            paper_id=p.id, author_id=a.id, position=i,
            affiliation=affiliations[i] if affiliations and i < len(affiliations) else None,
        ))
    return p


# ---- 词云 ----


def test_words_filters_stopwords_and_short(db):
    add_paper(db, "A", "The LLM framework for software testing and repair of code bugs")
    add_paper(db, "B", "We study the abstract analysis", confirmed=False)  # 非 AI4SE 不进默认 scope
    db.commit()

    result = stats_service.words(db, limit=50, scope="ai4se")

    words = {w["word"] for w in result["words"]}
    assert "llm" in words
    assert "testing" in words and "repair" in words
    assert "the" not in words  # 停用词过滤
    assert "of" not in words
    assert "we" not in words
    assert "study" not in words  # 停用词
    assert "analysis" not in words  # 非 AI4SE 论文的摘要不参与


def test_words_scope_all(db):
    add_paper(db, "A", "LLM for testing", confirmed=True)
    add_paper(db, "B", "LLM for analysis", confirmed=False)
    db.commit()

    assert stats_service.words(db, scope="all")["words"][0]["word"] == "llm"
    all_words = {w["word"] for w in stats_service.words(db, scope="all")["words"]}
    assert "analysis" in all_words


# ---- 作者榜 ----


def test_authors_top_aggregates(db):
    add_paper(db, "P1", "a", authors=("Alice Zhang", "Bob Li"))
    add_paper(db, "P2", "b", authors=("Alice Zhang",))
    add_paper(db, "P3", "c", authors=("Bob Li",), confirmed=False)
    db.commit()

    result = stats_service.authors_top(db, limit=10)

    by_name = {a["name"]: a for a in result["authors"]}
    assert by_name["Alice Zhang"]["paper_count"] == 2
    assert by_name["Alice Zhang"]["ai4se_count"] == 2
    assert by_name["Bob Li"]["paper_count"] == 2
    assert by_name["Bob Li"]["ai4se_count"] == 1  # P3 非 AI4SE
    assert result["authors"][0]["name"] == "Alice Zhang"  # 论文数降序


def test_authors_top_topics(db):
    add_paper(db, "P1", "a", topics=("code_repair", "testing"), authors=("Alice Zhang",))
    add_paper(db, "P2", "b", topics=("code_repair",), authors=("Alice Zhang",))
    db.commit()

    result = stats_service.authors_top(db, limit=10)

    alice = result["authors"][0]
    assert alice["top_topics"][0]["slug"] == "code_repair"  # 频次最高的主题在前
    assert len(alice["top_topics"]) == 2


# ---- 会议×主题矩阵 ----


def test_cross_matrix_shape(db):
    icse = Venue(short_name="ICSE", full_name="ICSE", type="conference", rank="A")
    fse = Venue(short_name="FSE", full_name="FSE", type="conference", rank="A")
    db.add_all([icse, fse])
    db.commit()
    add_paper(db, "P1", "a", topics=("code_repair",), venue=icse)
    add_paper(db, "P2", "b", topics=("testing",), venue=icse)
    add_paper(db, "P3", "c", topics=("code_repair",), venue=fse)
    db.commit()

    result = stats_service.cross(db)

    assert result["venues"] == ["FSE", "ICSE"]
    assert set(result["topics"]) == {"code_repair", "testing"}
    matrix = dict(zip(result["venues"], result["matrix"]))
    assert matrix["ICSE"][result["topics"].index("code_repair")] == 1
    assert matrix["ICSE"][result["topics"].index("testing")] == 1
    assert matrix["FSE"][result["topics"].index("code_repair")] == 1


# ---- 合作网络 ----


def test_coauthor_links_weight(db):
    add_paper(db, "P1", "a", authors=("A", "B"))
    add_paper(db, "P2", "b", authors=("A", "B"))
    add_paper(db, "P3", "c", authors=("A", "C"))
    add_paper(db, "P4", "d", authors=("D", "E", "F"))
    db.commit()

    result = stats_service.coauthor(db, limit=100)

    nodes = {n["name"]: n for n in result["nodes"]}
    assert nodes["A"]["paper_count"] == 3
    weights = {(l["source"], l["target"]): l["weight"] for l in result["links"]}
    # A-B 共著 2 篇；A-C 共著 1 篇；D/E/F 无共著（不同论文）→ 无边
    ab = max(w for (a, b), w in weights.items() if (a, b) in ((1, 2), (2, 1)))
    assert ab == 2
    assert len(result["links"]) >= 2  # A-B、A-C


def test_coauthor_limit_trims_nodes(db):
    for i in range(5):
        add_paper(db, f"P{i}", "a", authors=(f"Author{i}",))
    db.commit()

    result = stats_service.coauthor(db, limit=3)

    assert len(result["nodes"]) == 3


# ---- 机构榜 + 作者机构 ----


def test_authors_top_affiliation(db):
    add_paper(db, "P1", "a", authors=("Alice Zhang",), affiliations=("sun yat-sen university",))
    db.commit()

    result = stats_service.authors_top(db, limit=10)

    assert result["authors"][0]["affiliation"] == "sun yat-sen university"


def test_authors_top_skips_junk_affiliation(db):
    # arXiv 机构自由文本常把作者名填进机构栏（如 "peter"），作者榜不应展示
    add_paper(db, "P1", "a", authors=("Alice Zhang",), affiliations=("peter",))
    db.commit()

    result = stats_service.authors_top(db, limit=10)

    assert result["authors"][0]["affiliation"] is None


def test_institutions_top_distinct_papers(db):
    # 同一论文两个作者来自同一机构 → paper_count 只算 1 篇（COUNT DISTINCT）
    add_paper(db, "P1", "a", authors=("Alice Zhang", "Bob Li"),
              affiliations=("university of copenhagen", "university of copenhagen"))
    db.commit()

    result = stats_service.institutions_top(db, limit=10)

    insts = {i["name"]: i for i in result["institutions"]}
    assert insts["university of copenhagen"]["paper_count"] == 1


def test_institutions_top_filters_junk_and_counts_ai4se(db):
    add_paper(db, "P1", "a", authors=("Alice Zhang",), affiliations=("peter",))
    add_paper(db, "P2", "b", authors=("Bob Li",), affiliations=("university of copenhagen",),
              confirmed=False)
    db.commit()

    result = stats_service.institutions_top(db, limit=10)

    names = {i["name"] for i in result["institutions"]}
    assert "peter" not in names  # 垃圾项过滤
    copenhagen = [i for i in result["institutions"] if i["name"] == "university of copenhagen"][0]
    assert copenhagen["paper_count"] == 1
    assert copenhagen["ai4se_count"] == 0  # P2 非 AI4SE


# ---- 机构详情（M12） ----


def test_institution_detail_counts_topics_coinst(db):
    add_paper(db, "P1", "a", topics=("code_repair",), authors=("Alice Zhang", "Bob Li"),
              affiliations=("university of copenhagen", "university of copenhagen"))
    add_paper(db, "P2", "b", topics=("testing",), authors=("Alice Zhang", "Carol Wu"),
              affiliations=("university of copenhagen", "kth royal institute of technology"),
              confirmed=False)
    db.commit()

    result = institution_service.institution_detail(db, "university of copenhagen")

    assert result["paper_count"] == 2  # P1、P2 各算 1 篇（DISTINCT）
    assert result["ai4se_count"] == 1  # P2 非 AI4SE
    slugs = {t["slug"]: t["count"] for t in result["topics"]}
    assert slugs == {"code_repair": 1, "testing": 1}
    co = {c["name"]: c["count"] for c in result["co_institutions"]}
    assert co["kth royal institute of technology"] == 1


def test_institution_detail_coinst_distinct(db):
    # 同一论文两个作者来自同一合作机构 → 只算 1 篇
    add_paper(db, "P1", "a", authors=("A", "B", "C"),
              affiliations=("university of copenhagen", "mit", "mit"))
    db.commit()

    result = institution_service.institution_detail(db, "university of copenhagen")

    co = {c["name"]: c["count"] for c in result["co_institutions"]}
    assert co["mit"] == 1


def test_institution_detail_filters_junk_coinst(db):
    add_paper(db, "P1", "a", authors=("A", "B"),
              affiliations=("university of copenhagen", "peter"))
    db.commit()

    result = institution_service.institution_detail(db, "university of copenhagen")

    names = {c["name"] for c in result["co_institutions"]}
    assert "peter" not in names


def test_institution_detail_unknown_returns_zeros(db):
    result = institution_service.institution_detail(db, "nonexistent institution")

    assert result["paper_count"] == 0
    assert result["ai4se_count"] == 0
    assert result["topics"] == []
    assert result["co_institutions"] == []
