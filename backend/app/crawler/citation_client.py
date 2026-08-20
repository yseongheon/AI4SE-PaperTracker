"""引用数查询客户端（M8，DR-023 调整：OpenAlex 被墙 → 双源混合）。

实测（2026-08-19）：api.openalex.org 国内不可达（连接超时）；api.crossref.org 与
api.semanticscholar.org 可达。用户拍板双源：
- Crossref 优先：按 DOI 查 is-referenced-by-count（快、限流宽松）
- Semantic Scholar 兜底：按 arXiv ID 查 citationCount（限流 100 次/5 分钟，3s/请求）
结果本地缓存（data/citation_cache/），支持断点续跑；幂等。
"""
import json
import logging
import re
import time
from pathlib import Path
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

CROSSREF_BASE = "https://api.crossref.org/works"
S2_BASE = "https://api.semanticscholar.org/graph/v1/paper"
CACHE_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "citation_cache"

CROSSREF_DELAY = 0.5  # Crossref 限流宽松，0.5s/请求
S2_DELAY = 3.0  # S2 无 key 100 次/5 分钟 → 3s/请求保守档


class CitationClient:
    """双源引用数查询：doi 优先 Crossref，arxiv_id 兜底 Semantic Scholar。"""

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = cache_dir or CACHE_DIR
        self.client = httpx.Client(timeout=30.0, headers={"User-Agent": "AI4SE-PaperTracker/0.1 (mailto:xiaoyf66@mail2.sysu.edu.cn)"})
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.hits = 0
        self.misses = 0

    def close(self) -> None:
        self.client.close()

    # ---- 缓存 ----

    @staticmethod
    def _safe_key(key: str) -> str:
        """文件名安全化：Windows 文件名不能含 : / 等字符（doi:10.1145/... → doi_10_1145_...）。"""
        return re.sub(r"[^\w.-]", "_", key)

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / f"{self._safe_key(key)}.json"

    def _cache_get(self, key: str) -> int | None:
        path = self._cache_path(key)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self.hits += 1
                return data.get("cited_by_count")
            except (ValueError, KeyError, TypeError, OSError):
                pass
        return None

    def _cache_put(self, key: str, value: int | None) -> None:
        try:
            self._cache_path(key).write_text(
                json.dumps({"cited_by_count": value}, ensure_ascii=False), encoding="utf-8"
            )
        except OSError as exc:
            logger.warning("citation cache write failed (non-fatal): %s (%s)", key, exc)

    def _cache_get_json(self, key: str) -> dict | None:
        """JSON 缓存读（作者机构用，独立于 int 计数缓存）。"""
        path = self._cache_path(key)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self.hits += 1
                return data
            except (ValueError, TypeError, OSError):
                pass
        return None

    def _cache_put_json(self, key: str, value: dict) -> None:
        try:
            self._cache_path(key).write_text(
                json.dumps(value, ensure_ascii=False), encoding="utf-8"
            )
        except OSError as exc:
            logger.warning("affiliation cache write failed (non-fatal): %s (%s)", key, exc)

    # ---- Crossref（按 DOI） ----

    def _crossref_lookup(self, doi: str) -> int | None:
        url = f"{CROSSREF_BASE}/{quote(doi, safe='')}"
        resp = self.client.get(url)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return int(resp.json()["message"].get("is-referenced-by-count") or 0)

    def lookup_authors(self, doi: str) -> list[dict] | None:
        """按 DOI 拉取作者机构（Crossref author.affiliation），本地缓存 aff:{doi}。

        返回 [{"name": "given family 或企业名", "affiliations": [第一个非空机构]}, ...]；
        无作者/失败返回 None，调用方跳过。真实请求后睡 CROSSREF_DELAY（限流）。
        """
        key = f"aff:{doi}"
        if self._cache_path(key).exists():
            cached = self._cache_get_json(key)
            if cached is not None:
                return cached.get("authors")
        try:
            authors = self._crossref_authors(doi)
            self._cache_put_json(key, {"authors": authors or []})
            return authors or None
        except Exception as exc:
            logger.warning("crossref authors failed %s: %s", doi, exc)
            return None
        finally:
            time.sleep(CROSSREF_DELAY)

    def _crossref_authors(self, doi: str) -> list[dict]:
        """Crossref works 作者+机构解析。

        message.author[] 每项：given/family（个人）或 name（企业作者）；
        affiliation 兼容 [{"name": ...}] 与 [str]；多机构取第一个非空（String(255) 限制）。
        """
        url = f"{CROSSREF_BASE}/{quote(doi, safe='')}"
        resp = self.client.get(url)
        if resp.status_code == 404:
            return []
        resp.raise_for_status()
        authors = resp.json().get("message", {}).get("author") or []
        out = []
        for a in authors:
            if not isinstance(a, dict):
                continue
            name = f"{a.get('given', '')} {a.get('family', '')}".strip() or a.get("name", "")
            if not name:
                continue
            affs = []
            for entry in a.get("affiliation") or []:
                if isinstance(entry, dict):
                    val = entry.get("name")
                elif isinstance(entry, str):
                    val = entry
                else:
                    val = None
                if val and val.strip():
                    affs.append(val.strip())
            out.append({"name": name, "affiliations": affs[:1]})
        return out

    # ---- Semantic Scholar（按 arXiv ID） ----

    def _s2_lookup(self, arxiv_id: str) -> int | None:
        url = f"{S2_BASE}/arXiv:{quote(arxiv_id)}?fields=citationCount"
        for attempt in range(2):  # 429 尊重 Retry-After，最多重试 1 次
            resp = self.client.get(url)
            if resp.status_code == 404:
                return None
            if resp.status_code == 429:
                retry = int(resp.headers.get("Retry-After", "30"))
                logger.warning("S2 rate limited, waiting %ds (attempt %d)", retry, attempt + 1)
                time.sleep(retry)
                continue
            resp.raise_for_status()
            return int(resp.json().get("citationCount") or 0)
        return None

    # ---- 统一入口 ----

    def lookup(self, doi: str | None, arxiv_id: str | None) -> int | None:
        """doi 优先（Crossref），无/失败 → arxiv（S2）。全部走本地缓存。"""
        if doi:
            cached = self._cache_get(f"doi:{doi}")
            if cached is not None or self._cache_path(f"doi:{doi}").exists():
                return cached
            try:
                value = self._crossref_lookup(doi)
                self._cache_put(f"doi:{doi}", value)
                if value is not None:
                    return value
            except Exception as exc:
                logger.warning("crossref lookup failed %s: %s", doi, exc)
            time.sleep(CROSSREF_DELAY)

        if arxiv_id:
            cached = self._cache_get(f"arxiv:{arxiv_id}")
            if cached is not None or self._cache_path(f"arxiv:{arxiv_id}").exists():
                return cached
            try:
                value = self._s2_lookup(arxiv_id)
                self._cache_put(f"arxiv:{arxiv_id}", value)
                return value
            except Exception as exc:
                logger.warning("s2 lookup failed %s: %s", arxiv_id, exc)
            time.sleep(S2_DELAY)
        return None


def build_citation_client() -> CitationClient:
    return CitationClient()
