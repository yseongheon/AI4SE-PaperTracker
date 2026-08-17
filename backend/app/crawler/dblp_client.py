"""DBLP API 客户端：会议流批量拉取（DR-015 选定方案）。

按「会议 stream」一次拉取该会全部年份论文（如 stream:conf/icse:），
本地过滤年份后与库内论文匹配——请求数 = 会议数而非论文数。
限流红线（CLAUDE.md 第 6 章）：1–2s/请求、429 尊重 Retry-After。
"""
import json
import logging
from dataclasses import dataclass

import httpx

from app.crawler.http_client import HttpPolicy, get_with_retry
from app.crawler.normalize import normalize_title

logger = logging.getLogger(__name__)

DBLP_API_URL = "https://dblp.org/search/publ/api"
PAGE_SIZE = 100  # 实测：DBLP stream 查询每页固定 100 条（h 参数无效）


@dataclass
class DblpHit:
    """DBLP 单条会议论文记录。venue_short_name 由拉取方传入（stream 查询本身就确定了所属会议，比解析 key 更可靠）。"""

    key: str  # DBLP key，如 conf/icse/Wang2025abc
    title: str
    title_normalized: str
    authors: list[str]
    year: int
    venue_short_name: str  # 所属会议短名（ICSE/FSE/ASE/ISSTA）
    doi: str | None
    url: str | None


class DblpClient:
    def __init__(self, policy: HttpPolicy | None = None) -> None:
        # DBLP 红线：1–2s/请求
        self.policy = policy or HttpPolicy(min_interval=1.5, max_attempts=3)

    def fetch_stream(
        self, dblp_key: str, venue_short_name: str, years: range | None = None
    ) -> list[DblpHit]:
        """拉取一个会议 stream 的记录。

        实测：DBLP stream 查询每页固定只返回 100 条（h 参数无效），
        全历史（如 ICSE 7894 条）逐页拉要 79 页；按年份逐年查询
        （stream:conf/icse: AND year:2025:）每会每年仅 1~4 页，大幅减请求。
        years 为 None 时拉全量。
        """
        hits: list[DblpHit] = []
        year_list = list(years) if years is not None else [None]
        with httpx.Client() as client:
            for year in year_list:
                query = f"stream:{dblp_key}:"
                if year is not None:
                    query += f" AND year:{year}:"
                start = 0
                while True:
                    resp = get_with_retry(
                        client,
                        DBLP_API_URL,
                        self.policy,
                        params={
                            "q": query,
                            "format": "json",
                            "h": PAGE_SIZE,
                            "start": start,
                        },
                        timeout=60.0,
                    )
                    page = self._parse_hits(resp.text, venue_short_name)
                    logger.info("dblp %s year=%s start=%d got=%d", dblp_key, year, start, len(page))
                    hits.extend(page)
                    if len(page) < PAGE_SIZE:
                        break
                    start += PAGE_SIZE
        return hits

    @staticmethod
    def _parse_hits(json_text: str, venue_short_name: str) -> list[DblpHit]:
        data = json.loads(json_text)
        hits_wrap = (data.get("result") or {}).get("hits") or {}
        raw = hits_wrap.get("hit", []) if isinstance(hits_wrap, dict) else []

        out: list[DblpHit] = []
        for h in raw:
            info = h.get("info") or {}
            title = info.get("title") or ""
            if not title:
                continue
            authors_raw = (info.get("authors") or {}).get("author")
            if isinstance(authors_raw, dict):  # 单作者时 DBLP 返回对象而非数组
                authors_raw = [authors_raw]
            authors = [
                (a.get("text") or "").strip()
                for a in (authors_raw or [])
                if (a.get("text") or "").strip()
            ]
            try:
                year = int(info.get("year") or 0)
            except (TypeError, ValueError):
                continue
            out.append(
                DblpHit(
                    key=info.get("key") or "",
                    title=title,
                    title_normalized=normalize_title(title),
                    authors=authors,
                    year=year,
                    venue_short_name=venue_short_name,
                    doi=info.get("doi") or None,
                    url=info.get("url") or None,
                )
            )
        return out
