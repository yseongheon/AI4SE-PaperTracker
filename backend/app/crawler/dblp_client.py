"""DBLP API 客户端：会议流批量拉取（DR-015 选定方案）。

按「会议 stream」一次拉取该会全部记录（如 stream:conf/icse:），本地过滤年份后
与库内论文匹配——请求数 = 会议数 × 页数而非论文数。

实测约束（2026-08-17，已记入 CLAUDE.md 限流红线）：
- 翻页参数是 f（first）；用 start 会被节点忽略，每页返回相同 100 条（曾致无限循环）
- stream 查询返回总数 @total 可用于终止；ICSE 全历史 7894 条 = 79 页
- `AND year:2025:` 修饰符在部分 DBLP 后端节点上被忽略（翻页时返回全流），不可靠
- 短时间高频连续请求会触发临时封禁（WinError 10054），因此采用 2s 保守间隔
- 每日增量依赖 7 天本地缓存，日常匹配几乎零 DBLP 请求；缓存过期才全量刷新
"""
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import httpx

from app.config import settings
from app.crawler.http_client import HttpPolicy, get_with_retry
from app.crawler.normalize import normalize_title

logger = logging.getLogger(__name__)

DBLP_API_URL = "https://dblp.org/search/publ/api"
PAGE_SIZE = 100  # 实测：DBLP stream 查询每页固定 100 条（h 参数无效）
CACHE_TTL_DAYS = 7  # 会议流缓存有效期：过期后全量刷新一次


@dataclass
class DblpHit:
    """DBLP 单条会议论文记录。venue_short_name 由拉取方传入（stream 查询本身就确定了所属会议，比解析 key 更可靠）。"""

    key: str  # DBLP key，如 conf/icse/Wang2025abc
    title: str
    title_normalized: str
    authors: list[str] = field(default_factory=list)
    year: int = 0
    venue_short_name: str = ""
    doi: str | None = None
    url: str | None = None


