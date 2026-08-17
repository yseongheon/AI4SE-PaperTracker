"""限流器与指数退避测试（mock 时钟，不真实等待）。"""
from unittest.mock import patch

from app.crawler.rate_limiter import RateLimiter, backoff_sleep


def test_rate_limiter_no_wait_on_first():
    limiter = RateLimiter(min_interval=3.0)
    with patch("app.crawler.rate_limiter.time.monotonic", side_effect=[100.0, 100.0]), patch(
        "app.crawler.rate_limiter.time.sleep"
    ) as sleep:
        limiter.acquire()
    sleep.assert_not_called()


def test_rate_limiter_waits_when_interval_not_elapsed():
    limiter = RateLimiter(min_interval=3.0)
    # 两次 acquire：第二次距上次仅 0s → 需睡满 3s；第三次已过 3s → 不睡
    with patch("app.crawler.rate_limiter.time.monotonic", side_effect=[100.0, 100.0, 100.0, 100.0]), patch(
        "app.crawler.rate_limiter.time.sleep"
    ) as sleep:
        limiter.acquire()
        limiter.acquire()
    sleep.assert_called_once_with(3.0)


def test_rate_limiter_no_wait_after_interval():
    limiter = RateLimiter(min_interval=3.0)
    # 第一次 t=100（记录 _last=100），第二次 t=103.5 → 间隔已满足，不睡
    with patch("app.crawler.rate_limiter.time.monotonic", side_effect=[100.0, 100.0, 103.5, 103.5]), patch(
        "app.crawler.rate_limiter.time.sleep"
    ) as sleep:
        limiter.acquire()
        limiter.acquire()
    sleep.assert_not_called()


def test_backoff_sequence():
    with patch("app.crawler.rate_limiter.time.sleep") as sleep:
        for i in range(4):
            backoff_sleep(i)
    assert [c.args[0] for c in sleep.call_args_list] == [1.0, 2.0, 4.0, 8.0]


def test_backoff_caps_at_max():
    with patch("app.crawler.rate_limiter.time.sleep") as sleep:
        backoff_sleep(99)
    assert sleep.call_args.args[0] == 8.0
