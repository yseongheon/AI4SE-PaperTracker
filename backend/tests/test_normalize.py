"""标题/作者归一化测试：跨源匹配键的正确性。"""
from app.crawler.normalize import author_last_name, normalize_author, normalize_title


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
