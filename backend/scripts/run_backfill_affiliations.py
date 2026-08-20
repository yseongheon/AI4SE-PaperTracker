"""机构回填（机构榜/作者机构功能）：从 arXiv 重拉论文元数据，提取每作者机构。

用法（cd backend）：
    python -m scripts.run_backfill_affiliations             # 回填有缺失机构的论文
    python -m scripts.run_backfill_affiliations --limit 50  # 试跑前 50 篇
    python -m scripts.run_backfill_affiliations --force     # 全量重写（覆盖已有机构）

设计：
- 幂等：arXiv id_list 批量拉取（默认 200/批，实测必须显式传 max_results 否则默认只回 10 条）
- 按 normalized_id 匹配（响应顺序不保证）；作者按与 _replace_authors 相同的去重规则对齐 position
- 机构经 normalize_institution 规则归一化后写入 paper_authors.affiliation
- 审计：crawl_runs 表记录 source=affiliation；每批 commit 断点续跑
"""
import argparse
import logging
import time
from datetime import datetime

from app.crawler.arxiv_client import ArxivClient
from app.crawler.normalize import apply_institution_alias, normalize_author, normalize_institution
from app.db import SessionLocal
from app.models import CrawlRun, Paper, PaperAuthor
from app.services.institution_service import load_institution_alias_map

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_BATCH = 200


def _align_affiliations(
    authors: list[str], affiliations: list[str], alias_map: dict[str, str] | None = None
) -> dict[int, str | None]:
    """按与 _replace_authors 相同的去重规则（空/重复名跳过）对齐，返回 {position: 归一化+别名合并机构}。"""
    seen: set[str] = set()
    position = 0
    out: dict[int, str | None] = {}
    for name, raw_aff in zip(authors, affiliations):
        norm = normalize_author(name)
        if norm in seen or not norm:
            continue
        seen.add(norm)
        out[position] = apply_institution_alias(normalize_institution(raw_aff), alias_map)
        position += 1
    return out


def run_backfill_affiliations(
    force: bool = False, limit: int | None = None, batch_size: int = DEFAULT_BATCH
) -> dict:
    db = SessionLocal()
    client = ArxivClient()
    alias_map = load_institution_alias_map(db)
    try:
        q = db.query(Paper).filter(Paper.arxiv_id.isnot(None))
        if not force:
            # 只处理存在缺失机构作者链接的论文（幂等；首跑后无机构论文会被再次扫描，属可接受成本）
            q = q.filter(Paper.author_links.any(PaperAuthor.affiliation.is_(None)))
        query = q.order_by(Paper.id)
        if limit:
            query = query.limit(limit)
        papers = query.all()
        if not papers:
            logger.info("no papers to backfill (all authors have affiliation or none pending)")
            return {"processed": 0, "with_affiliation": 0, "mismatch": 0, "missing_entries": 0}

        logger.info("backfill affiliations for %d papers (force=%s, batch=%d)", len(papers), force, batch_size)
        run = CrawlRun(source="affiliation", status="running")
        db.add(run)
        db.commit()

        processed = with_affiliation = mismatch = missing_entries = 0
        start = time.monotonic()
        for i in range(0, len(papers), batch_size):
            batch = papers[i : i + batch_size]
            ids = [p.arxiv_id for p in batch]
            entries = client.fetch_by_ids(ids)
            by_id = {e.normalized_id: e for e in entries}

            for paper in batch:
                entry = by_id.get(paper.arxiv_id)
                if entry is None:
                    missing_entries += 1
                    logger.warning("arxiv entry not returned for %s, skip", paper.arxiv_id)
                    continue
                aff_by_position = _align_affiliations(entry.authors, entry.affiliations, alias_map)
                links = sorted(paper.author_links, key=lambda l: l.position)
                if len(links) != len(aff_by_position):
                    mismatch += 1
                    logger.warning(
                        "author count mismatch for %s: db=%d arxiv=%d (best-effort align)",
                        paper.arxiv_id, len(links), len(aff_by_position),
                    )
                assigned = False
                for link in links:
                    link.affiliation = aff_by_position.get(link.position)
                    if link.affiliation:
                        assigned = True
                if assigned:
                    with_affiliation += 1
                processed += 1

            db.commit()  # 每批提交：断点续跑不丢进度
            elapsed = time.monotonic() - start
            rate = processed / elapsed if elapsed else 0
            logger.info(
                "progress %d/%d (with_aff=%d, %.1f/min)",
                min(processed, len(papers)), len(papers), with_affiliation, rate * 60,
            )

        run.status = "success"
        run.fetched_count = processed
        run.new_count = with_affiliation
        run.updated_count = processed - with_affiliation
        run.failed_count = missing_entries
        run.finished_at = datetime.utcnow()
        db.commit()
        logger.info(
            "affiliations done: %d processed, %d with affiliation, %d mismatch, %d missing",
            processed, with_affiliation, mismatch, missing_entries,
        )
        return {
            "processed": processed,
            "with_affiliation": with_affiliation,
            "mismatch": mismatch,
            "missing_entries": missing_entries,
        }
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="机构回填（arXiv 每作者机构 → paper_authors.affiliation）")
    parser.add_argument("--force", action="store_true", help="全量重写（覆盖已有机构）")
    parser.add_argument("--limit", type=int, default=None, help="最多处理 N 篇（试跑）")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH, help="每批 arXiv id 数（默认 200）")
    args = parser.parse_args()
    stats = run_backfill_affiliations(
        force=args.force, limit=args.limit, batch_size=args.batch_size
    )
    logger.info("stats: %s", stats)
