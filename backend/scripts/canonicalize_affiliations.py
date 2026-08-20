"""机构别名改写：把 paper_authors.affiliation 存量值经别名库映射为 canonical。

用法（cd backend）：
    python -m scripts.canonicalize_affiliations             # 全量改写
    python -m scripts.canonicalize_affiliations --limit 50  # 试跑前 50 行

设计：
- 幂等：仅 alias 命中才改写，重复执行无副作用
- 审计：crawl_runs 记录 source=canonicalize；每 COMMIT_EVERY 行 commit 断点续跑
"""
import argparse
import logging
from datetime import datetime

from app.crawler.normalize import apply_institution_alias
from app.db import SessionLocal
from app.models import CrawlRun, PaperAuthor
from app.services.institution_service import load_institution_alias_map

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

COMMIT_EVERY = 200


def canonicalize_affiliations(limit: int | None = None) -> dict:
    db = SessionLocal()
    alias_map = load_institution_alias_map(db)
    try:
        query = db.query(PaperAuthor).filter(PaperAuthor.affiliation.isnot(None))
        if limit:
            query = query.limit(limit)
        rows = query.all()
        if not rows:
            logger.info("no affiliations to canonicalize")
            return {"scanned": 0, "changed": 0}

        run = CrawlRun(source="canonicalize", status="running")
        db.add(run)
        db.commit()

        scanned = changed = 0
        for row in rows:
            canonical = apply_institution_alias(row.affiliation, alias_map)
            if canonical != row.affiliation:
                row.affiliation = canonical
                changed += 1
            scanned += 1
            if scanned % COMMIT_EVERY == 0:
                db.commit()  # 断点续跑不丢进度
        db.commit()

        run.status = "success"
        run.fetched_count = scanned
        run.updated_count = changed
        run.finished_at = datetime.utcnow()
        db.commit()
        logger.info("canonicalize done: %d scanned, %d changed", scanned, changed)
        return {"scanned": scanned, "changed": changed}
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="机构别名改写（存量 affiliation → canonical）")
    parser.add_argument("--limit", type=int, default=None, help="最多处理 N 行（试跑）")
    args = parser.parse_args()
    stats = canonicalize_affiliations(limit=args.limit)
    logger.info("stats: %s", stats)
