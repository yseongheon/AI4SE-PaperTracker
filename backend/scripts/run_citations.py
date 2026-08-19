"""引用数回填（M8，DR-023 双源混合）：Crossref(DOI) 优先 + Semantic Scholar(arXiv) 兜底。

用法（cd backend）：
    python -m scripts.run_citations             # 回填 citation_count IS NULL 的论文
    python -m scripts.run_citations --force     # 全量重查（覆盖已有值）
    python -m scripts.run_citations --limit 20  # 试跑前 20 篇

设计：
- 幂等：默认跳过已有值的论文；结果缓存 data/citation_cache/ 支持断点续跑
- 分两轮：先跑有 DOI 的（Crossref 快），再跑纯 arXiv 的（S2 慢，限流 20/min）
- 审计：crawl_runs 表记录 source=citation
"""
import argparse
import logging
import time
from datetime import datetime

from app.crawler.citation_client import CitationClient
from app.db import SessionLocal
from app.models import CrawlRun, Paper

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run_citations(force: bool = False, limit: int | None = None) -> dict:
    db = SessionLocal()
    client = CitationClient()
    try:
        q = db.query(Paper)
        if not force:
            q = q.filter(Paper.citation_count.is_(None))
        # 有 DOI 的优先（Crossref 快）；纯 arXiv 的靠后（S2 限流慢）
        query = q.order_by(Paper.doi.is_(None), Paper.id)
        if limit:
            query = query.limit(limit)
        pending = query.all()
        if not pending:
            logger.info("no papers to backfill (all have citation_count or none pending)")
            return {"updated": 0, "found": 0, "missing": 0}

        logger.info("backfill %d papers (force=%s)", len(pending), force)
        run = CrawlRun(source="citation", status="running")
        db.add(run)
        db.commit()

        updated = found = missing = 0
        start = time.monotonic()
        for i, paper in enumerate(pending, 1):
            value = client.lookup(paper.doi, paper.arxiv_id)
            paper.citation_count = value
            if value is None:
                missing += 1
            else:
                found += 1
            updated += 1
            db.commit()  # 每篇提交：断点续跑不丢进度
            if i % 50 == 0 or i == len(pending):
                elapsed = time.monotonic() - start
                rate = i / elapsed if elapsed else 0
                logger.info(
                    "progress %d/%d (found=%d missing=%d, %.1f/min)",
                    i, len(pending), found, missing, rate * 60,
                )

        run.status = "success"
        run.fetched_count = updated
        run.new_count = found
        run.updated_count = updated - found
        run.failed_count = missing
        run.finished_at = datetime.utcnow()
        db.commit()
        logger.info("citations done: %d updated, %d found, %d missing", updated, found, missing)
        return {"updated": updated, "found": found, "missing": missing}
    finally:
        client.close()
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="引用数回填（Crossref + Semantic Scholar）")
    parser.add_argument("--force", action="store_true", help="全量重查（覆盖已有值）")
    parser.add_argument("--limit", type=int, default=None, help="最多处理 N 篇（试跑）")
    args = parser.parse_args()
    stats = run_citations(force=args.force, limit=args.limit)
    logger.info("stats: %s", stats)
