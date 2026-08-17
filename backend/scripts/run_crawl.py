"""手动爬取 CLI（调度器兜底入口，CLAUDE.md 第 12 章）。

用法（backend/ 目录下）：
    python -m scripts.run_crawl                  # 增量：近 N 天（settings.crawl_lookback_days）
    python -m scripts.run_crawl --backfill       # 历史回填：近 180 天
    python -m scripts.run_crawl --backfill --days 90 --min-year 2024
"""
import argparse
import json
import logging

from app.crawler.pipeline import run_pipeline
from app.db import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="手动爬取 AI4SE 论文（arXiv → DBLP 匹配）")
    parser.add_argument("--backfill", action="store_true", help="历史回填模式（默认增量）")
    parser.add_argument("--days", type=int, default=180, help="回填/回溯天数（默认 180）")
    parser.add_argument(
        "--min-year", type=int, default=None, help="DBLP 拉取起始年份（默认按库内论文自适应）"
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        stats = run_pipeline(db, lookback_days=args.days if args.backfill else None, min_year=args.min_year)
        logger.info("crawl finished: %s", json.dumps(stats, ensure_ascii=False))
    except Exception:
        logger.exception("crawl failed")
        raise SystemExit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
