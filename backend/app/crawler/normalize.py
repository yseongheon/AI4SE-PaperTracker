"""标题/作者归一化：全项目跨源匹配的键（CLAUDE.md 第 5 章关联规则）。

规则：小写 → 去 LaTeX 命令与花括号/美元符 → 去标点 → 压缩空白。
arXiv 标题（含 LaTeX 命令）与 DBLP 标题（已排版）经此归一化后可稳定比对。
"""
import re

_LATEX_CMD = re.compile(r"\\[a-zA-Z]+\s*")  # \emph{、\alpha 等命令（连同尾随空格）
_BRACES_DOLLAR = re.compile(r"[{}$]")
_APOSTROPHE = re.compile(r"['’]")  # 直/弯撇号直接删除（What's 与 Whats 归一一致）
_PUNCT = re.compile(r"[^0-9a-z\s]")  # 标点与特殊字符 → 空格
_WS = re.compile(r"\s+")


def normalize_title(title: str | None) -> str:
    """标题归一化：匹配键 = 小写、去 LaTeX/标点/空白。"""
    if not title:
        return ""
    t = title.lower()
    t = _LATEX_CMD.sub(" ", t)
    t = _BRACES_DOLLAR.sub(" ", t)
    t = _APOSTROPHE.sub("", t)
    t = _PUNCT.sub(" ", t)
    t = _WS.sub(" ", t)
    return t.strip()


def normalize_author(name: str | None) -> str:
    """作者名归一化：小写、去点与标点、压缩空白（v1 不做拼音/缩写处理）。"""
    if not name:
        return ""
    t = name.lower()
    t = re.sub(r"[^0-9a-z\s]", " ", t)
    t = _WS.sub(" ", t)
    return t.strip()


def author_last_name(name: str) -> str:
    """取作者姓氏（末段）：DBLP 匹配时做姓氏粗校验用。

    DBLP 同名作者带消歧数字后缀（如 "Seongmin Lee 0001"），纯数字末段视为后缀跳过。
    """
    t = normalize_author(name)
    parts = [p for p in t.split() if p]
    while parts and parts[-1].isdigit():
        parts.pop()
    return parts[-1] if parts else ""
