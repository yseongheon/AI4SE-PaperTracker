"""DBLP 匹配器：预印本 ↔ 正式发表版关联（CLAUDE.md 第 5 章，全项目最关键的逻辑）。

匹配键 = title_normalized + 作者姓氏 + 年份 ±1；单候选回填、多候选优先按
arXiv journal_ref/comments 线索消歧、仍歧义则 pending 进人工复核。
"""
import logging
from collections import defaultdict

from sqlalchemy.orm import Session

from app.crawler.dblp_client import DblpHit
from app.crawler.normalize import author_last_name
from app.models import MatchStatus, Paper, Venue

logger = logging.getLogger(__name__)


class MatchStats:
    def __init__(self) -> None:
        self.records: int = 0  # DBLP 会议流记录总数
        self.matched: int = 0
        self.pending: int = 0
        self.none: int = 0


def _clue(paper: Paper) -> str:
    """arXiv 提供的发表线索（journal_ref + comments），用于多候选消歧。"""
    parts = [p for p in (paper.journal_ref, paper.comment) if p]
    return " ".join(parts).lower()


def match_papers(
    db: Session,
    papers: list[Paper],
    hits: list[DblpHit],
    venue_by_short: dict[str, Venue],
) -> MatchStats:
    """对 match_status=none 的论文做 DBLP 关联。

    命中 → 回填 dblp_key/doi/venue/year 并置 matched（不新建记录，双链接展示）；
    多候选且无消歧线索 → pending 进人工复核，不自动关联。
    """
    stats = MatchStats()
    stats.records = len(hits)

    index: dict[str, list[DblpHit]] = defaultdict(list)
    for hit in hits:
        if hit.title_normalized:
            index[hit.title_normalized].append(hit)

    for paper in papers:
        if paper.match_status != MatchStatus.NONE.value:
            continue

        cands = [
            h
            for h in index.get(paper.title_normalized, [])
            if abs(h.year - (paper.year or 0)) <= 1
        ]

        # 作者姓氏粗校验：论文第一作者姓氏需出现在候选作者中（空则跳过校验）
        first_last = (
            author_last_name(paper.author_links[0].author.name)
            if paper.author_links
            else ""
        )
        if first_last:
            cands = [
                h
                for h in cands
                if any(author_last_name(a) == first_last for a in h.authors)
            ]

        if not cands:
            stats.none += 1
            continue

        hit = _resolve(cands, paper)
        if hit is None:
            # 多候选歧义：候选快照落库（M5，人工复核脚本 scripts/review_pending.py 用）
            paper.match_status = MatchStatus.PENDING.value
            paper.match_candidates = [
                {
                    "key": h.key,
                    "venue_short_name": h.venue_short_name,
                    "year": h.year,
                    "doi": h.doi,
                }
                for h in cands
            ]
            stats.pending += 1
            continue

        venue = venue_by_short.get(hit.venue_short_name)
        paper.dblp_key = hit.key
        paper.doi = hit.doi
        paper.venue = venue
        if hit.year:
            paper.year = hit.year  # 以正式发表年份为准
        paper.match_status = MatchStatus.MATCHED.value
        paper.match_candidates = None  # 已定案，清掉历史候选
        if paper.status == "fetched":
            paper.status = "matched"
        stats.matched += 1

    return stats


def _resolve(cands: list[DblpHit], paper: Paper) -> DblpHit | None:
    """单候选直接返回；多候选先按 arXiv 发表线索（会议短名）消歧，消不掉返回 None。"""
    if len(cands) == 1:
        return cands[0]
    clue = _clue(paper)
    for h in cands:
        if h.venue_short_name.lower() in clue:
            logger.info("clue disambiguate %s → %s", paper.arxiv_id, h.venue_short_name)
            return h
    logger.info("ambiguous match %s: %s", paper.arxiv_id, [h.venue_short_name for h in cands])
    return None
