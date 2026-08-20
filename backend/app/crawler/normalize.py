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


# 机构常见缩写展开（顺序敏感：每个缩写先匹配"带句点"吞掉句点，再匹配"裸缩写"兜底。
# 不能只用 \buniv\.?\b：后跟逗号/分号时（如 "Univ.,"）句点后无词边界，\b 不成立导致句点残留）
_INSTITUTION_ABBREV = [
    (re.compile(r"\buniv\."), "university"),
    (re.compile(r"\buniv\b"), "university"),
    (re.compile(r"\binst\."), "institute"),
    (re.compile(r"\binst\b"), "institute"),
    (re.compile(r"\bdept\."), "department"),
    (re.compile(r"\bdept\b"), "department"),
    (re.compile(r"\bsch\."), "school"),
    (re.compile(r"\bsch\b"), "school"),
]


def normalize_institution(raw: str | None) -> str | None:
    """机构名归一化：小写、展开常见缩写、折叠空白、去尾标点；空返回 None。

    与 normalize_author 不同——必须保留 '&' 与句点（缩写展开依赖），故单独实现。
    规则化合并（免费，用户拍板）：能合并 "Tsinghua Univ." / "Tsinghua University" 等常见
    变体；不做 "Microsoft" vs "Microsoft Research" 这类语义合并（后续可加规则细化）。
    """
    if not raw:
        return None
    t = raw.lower()
    for pattern, repl in _INSTITUTION_ABBREV:
        t = pattern.sub(repl, t)
    t = t.replace("&", "and")
    t = _WS.sub(" ", t).strip()
    t = t.rstrip(".,;:")
    t = _WS.sub(" ", t).strip()
    return t or None


def apply_institution_alias(norm: str | None, alias_map: dict[str, str] | None = None) -> str | None:
    """机构别名合并：alias_map{归一化机构串: 权威名} 精确映射；无映射原样返回。

    纯函数（不碰 DB）——alias_map 由调用方从 institution_aliases 表加载
    （institution_service.load_institution_alias_map）。写库时在 normalize_institution
    之后套用，使存量与增量都落 canonical。
    """
    if not norm or not alias_map:
        return norm
    return alias_map.get(norm, norm)


def author_last_name(name: str) -> str:
    """取作者姓氏（末段）：DBLP 匹配时做姓氏粗校验用。

    DBLP 同名作者带消歧数字后缀（如 "Seongmin Lee 0001"），纯数字末段视为后缀跳过。
    """
    t = normalize_author(name)
    parts = [p for p in t.split() if p]
    while parts and parts[-1].isdigit():
        parts.pop()
    return parts[-1] if parts else ""