class DblpClient:
    def __init__(
        self, policy: HttpPolicy | None = None, cache_ttl_days: int = CACHE_TTL_DAYS
    ) -> None:
        # DBLP 红线：1–2s/请求，取 2s 保守档（详见模块 docstring）
        self.policy = policy or HttpPolicy(min_interval=2.0, max_attempts=3)
        self.cache_ttl_days = cache_ttl_days
        self.cache_dir = self._default_cache_dir()

    @staticmethod
    def _default_cache_dir() -> Path:
        """缓存目录 = 数据库所在目录的 dblp_cache/（与 data/ 同位置，不入 git）。"""
        db_path = Path(settings.database_url.removeprefix("sqlite:///"))
        return db_path.parent / "dblp_cache"

    # ---- 对外接口 ----

    def fetch_stream(
        self, dblp_key: str, venue_short_name: str, min_year: int | None = None
    ) -> list[DblpHit]:
        """拉取一个会议 stream 的记录（含 min_year 起的年份）。

        实测：stream 查询按年份倒序 → 页内全部记录年份 < min_year 时提前停止，
        近 3 年窗口只需 ~35 页（全历史 170 页）。优先本地缓存（7 天 TTL）。
        """
        cached = self._load_cache(dblp_key)
        if cached is not None:
            logger.info("dblp cache hit %s (%d hits)", dblp_key, len(cached))
            if min_year is not None:
                cached = [h for h in cached if h.year >= min_year]
            return cached

        hits, complete = self._fetch_pages(dblp_key, venue_short_name, min_year=min_year)
        if complete:
            # 只缓存完整拉取结果，避免截断/异常数据污染 7 天缓存
            self._save_cache(dblp_key, hits)
        else:
            logger.warning("dblp %s fetch incomplete (start < total), cache NOT saved", dblp_key)
        return hits

    # ---- 网络拉取 ----

    def _fetch_pages(
        self, dblp_key: str, venue_short_name: str, min_year: int | None = None
    ) -> tuple[list[DblpHit], bool]:
        """全量分页拉取，返回 (hits, complete)。complete=False（异常截断）时调用方不写缓存。

        终止条件（实测 DBLP 行为诡异，双保险）：
        1) start 越过 @total → 正常完整终止（complete=True）；
        2) 页内 key 全部已见过 → 内容循环（total 缺失时的兜底，complete=False）。
        min_year 仅用于缓存过滤（截断不可靠：排序非严格年份倒序）。
        """
        hits: list[DblpHit] = []
        seen_keys: set[str] = set()
        query = f"stream:{dblp_key}:"
        start = 0
        page_no = 0
        total: int | None = None
        complete = False
        with httpx.Client() as client:
            while True:
                text = self._fetch_page_with_pause(client, query, start)
                page, total = self._parse_page(text, venue_short_name)
                logger.info("dblp %s start=%d got=%d total=%s", dblp_key, start, len(page), total)
                if not page:
                    complete = total is not None and start >= total
                    break
                hits.extend(page)
                # 循环检测：本页 key 全部已在先前页见过 → DBLP 翻页内容循环（total 缺失时的兜底）
                new_keys = [h.key for h in page if h.key]
                is_loop = bool(new_keys) and all(k in seen_keys for k in new_keys)
                seen_keys.update(new_keys)
                start += PAGE_SIZE
                page_no += 1
                if page_no % 5 == 0:
                    logger.info("dblp %s pause 20s after %d pages", dblp_key, page_no)
                    time.sleep(20)
                if total is not None and start >= total:
                    complete = True
                    break
                if is_loop:
                    logger.warning("dblp %s content loop detected at start=%d, stop", dblp_key, start)
                    break
        logger.info("dblp %s fetch done: %d hits complete=%s", dblp_key, len(hits), complete)
        return hits, complete

    def _fetch_page_with_pause(
        self, client: httpx.Client, query: str, start: int
    ) -> str:
        """拉取单页原文：失败（限流/5xx/网络）休息 90s 重试，最多 5 轮。"""
        last_exc: Exception | None = None
        for attempt in range(5):
            try:
                resp = get_with_retry(
                    client,
                    DBLP_API_URL,
                    self.policy,
                    params={
                        "q": query,
                        "format": "json",
                        "h": PAGE_SIZE,
                        # 实测（2026-08-17）：翻页参数是 f（first），不是 start！
                        # start 会被当前 DBLP 节点忽略，每页返回相同 100 条 → 无限循环
                        "f": start,
                    },
                    timeout=60.0,
                )
                return resp.text
            except Exception as exc:  # 503/429/10054/JSONDecodeError 等
                last_exc = exc
                logger.warning(
                    "dblp %s start=%d attempt=%d failed (%s), pause 90s",
                    query,
                    start,
                    attempt,
                    type(exc).__name__,
                )
                time.sleep(90)
        raise last_exc or RuntimeError(f"dblp page fetch failed: {query} start={start}")

    # ---- 本地缓存 ----

    def _cache_file(self, dblp_key: str) -> Path:
        safe = dblp_key.replace("/", "_")
        return self.cache_dir / f"{safe}.json"

    def _load_cache(self, dblp_key: str) -> list[DblpHit] | None:
        """缓存有效期内返回 hits，否则返回 None。"""
        path = self._cache_file(dblp_key)
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            fetched_at = datetime.fromisoformat(raw["fetched_at"])
            if (datetime.utcnow() - fetched_at).days >= self.cache_ttl_days:
                return None
            return [DblpHit(**item) for item in raw["hits"]]
        except (ValueError, KeyError, TypeError):
            logger.warning("dblp cache corrupt: %s, will refetch", path)
            return None

    def _save_cache(self, dblp_key: str, hits: list[DblpHit]) -> None:
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            payload = {
                "fetched_at": datetime.utcnow().isoformat(),
                "hits": [asdict(h) for h in hits],
            }
            self._cache_file(dblp_key).write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
        except OSError:
            logger.exception("dblp cache write failed (non-fatal)")

    # ---- 解析 ----

    @staticmethod
    def _parse_page(json_text: str, venue_short_name: str) -> tuple[list[DblpHit], int | None]:
        """解析单页：返回 (hits, total)。total 为响应中的命中总数，用于分页终止。"""
        data = json.loads(json_text)
        hits_wrap = (data.get("result") or {}).get("hits") or {}
        raw = hits_wrap.get("hit", []) if isinstance(hits_wrap, dict) else []
        total_raw = hits_wrap.get("@total")
        try:
            total = int(total_raw) if total_raw else None
        except (TypeError, ValueError):
            total = None
        hits = DblpClient._parse_hits(json_text, venue_short_name)
        return hits, total

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
