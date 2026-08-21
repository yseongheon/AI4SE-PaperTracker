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

    items, total = stats_service.authors_top(db, page=1, page_size=10)
    result = {"authors": items}

    by_name = {a["name"]: a for a in result["authors"]}
    assert by_name["Alice Zhang"]["paper_count"] == 2
    assert by_name["Alice Zhang"]["ai4se_count"] == 2
    assert by_name["Bob Li"]["paper_count"] == 2
    assert by_name["Bob Li"]["ai4se_count"] == 1  # P3 非 AI4SE
    assert result["authors"][0]["name"] == "Alice Zhang"  # 论文数降序
    assert total == 2


def test_authors_top_topics(db):
    add_paper(db, "P1", "a", topics=("code_repair", "testing"), authors=("Alice Zhang",))
    add_paper(db, "P2", "b", topics=("code_repair",), authors=("Alice Zhang",))
    db.commit()

    items, total = stats_service.authors_top(db, page=1, page_size=10)
    result = {"authors": items}

    alice = result["authors"][0]
    assert alice["top_topics"][0]["slug"] == "code_repair"  # 频次最高的主题在前
    assert len(alice["top_topics"]) == 2
    assert total == 1


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

    items, total = stats_service.authors_top(db, page=1, page_size=10)
    result = {"authors": items}

    assert result["authors"][0]["affiliation"] == "sun yat-sen university"
    assert total == 1


def test_authors_top_skips_junk_affiliation(db):
    # arXiv 机构自由文本常把作者名填进机构栏（如 "peter"），作者榜不应展示
    add_paper(db, "P1", "a", authors=("Alice Zhang",), affiliations=("peter",))
    db.commit()

    items, total = stats_service.authors_top(db, page=1, page_size=10)
    result = {"authors": items}

    assert result["authors"][0]["affiliation"] is None
    assert total == 1


def test_institutions_top_distinct_papers(db):
    # 同一论文两个作者来自同一机构 → paper_count 只算 1 篇（COUNT DISTINCT）
    add_paper(db, "P1", "a", authors=("Alice Zhang", "Bob Li"),
              affiliations=("university of copenhagen", "university of copenhagen"))
    db.commit()

    items, total = stats_service.institutions_top(db, page=1, page_size=10)
    result = {"institutions": items}

    insts = {i["name"]: i for i in result["institutions"]}
    assert insts["university of copenhagen"]["paper_count"] == 1
    assert total == 1


def test_institutions_top_filters_junk_and_counts_ai4se(db):
    add_paper(db, "P1", "a", authors=("Alice Zhang",), affiliations=("peter",))
    add_paper(db, "P2", "b", authors=("Bob Li",), affiliations=("university of copenhagen",),
              confirmed=False)
    db.commit()

    items, total = stats_service.institutions_top(db, page=1, page_size=10)
    result = {"institutions": items}

    names = {i["name"] for i in result["institutions"]}
    assert "peter" not in names  # 垃圾项过滤
    copenhagen = [i for i in result["institutions"] if i["name"] == "university of copenhagen"][0]
    assert copenhagen["paper_count"] == 1
    assert copenhagen["ai4se_count"] == 0  # P2 非 AI4SE
    assert total == 1  # "peter" 垃圾机构不计入 total


# ---- 作者/机构榜分页（M13） ----


def test_authors_top_pagination(db):
    for i in range(5):
        add_paper(db, f"P{i}", "a", authors=(f"Author{i}",))
    db.commit()

    page1, total = stats_service.authors_top(db, page=1, page_size=2)
    assert total == 5
    assert [a["name"] for a in page1] == ["Author0", "Author1"]  # 论文数相同按 Author.id 升序
    page2, _ = stats_service.authors_top(db, page=2, page_size=2)
    assert [a["name"] for a in page2] == ["Author2", "Author3"]
    page3, _ = stats_service.authors_top(db, page=3, page_size=2)
    assert [a["name"] for a in page3] == ["Author4"]
    page4, _ = stats_service.authors_top(db, page=4, page_size=2)
    assert page4 == []


def test_authors_top_page_beyond_end(db):
    add_paper(db, "P1", "a", authors=("Alice Zhang",))
    db.commit()

    items, total = stats_service.authors_top(db, page=999, page_size=10)
    assert items == []
    assert total == 1


def test_authors_top_search_q(db):
    add_paper(db, "P1", "a", authors=("Alice Zhang",))
    add_paper(db, "P2", "b", authors=("Bob Li",))
    add_paper(db, "P3", "c", authors=("Carol Wu",))
    db.commit()

    items, total = stats_service.authors_top(db, page=1, page_size=10, q="alice")
    assert total == 1
    assert items[0]["name"] == "Alice Zhang"
    # 不区分大小写 + 部分匹配
    items, total = stats_service.authors_top(db, q="ZHANG")
    assert total == 1 and items[0]["name"] == "Alice Zhang"
    # 无匹配
    items, total = stats_service.authors_top(db, q="zzz")
    assert total == 0 and items == []


def test_institutions_top_total_and_pagination(db):
    # 5 个可信机构 + 1 个垃圾（作者名误填）→ total 只算可信数，垃圾不进任何页
    for i in range(5):
        add_paper(db, f"P{i}", "a", authors=(f"Author{i}",),
                  affiliations=(f"university {i}",))
    add_paper(db, "Pjunk", "a", authors=("Junk",), affiliations=("peter",))
    db.commit()

    items, total = stats_service.institutions_top(db, page=1, page_size=2)
    assert total == 5
    assert len(items) == 2
    page3, total3 = stats_service.institutions_top(db, page=3, page_size=2)
    assert len(page3) == 1  # 第 3 页只剩 1 条
    assert total3 == 5
    all_names = []
    for page in range(1, 4):
        page_items, _ = stats_service.institutions_top(db, page=page, page_size=2)
        all_names += [i["name"] for i in page_items]
    assert "peter" not in all_names


def test_institutions_top_search_q(db):
    add_paper(db, "P1", "a", authors=("Alice Zhang",),
              affiliations=("university of copenhagen",))
    add_paper(db, "P2", "b", authors=("Bob Li",),
              affiliations=("kth royal institute of technology",))
    db.commit()

    items, total = stats_service.institutions_top(db, q="copenhagen")
    assert total == 1
    assert items[0]["name"] == "university of copenhagen"
    # 大小写不敏感
    items, total = stats_service.institutions_top(db, q="KTH")
    assert total == 1 and items[0]["name"] == "kth royal institute of technology"
    # 无匹配
    items, total = stats_service.institutions_top(db, q="zzz")
    assert total == 0 and items == []


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
