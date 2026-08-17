"""DBLP 匹配歧义人工复核（M5）：处理 match_status=pending 的论文。

歧义时匹配器把候选快照存入 papers.match_candidates（JSON），本脚本列出候选、
接受其中一个（回填 dblp_key/doi/venue/year 并置 matched）或整篇拒绝（rejected）。

用法（cd backend）：
    python -m scripts.review_pending list                        # 列出 pending 论文 + 候选
    python -m scripts.review_pending accept 123 --idx 1          # 接受第 1 个候选（1-based）
    python -m scripts.review_pending accept 123 --key conf/icse/2026/xxx   # 直接指定 DBLP key
    python -m scripts.review_pending reject 123                  # 确认无正式版，拒绝
"""
import argparse
import logging
import sys

from sqlalchemy import exc as sa_exc
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import MatchStatus, Paper, Venue

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def list_pending(db: Session) -> list[Paper]:
    return (
        db.query(Paper)
        .filter(Paper.match_status == MatchStatus.PENDING.value)
        .order_by(Paper.id)
        .all()
    )


def _find_pending(db: Session, paper_id: int) -> Paper:
    paper = db.get(Paper, paper_id)
    if paper is None:
        raise ValueError(f"论文 {paper_id} 不存在")
    if paper.match_status != MatchStatus.PENDING.value:
        raise ValueError(f"论文 {paper_id} 当前状态为 {paper.match_status}，不是 pending")
    return paper


def _venue_by_dblp_prefix(db: Session, dblp_key: str) -> Venue | None:
    """按 dblp_key 集合前缀反查 venue（conf/icse → ICSE）；查不到返回 None。"""
    for venue in db.query(Venue).order_by(Venue.dblp_key.desc()):  # 最长前缀优先
        if venue.dblp_key and dblp_key.startswith(venue.dblp_key + "/"):
            return venue
    return None


def accept_candidate(
    db: Session, paper_id: int, index: int | None = None, key: str | None = None
) -> Paper:
    """接受候选：--idx 取 match_candidates 第 N 个；--key 直接指定 DBLP key。"""
    if (index is None) == (key is None):
        raise ValueError("accept 必须且只能提供 --idx 或 --key 之一")
    paper = _find_pending(db, paper_id)

    if index is not None:
        cands = paper.match_candidates or []
        if not 1 <= index <= len(cands):
            raise ValueError(f"候选序号 {index} 超出范围（共 {len(cands)} 个候选）")
        c = cands[index - 1]
        dblp_key, doi, year, venue_short = (
            c["key"], c.get("doi"), c.get("year"), c.get("venue_short_name"),
        )
        venue = (
            db.query(Venue).filter_by(short_name=venue_short).first()
            if venue_short else None
        )
    else:
        dblp_key, doi, year, venue = key.strip(), None, None, None
        venue = _venue_by_dblp_prefix(db, dblp_key)

    if not dblp_key or "/" not in dblp_key:
        raise ValueError(f"非法 dblp_key：{dblp_key!r}")

    paper.dblp_key = dblp_key
    paper.doi = doi
    paper.venue = venue
    if year:
        paper.year = year  # 以正式发表年份为准
    paper.match_status = MatchStatus.MATCHED.value
    paper.match_candidates = None
    if paper.status == "fetched":
        paper.status = "matched"
    db.commit()
    logger.info("accept %s → %s（venue=%s）", paper_id, dblp_key, venue.short_name if venue else "?")
    return paper


def reject_paper(db: Session, paper_id: int) -> Paper:
    """拒绝：确认该 arXiv 论文无 CCF-A 正式版。"""
    paper = _find_pending(db, paper_id)
    paper.match_status = MatchStatus.REJECTED.value
    db.commit()
    logger.info("reject %s（%s）", paper_id, paper.title[:60])
    return paper


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="列出所有 pending 论文与候选")

    ap = sub.add_parser("accept", help="接受一个候选并回填")
    ap.add_argument("paper_id", type=int)
    ap.add_argument("--idx", type=int, help="候选序号（1-based，见 list 输出）")
    ap.add_argument("--key", type=str, help="直接指定 DBLP key（conf/venue/year/xxx）")

    rp = sub.add_parser("reject", help="拒绝：确认无正式版")
    rp.add_argument("paper_id", type=int)

    args = parser.parse_args(argv)
    db = SessionLocal()
    try:
        if args.cmd == "list":
            papers = list_pending(db)
            if not papers:
                print("无 pending 论文")
                return 0
            for p in papers:
                print(f"[{p.id}] {p.title}（{p.year or '?'}）{p.arxiv_url or ''}")
                for i, c in enumerate(p.match_candidates or [], 1):
                    print(f"    {i}. {c.get('venue_short_name') or '?'} {c.get('key')} "
                          f"({c.get('year') or '?'}) doi={c.get('doi') or '-'}")
            print(f"\n共 {len(papers)} 篇待复核")
        elif args.cmd == "accept":
            accept_candidate(db, args.paper_id, index=args.idx, key=args.key)
        elif args.cmd == "reject":
            reject_paper(db, args.paper_id)
        return 0
    except ValueError as e:
        print(f"错误：{e}", file=sys.stderr)
        return 1
    except sa_exc.IntegrityError as e:
        db.rollback()
        print(f"错误：DBLP key 冲突（可能已被其他论文使用）：{e.orig}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
