"""arXiv API 客户端：按分类+提交时间窗拉取论文元数据（Atom XML）。

限流红线（CLAUDE.md 第 6 章）：每请求间隔 ≥3 秒、单连接、max_results ≤ 500、
描述性 User-Agent、指数退避（均由 http_client 统一保证）。
"""
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import httpx

from app.crawler.http_client import HttpPolicy, get_with_retry

logger = logging.getLogger(__name__)

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ATOM_NS = {"a": "http://www.w3.org/2005/Atom", "ar": "http://arxiv.org/schemas/atom"}
MAX_PAGE = 500  # arXiv 上限


@dataclass
class ArxivEntry:
    """arXiv 单条论文元数据（解析后的最小字段集）。"""

    arxiv_id: str  # 如 2502.12345
    title: str
    abstract: str
    authors: list[str] = field(default_factory=list)
    published: datetime | None = None
    updated: datetime | None = None
    journal_ref: str | None = None  # 正式发表出处线索（如 "Accepted at ICSE 2026"）
    comment: str | None = None
    categories: list[str] = field(default_factory=list)
    url: str = ""

    @property
    def normalized_id(self) -> str:
        """去版本号：2502.12345v2 → 2502.12345（版本更新按同一论文 upsert）。"""
        return self.arxiv_id.split("v")[0]


class ArxivClient:
    def __init__(self, policy: HttpPolicy | None = None) -> None:
        # arXiv 红线：≥3s/请求
        self.policy = policy or HttpPolicy(min_interval=3.0, max_attempts=3)

    def fetch(self, since: datetime, until: datetime | None = None) -> list[ArxivEntry]:
        """拉取 [since, until) 窗口内 cs.SE 提交的论文；until 默认 now。

        分页循环：start 递增直到返回条数 < MAX_PAGE。
        """
        until = until or datetime.utcnow()
        entries: list[ArxivEntry] = []
        start = 0
        with httpx.Client() as client:
            while True:
                query = (
                    f"cat:cs.SE AND submittedDate:[{since:%Y%m%d%H%M} TO {until:%Y%m%d%H%M}]"
                )
                resp = get_with_retry(
                    client,
                    ARXIV_API_URL,
                    self.policy,
                    params={"search_query": query, "start": start, "max_results": MAX_PAGE},
                    timeout=60.0,
                )
                page = self._parse_feed(resp.text)
                logger.info("arxiv page start=%d got=%d", start, len(page))
                entries.extend(page)
                if len(page) < MAX_PAGE:
                    break
                start += MAX_PAGE
        return entries

    @staticmethod
    def _parse_feed(xml_text: str) -> list[ArxivEntry]:
        root = ET.fromstring(xml_text)
        out: list[ArxivEntry] = []
        for entry in root.findall("a:entry", ATOM_NS):
            try:
                e = ArxivClient._parse_entry(entry)
                if e:
                    out.append(e)
            except Exception:  # 单条解析失败不拖垮整页
                logger.exception("parse arxiv entry failed, skip")
        return out

    @staticmethod
    def _parse_entry(entry: ET.Element) -> ArxivEntry | None:
        url_el = entry.find("a:id", ATOM_NS)
        if url_el is None or url_el.text is None:
            return None
        m = re.search(r"abs/([\w.]+)", url_el.text)
        if not m:
            return None

        def text(tag: str) -> str:
            el = entry.find(tag, ATOM_NS)
            if el is None or el.text is None:
                return ""
            return " ".join(el.text.split())  # 压缩换行/空白

        def dt(tag: str) -> datetime | None:
            el = entry.find(tag, ATOM_NS)
            if el is None or not el.text:
                return None
            try:
                return datetime.fromisoformat(el.text.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                return None

        authors = [
            " ".join(a.text.split())
            for a in entry.findall("a:author/a:name", ATOM_NS)
            if a.text
        ]
        categories = [
            c.get("term", "")
            for c in entry.findall("a:category", ATOM_NS)
            if c.get("term")
        ]

        def arx_text(tag: str) -> str | None:
            el = entry.find(f"ar:{tag}", ATOM_NS)
            if el is None or not el.text:
                return None
            return " ".join(el.text.split())

        return ArxivEntry(
            arxiv_id=m.group(1),
            title=text("a:title"),
            abstract=text("a:summary"),
            authors=authors,
            published=dt("a:published"),
            updated=dt("a:updated"),
            journal_ref=arx_text("journal_ref"),
            comment=arx_text("comment"),
            categories=categories,
            url=url_el.text,
        )


def default_lookback_window(days: int) -> tuple[datetime, datetime]:
    """默认增量窗口：近 days 天（含容错）。"""
    until = datetime.utcnow()
    return until - timedelta(days=days), until
