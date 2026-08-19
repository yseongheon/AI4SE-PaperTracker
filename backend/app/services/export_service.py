"""数据导出（M6）：CSV / JSON / BibTeX 三种格式，供 /api/export 与测试复用。

设计：三个纯函数生成器（输入 = PaperListItem 列表），无 DB 依赖、可单测；
CSV 带 UTF-8 BOM（Excel 兼容）；BibTeX 按 venue.type 选 @inproceedings/@article，
无正式版用 @misc arXiv 预印本兜底。
"""
import csv
import io
import json
import re

from app.schemas.paper import PaperListItem

# BibTeX 需要转义的特殊字符（& % # _ { } ~ $ ^）
_BIBTEX_ESCAPE = re.compile(r"([&%#_{}~$^])")


def _bibtex_escape(text: str | None) -> str:
    return _BIBTEX_ESCAPE.sub(r"\\\1", (text or "").strip())


def _bibtex_authors(authors: list[str]) -> str:
    """作者格式：原名已含逗号（Last, First）保持原样，否则转 Last, First。"""
    parts = []
    for name in authors:
        name = name.strip()
        if not name:
            continue
        if "," in name:
            parts.append(name)
            continue
        tokens = name.split()
        if len(tokens) > 1:
            parts.append(tokens[-1] + ", " + " ".join(tokens[:-1]))
        else:
            parts.append(name)
    return " and ".join(parts) or "Anonymous"


def _bibtex_key(paper: PaperListItem) -> str:
    """条目 key：arxiv_id（去点）> dblp_key 尾部 > paper id。"""
    if paper.arxiv_url and "/abs/" in paper.arxiv_url:
        return paper.arxiv_url.rsplit("/abs/", 1)[-1].replace(".", "")
    if paper.dblp_url:
        return paper.dblp_url.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return f"paper{paper.id}"


def _bibtex_entry(paper: PaperListItem) -> str:
    venue_type = paper.venue.type if paper.venue else None
    if venue_type == "conference":
        entry_type, venue_field = "inproceedings", "booktitle"
    elif venue_type == "journal":
        entry_type, venue_field = "article", "journal"
    else:
        entry_type, venue_field = "misc", "howpublished"
    venue_name = paper.venue.full_name if paper.venue else "arXiv preprint"

    lines = [
        f"@{entry_type}{{{_bibtex_key(paper)},",
        f"  title = {{{_bibtex_escape(paper.title)}}},",
        f"  author = {{{_bibtex_authors(paper.authors)}}},",
        f"  {venue_field} = {{{_bibtex_escape(venue_name)}}},",
        f"  year = {{{paper.year or ''}}},",
    ]
    if paper.doi:
        lines.append(f"  doi = {{{_bibtex_escape(paper.doi)}}},")
    if paper.arxiv_url:
        lines.append(f"  url = {{{paper.arxiv_url}}},")
    if paper.dblp_url:
        lines.append(f"  dblp = {{{paper.dblp_url}}},")
    lines.append("}\n")
    return "\n".join(lines)


def to_csv(items: list[PaperListItem]) -> bytes:
    """CSV：UTF-8 BOM（Excel 直接打开不乱码）。"""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["id", "title", "authors", "venue", "year", "published_at", "is_ai4se",
         "topics", "arxiv_url", "dblp_url", "doi", "bookmarked", "read"]
    )
    for p in items:
        writer.writerow(
            [
                p.id,
                p.title,
                "; ".join(p.authors),
                p.venue.short_name if p.venue else "",
                p.year or "",
                p.published_at.isoformat() if p.published_at else "",
                "yes" if p.is_ai4se_confirmed else "no",
                "; ".join(t.slug for t in p.topics),
                p.arxiv_url or "",
                p.dblp_url or "",
                p.doi or "",
                "yes" if p.marks.bookmark else "",
                "yes" if p.marks.read else "",
            ]
        )
    return ("﻿" + buf.getvalue()).encode("utf-8")  # UTF-8 BOM：Excel 直接打开不乱码


def to_json(items: list[PaperListItem]) -> bytes:
    # mode="json"：date 等类型序列化为 ISO 字符串（否则 TypeError）
    return json.dumps(
        [p.model_dump(mode="json") for p in items], ensure_ascii=False, indent=2
    ).encode("utf-8")


def to_bibtex(items: list[PaperListItem]) -> bytes:
    return "".join(_bibtex_entry(p) for p in items).encode("utf-8")


_FORMATTERS = {
    "csv": (to_csv, "text/csv; charset=utf-8", "papers.csv"),
    "json": (to_json, "application/json; charset=utf-8", "papers.json"),
    "bibtex": (to_bibtex, "application/x-bibtex; charset=utf-8", "papers.bib"),
}


def export(format_name: str, items: list[PaperListItem]) -> tuple[bytes, str, str]:
    """按格式导出，返回 (content, content_type, filename)。"""
    formatter = _FORMATTERS.get(format_name)
    if formatter is None:
        raise ValueError(f"unsupported export format: {format_name}")
    fn, content_type, filename = formatter
    return fn(items), content_type, filename
