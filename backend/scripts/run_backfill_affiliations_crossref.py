"""机构回填（A 会论文）：从 Crossref 按 DOI 拉取作者机构，写入 paper_authors.affiliation。

用法（cd backend）：
    python -m scripts.run_backfill_affiliations_crossref             # 回填有缺失机构的 DOI 论文
    python -m scripts.run_backfill_affiliations_crossref --limit 5   # 试跑前 5 篇
    python -m scripts.run_backfill_affiliations_crossref --force     # 全量重写（覆盖已有机构）

设计：
- 幂等：非 force 只处理存在缺失机构作者链接的论文；Crossref 响应走 aff:{doi} 本地缓存
- 作者匹配：P1 精确全名 → P2 位置+姓氏 → P3 纯位置（best-effort）
- 机构经 normalize_institution + 别名合并后写入；审计 crawl_runs source=crossref_aff；每篇 commit 断点续跑
"""
import argparse
import logging
import time
from collections import defaultdict
from datetime import datetime

from app.crawler.citation_client import build_citation_client
from app.crawler.normalize import (
    apply_institution_alias,
    author_last_name,
    normalize_author,
    normalize_institution,
)
from app.db import SessionLocal
from app.models import CrawlRun, Paper, PaperAuthor
from app.services.institution_service import load_institution_alias_map

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _pick_affiliation(affs: list[str], alias_map: dict[str, str]) -> str | None:
    """取第一个非空机构，经归一化 + 别名合并。"""
    for raw in affs:
        norm = apply_institution_alias(normalize_institution(raw), alias_map)
        if norm:
            return norm
    return None


def _match_affiliations(
    links: list[PaperAuthor], crossref_authors: list[dict], alias_map: dict[str, str]
) -> dict[int, str | None]:
    """Crossref 作者 → 本库 paper_author 的机构分配（返回 {position: canonical 机构或 None}）。

    P1 精确全名匹配（normalize_author）；P2 数量相等时按位置+姓氏兜底（防重排）；
    P3 纯位置兜底（best-effort）。Crossref 作者顺序与 arXiv 可能有差异。
    """
    by_name: dict[str, list[PaperAuthor]] = defaultdict(list)
    for link in links:
        by_name[normalize_author(link.author.name)].append(link)

    used: set[int] = set()
    out: dict[int, str | None] = {}

    def assign(ca: dict, position: int) -> None:
        used.add(position)
        out[position] = _pick_affiliation(ca.get("affiliations") or [], alias_map)

    # P1：精确全名匹配（同名多作者取第一个未分配）
    for ca in crossref_authors:
        key = normalize_author(ca.get("name", ""))
        for link in by_name.get(key, []):
            if link.position not in used:
                assign(ca, link.position)
                break

    # P2：数量相等时按位置 + 姓氏兜底
    if len(crossref_authors) == len(links):
        for ca, link in zip(crossref_authors, links):
            if link.position in used:
                continue
            if author_last_name(ca.get("name", "")) == author_last_name(link.author.name):
                assign(ca, link.position)

    # P3：纯位置兜底（best-effort）
    for i, link in enumerate(links):
        if link.position in used:
            continue
        if i < len(crossref_authors):
            assign(crossref_authors[i], link.position)
        else:
            out[link.position] = None
    return out


def run_crossref_affiliations(
    force: bool = False, limit: int | None = None, client=None
) -> dict:
    db = SessionLocal()
    client = client or build_citation_client()
    alias_map = load_institution_alias_map(db)
    try:
        q = db.query(Paper).filter(Paper.doi.isnot(None))
        if not force:
            # 只处理存在缺失机构作者链接的论文（幂等；首跑后无机构论文会被再次扫描，属可接受成本）
            q = q.filter(Paper.author_links.any(PaperAuthor.affiliation.is_(None)))
        query = q.order_by(Paper.id)
        if limit:
            query = query.limit(limit)
        papers = query.all()
        if not papers:
            logger.info("no papers to backfill (no DOI papers with missing affiliations)")
            return {"processed": 0, "with_affiliation": 0, "mismatch": 0, "no_crossref": 0}

        logger.info("backfill crossref affiliations for %d papers (force=%s)", len(papers), force)
        run = CrawlRun(source="crossref_aff", status="running")
        db.add(run)
        db.commit()

        processed = with_affiliation = mismatch = no_crossref = 0
        start = time.monotonic()
        for paper in papers:
            crossref = client.lookup_authors(paper.doi)
            if not crossref:
                no_crossref += 1
                logger.warning("no crossref authors for doi=%s", paper.doi)
            else:
                links = sorted(paper.author_links, key=lambda l: l.position)
                if len(links) != len(crossref):
                    mismatch += 1
                matched = _match_affiliations(links, crossref, alias_map)
                assigned = False
                for link in links:
                    link.affiliation = matched.get(link.position)
                    if link.affiliation:
                        assigned = True
                if assigned:
                    with_affiliation += 1
            processed += 1
            db.commit()  # 每篇提交：断点续跑不丢进度
            if processed % 50 == 0:
                elapsed = time.monotonic() - start
                rate = processed / elapsed if elapsed else 0
                logger.info(
                    "progress %d/%d (with_aff=%d, %.1f/min)",
                    processed, len(papers), with_affiliation, rate * 60,
                )

        run.status = "success"
        run.fetched_count = processed
        run.new_count = with_affiliation
        run.updated_count = processed - with_affiliation
        run.failed_count = no_crossref
        run.finished_at = datetime.utcnow()
        db.commit()
        logger.info(
            "crossref affiliations done: %d processed, %d with aff, %d mismatch, %d no_crossref",
            processed, with_affiliation, mismatch, no_crossref,
        )
        return {
            "processed": processed,
            "with_affiliation": with_affiliation,
            "mismatch": mismatch,
            "no_crossref": no_crossref,
        }
    finally:
        client.close()
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crossref 机构回填（A 会 DOI 论文 → paper_authors.affiliation）")
    parser.add_argument("--force", action="store_true", help="全量重写（覆盖已有机构）")
    parser.add_argument("--limit", type=int, default=None, help="最多处理 N 篇（试跑）")
    args = parser.parse_args()
    stats = run_crossref_affiliations(force=args.force, limit=args.limit)
    logger.info("stats: %s", stats)
