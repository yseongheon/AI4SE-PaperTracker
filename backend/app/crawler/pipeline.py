"""爬取管线：① arXiv 拉取 → ② 归一化去重 upsert → ③ DBLP A 会匹配 → ⑥ 审计入库。

M1 范围（DR-017）：只爬 cs.SE；关键词初筛④与 LLM 精标⑤属 M2。
②③ 幂等，可安全重跑（CLAUDE.md 第 6 章）。
"""
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.crawler.arxiv_client import ArxivClient, ArxivEntry, default_lookback_window
from app.crawler.dblp_client import DblpClient
from app.crawler.matcher import MatchStats, match_papers
from app.crawler.normalize import normalize_author, normalize_title
from app.models import Author, CrawlRun, Paper, PaperAuthor, Venue

logger = logging.getLogger(__name__)


def run_pipeline(db: Session, lookback_days: int | None = None, min_year: int | None = None) -> dict:
    """跑一次完整爬取，返回审计统计。

    lookback_days: 回溯天数（默认 settings.crawl_lookback_days）
    min_year: DBLP 拉取起始年份（默认按库内论文年份自适应）
    """
    lookback_days = lookback_days or settings.crawl_lookback_days
    since, until = default_lookback_window(lookback_days)

    arxiv_run = _start_run(db, "arxiv")
    try:
        entries = ArxivClient().fetch(since, until)
        new_count, updated_count = upsert_papers(db, entries)
        _finish_run(db, arxiv_run, fetched=len(entries), new=new_count, updated=updated_count)
        logger.info(
            "arxiv crawl done: fetched=%d new=%d updated=%d", len(entries), new_count, updated_count
        )
    except Exception as exc:
        _fail_run(db, arxiv_run, exc)
        raise

    dblp_stats = MatchStats()
    dblp_run = _start_run(db, "dblp")
    try:
        dblp_stats = run_dblp_match(db, min_year=min_year)
        _finish_run(db, dblp_run, fetched=dblp_stats.records, new=dblp_stats.matched)
        logger.info(
            "dblp match done: records=%d matched=%d pending=%d",
            dblp_stats.records,
            dblp_stats.matched,
            dblp_stats.pending,
        )
    except Exception as exc:
        _fail_run(db, dblp_run, exc)
        raise

    return {
        "arxiv_fetched": len(entries),
        "arxiv_new": new_count,
        "arxiv_updated": updated_count,
        "dblp_records": dblp_stats.records,
        "dblp_matched": dblp_stats.matched,
        "dblp_pending": dblp_stats.pending,
    }


def upsert_papers(db: Session, entries: list[ArxivEntry]) -> tuple[int, int]:
    """按 arxiv_id upsert（幂等）：新论文插入，已存在则更新元数据；作者 N:M 重建。"""
    new_count = 0
    updated_count = 0
    for entry in entries:
        arxiv_id = entry.normalized_id
        paper = db.query(Paper).filter_by(arxiv_id=arxiv_id).first()
        if paper is None:
            paper = Paper(arxiv_id=arxiv_id, arxiv_url=entry.url or f"https://arxiv.org/abs/{arxiv_id}")
            db.add(paper)
            new_count += 1
        else:
            updated_count += 1

        paper.title = entry.title
        paper.title_normalized = normalize_title(entry.title)
        paper.abstract = entry.abstract or None
        paper.published_at = entry.published
        paper.arxiv_updated_at = entry.updated
        paper.journal_ref = entry.journal_ref
        paper.comment = entry.comment
        if paper.year is None and entry.published:
            paper.year = entry.published.year  # 暂无正式发表年份时先用 arXiv 年份
        _replace_authors(db, paper, entry.authors)
    db.commit()
    return new_count, updated_count


def _replace_authors(db: Session, paper: Paper, author_names: list[str]) -> None:
    """重建作者关联（幂等）：归一化查重，重复作者复用同一 Author 记录。"""
    paper.author_links.clear()
    for position, name in enumerate(author_names):
        norm = normalize_author(name)
        author = db.query(Author).filter_by(name_normalized=norm).first()
        if author is None:
            author = Author(name=name, name_normalized=norm)
            db.add(author)
            db.flush()  # 获取新作者 id
        paper.author_links.append(PaperAuthor(author=author, position=position))


def run_dblp_match(db: Session, min_year: int | None = None) -> MatchStats:
    """会议流批量拉取 + 本地匹配（DR-015）。对 match_status=none 的论文执行。"""
    venues = (
        db.query(Venue)
        .filter(Venue.is_active.is_(True), Venue.type == "conference")
        .order_by(Venue.id)
        .all()
    )
    if not venues:
        logger.warning("venues 表为空，跳过 DBLP 匹配（请先运行 seed_venues）")
        return MatchStats()

    min_year = min_year or _auto_min_year(db)
    current_year = datetime.utcnow().year
    years = range(min_year, current_year + 2)  # +2 容错跨年提前发表
    hits = []
    client = DblpClient()
    for venue in venues:
        if not venue.dblp_key:
            continue
        stream_hits = client.fetch_stream(venue.dblp_key, venue.short_name, years=years)
        hits.extend(stream_hits)

    papers = db.query(Paper).filter(Paper.match_status == "none").all()
    venue_by_short = {v.short_name: v for v in venues}
    stats = match_papers(db, papers, hits, venue_by_short)
    db.commit()
    return stats


def _auto_min_year(db: Session) -> int:
    """DBLP 拉取起始年份：库内最早论文年份 -1（容错 ±1 年规则），库空用今年 -2。"""
    now = datetime.utcnow()
    min_year = db.query(Paper.year).order_by(Paper.year.asc()).first()
    if min_year and min_year[0]:
        return min_year[0] - 1
    return now.year - 2


# ---- 审计记录 ----

def _start_run(db: Session, source: str) -> CrawlRun:
    run = CrawlRun(source=source, status="running")
    db.add(run)
    db.commit()
    return run


def _finish_run(
    db: Session, run: CrawlRun, fetched: int = 0, new: int = 0, updated: int = 0
) -> None:
    run.status = "success"
    run.fetched_count = fetched
    run.new_count = new
    run.updated_count = updated
    run.finished_at = datetime.utcnow()
    db.commit()


def _fail_run(db: Session, run: CrawlRun, exc: Exception) -> None:
    run.status = "failed"
    run.error = f"{type(exc).__name__}: {exc}"
    run.finished_at = datetime.utcnow()
    db.commit()
