"""外部 HTTP 统一调用：限流 + 指数退避 + 429 尊重 Retry-After（CLAUDE.md 第 7 章重试约定）。"""
import time

import httpx

from app.crawler.rate_limiter import RateLimiter, backoff_sleep

# 描述性 User-Agent：arXiv/DBLP 礼貌使用要求（CLAUDE.md 第 6 章红线）
USER_AGENT = "AI4SE-PaperTracker/0.1 (academic paper tracking; contact xiaoyf-debug@qq.com)"


class HttpPolicy:
    """一次外部 API 的访问策略：限流间隔 + 重试次数。"""

    def __init__(self, min_interval: float = 3.0, max_attempts: int = 3) -> None:
        self.min_interval = min_interval
        self.max_attempts = max_attempts
        self.limiter = RateLimiter(min_interval)


def get_with_retry(
    client: httpx.Client,
    url: str,
    policy: HttpPolicy,
    params: dict | None = None,
    timeout: float = 30.0,
) -> httpx.Response:
    """GET 请求：每请求前限流；网络错误按退避表重试；429 尊重 Retry-After。"""
    last_exc: httpx.HTTPError | None = None
    for attempt in range(policy.max_attempts):
        policy.limiter.acquire()
        try:
            resp = client.get(
                url, params=params, timeout=timeout, headers={"User-Agent": USER_AGENT}
            )
            if resp.status_code == 429 or resp.status_code >= 500:
                # 429：优先尊重 Retry-After；无则按退避表。5xx（临时服务器故障）按退避表重试
                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After", "")
                    if retry_after.isdigit():
                        time.sleep(min(int(retry_after), 60))
                        continue
                if attempt < policy.max_attempts - 1:
                    backoff_sleep(attempt)
                    continue
            resp.raise_for_status()
            return resp
        except httpx.HTTPStatusError:
            raise  # 其余 4xx 不重试（参数错误等重试无意义）
        except httpx.HTTPError as exc:  # 网络/超时/连接错误
            last_exc = exc
            if attempt < policy.max_attempts - 1:
                backoff_sleep(attempt)
    raise last_exc if last_exc else httpx.HTTPError(f"GET {url} failed")
