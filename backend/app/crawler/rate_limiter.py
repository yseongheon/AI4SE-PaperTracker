"""限流器（RateLimiter）：保证外部 API 请求间隔 ≥ 最小间隔，遵守限流红线。"""
import time

# 指数退避表：attempt 0→1s、1→2s、2→4s、3→8s（CLAUDE.md 第 6 章红线）
BACKOFFS = (1, 2, 4, 8)


class RateLimiter:
    """串行请求限流：acquire() 阻塞直至距上一次请求满 min_interval 秒。"""

    def __init__(self, min_interval: float) -> None:
        self.min_interval = min_interval
        self._last: float = 0.0

    def acquire(self) -> None:
        now = time.monotonic()
        wait = self._last + self.min_interval - now
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()


def backoff_sleep(attempt: int) -> None:
    """指数退避：attempt 从 0 起，依次睡 1/2/4/8 秒；超出表长则取末档。"""
    index = min(max(attempt, 0), len(BACKOFFS) - 1)
    time.sleep(BACKOFFS[index])
