"""标题/作者/机构归一化测试：跨源匹配键的正确性。"""
from app.crawler.normalize import (
    apply_institution_alias,
    author_last_name,
    normalize_author,
    normalize_institution,
    normalize_title,
)


def test_basic_lowercase_and_ws():
    assert normalize_title("An Empirical Study of Code Repair") == "an empirical study of code repair"
    assert normalize_title("  Multi-line\nTitle  ") == "multi line title"


def test_latex_commands_stripped():
    # \emph{...}：命令与花括号都要去掉，内容保留
    assert normalize_title(r"Repairing Bugs with \emph{LLM} Agents") == "repairing bugs with llm agents"
    assert normalize_title(r"{\it Deep} Learning") == "deep learning"


def test_math_and_punct_stripped():
    assert normalize_title(r"Verifying $K$-Step Properties") == "verifying k step properties"
    assert normalize_title("Code, Repairs & Bugs: A Survey!") == "code repairs bugs a survey"
    assert normalize_title("What's New in LLM-based Testing?") == "whats new in llm based testing"


def test_empty_input():
    assert normalize_title("") == ""
    assert normalize_title(None) == ""
    assert normalize_author(None) == ""


def test_arxiv_vs_dblp_same_paper():
    # arXiv 标题带 LaTeX 排版，DBLP 标题已排版：归一化后应一致
    arxiv_title = r"Towards Robust \emph{LLM}-based Program Repair at Scale"
    dblp_title = "Towards Robust LLM-based Program Repair at Scale"
    assert normalize_title(arxiv_title) == normalize_title(dblp_title)


def test_normalize_author():
    assert normalize_author("Xiaoyu, Wang.") == "xiaoyu wang"
    assert normalize_author("WANG Xiaoyu") == "wang xiaoyu"
    assert normalize_author("  A.  Zhang  ") == "a zhang"


def test_author_last_name():
    assert author_last_name("Xiaoyu Wang") == "wang"
    assert author_last_name("Alice B. Zhang") == "zhang"
    assert author_last_name("") == ""


def test_author_last_name_dblp_disambiguation_suffix():
    # DBLP 同名作者带消歧数字后缀（如 "Seongmin Lee 0001"）：姓氏应取 "lee" 而非 "0001"
    assert author_last_name("Seongmin Lee 0001") == "lee"
    assert author_last_name("Miao Miao 0001") == "miao"
    assert author_last_name("Bob Li 0002") == "li"


# ---- 机构归一化（机构榜/作者机构） ----


def test_normalize_institution_expands_abbrev():
    assert normalize_institution("Tsinghua Univ.") == "tsinghua university"
    assert normalize_institution("TU Wien Inst.") == "tu wien institute"
    assert normalize_institution("Software & Systems Engineering") == "software and systems engineering"
    assert normalize_institution("Dept. of CS") == "department of cs"


def test_normalize_institution_strips_punct_and_ws():
    assert normalize_institution("  Zhejiang Univ., China; ") == "zhejiang university, china"
    assert normalize_institution("X Univ.\n\tY") == "x university y"


def test_normalize_institution_empty_is_none():
    assert normalize_institution("") is None
    assert normalize_institution("   ") is None
    assert normalize_institution(None) is None


# ---- 机构别名合并 ----

_ALIAS = {"the university of warwick": "university of warwick"}


def test_apply_institution_alias_hit():
    assert apply_institution_alias("the university of warwick", _ALIAS) == "university of warwick"


def test_apply_institution_alias_miss_unchanged():
    assert apply_institution_alias("university of edinburgh", _ALIAS) == "university of edinburgh"


def test_apply_institution_alias_empty_or_none_map():
    assert apply_institution_alias("university of warwick", {}) == "university of warwick"
    assert apply_institution_alias("university of warwick", None) == "university of warwick"


def test_apply_institution_alias_none_or_empty_input():
    assert apply_institution_alias(None, _ALIAS) is None
    assert apply_institution_alias("", _ALIAS) == ""
