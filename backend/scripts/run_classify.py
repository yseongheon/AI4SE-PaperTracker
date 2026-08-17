"""批量分类：④ 关键词初筛 → ⑤ DeepSeek 精标（M2）。

用法（cd backend）：
- python -m scripts.run_classify            # 初筛 + 精标全部未处理候选
- python -m scripts.run_classify --dry-run  # 只统计候选数与预估成本，不调用 API
- python -m scripts.run_classify --limit 20 # 试跑前 20 篇
- python -m scripts.run_classify --reclassify  # 重标已精标过的候选（覆盖）

成本控制（DR-019 授权内自主决策）：
- 精标范围 = 关键词初筛候选（DR-018），不处理全库
- CostTracker 跨运行累计（data/llm_cost.json），超 LLM_COST_LIMIT_USD 自动停止
- 并发 2（DeepSeek 限流红线），失败重试 2 次后跳过并记录
- --dry-run 估算成本后需人工确认全量（一次性 >$0.5 时）
"""
import argparse
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from app.crawler.classifier import CostLimitExceeded, CostTracker, DeepSeekClassifier
from app.crawler.keyword_rules import run_keyword_screen
from app.db import SessionLocal
from app.models import CrawlRun, Paper, PaperTopic, Topic
from scripts.seed_keyword_rules import seed_keyword_rules

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

LLM_CONCURRENCY = 2  # DeepSeek 并发上限（红线）
EST_INPUT_TOKENS = 600  # 单篇估算输入 token（标题+摘要）
EST_OUTPUT_TOKENS = 300  # 单篇估算输出 token（JSON+摘要）
EST_COST_PER_PAPER = (
    EST_INPUT_TOKENS / 1e6 * 0.27 + EST_OUTPUT_TOKENS / 1e6 * 1.10
)  # ≈ $0.00046/篇


def _pending_candidates(db, reclassify: bool, limit: int | None) -> list[Paper]:
    """待精标候选：is_ai4se_candidate=True；默认只取未精标过的。"""
    q = db.query(Paper).filter(Paper.is_ai4se_candidate.is_(True))
    if not reclassify:
        q = q.filter(Paper.status != "classified")
    q = q.order_by(Paper.id)
    if limit:
        q = q.limit(limit)
    return q.all()


def _apply_result(db, paper: Paper, result) -> None:
    """精标结果回写：确认标记 / 中文摘要 / llm 标签。

    paper_topics 主键是 (paper_id, topic_id)——LLM 是最终权威，先删除该论文
    全部旧标签（keyword+llm）再写 llm 标签，避免唯一约束冲突与旧标签残留。
    """
    paper.is_ai4se_confirmed = result.is_ai4se
    paper.summary_zh = result.summary_zh if result.is_ai4se else None
    paper.status = "classified"
    db.query(PaperTopic).filter(PaperTopic.paper_id == paper.id).delete(
        synchronize_session=False
    )
    if result.is_ai4se:
        slug_to_id = {t.slug: t.id for t in db.query(Topic).all()}
        for slug in result.topics:
            tid = slug_to_id.get(slug)
            if tid is None:
                continue
            db.add(
                PaperTopic(
                    paper_id=paper.id,
                    topic_id=tid,
                    confidence=result.confidence,
                    method="llm",
                )
            )


def run_classify(
    dry_run: bool = False,
    limit: int | None = None,
    reclassify: bool = False,
) -> dict:
    db = SessionLocal()
    try:
        added, existing = seed_keyword_rules(db)
        if added:
            logger.info("seeded %d new keyword rules", added)
        screen = run_keyword_screen(db)
        candidates = _pending_candidates(db, reclassify, limit)
        logger.info(
            "candidates to classify: %d (screen: %d candidates / %d scanned)",
            len(candidates),
            screen["candidates"],
            screen["scanned"],
        )

        est_cost = len(candidates) * EST_COST_PER_PAPER
        tracker = CostTracker()
        if dry_run:
            logger.info(
                "DRY-RUN: %d papers → est cost $%.4f (limit $%.2f, already spent $%.4f)",
                len(candidates),
                est_cost,
                tracker.limit_usd,
                tracker.total_usd,
            )
            return {"candidates": len(candidates), "est_cost_usd": round(est_cost, 4)}

        if not candidates:
            logger.info("no candidates to classify")
            return {"classified": 0, "confirmed": 0, "failed": 0, "cost_usd": 0.0}

        if est_cost > 0.5 and not reclassify:
            logger.info(
                "est cost $%.3f for %d papers (within $%.2f limit) — proceed",
                est_cost,
                len(candidates),
                tracker.limit_usd,
            )

        run = CrawlRun(source="llm", status="running")
        db.add(run)
        db.commit()

        lock = threading.Lock()
        stop = threading.Event()
        classified = confirmed = failed = 0

        def worker(paper_ids: list[int]) -> None:
            nonlocal classified, confirmed, failed
            local_db = SessionLocal()
            try:
                classifier = DeepSeekClassifier(cost=tracker)
                for pid in paper_ids:
                    if stop.is_set():
                        return
                    paper = local_db.query(Paper).get(pid)
                    if paper is None:
                        continue
                    try:
                        result = classifier.classify(
                            paper.title, paper.abstract, paper.year
                        )
                        with lock:
                            if result is not None:
                                _apply_result(local_db, paper, result)
                                classified += 1
                                confirmed += 1 if result.is_ai4se else 0
                                local_db.commit()
                            else:
                                failed += 1
                                logger.warning("classify failed (skipped): id=%d", pid)
                    except CostLimitExceeded:
                        logger.error("COST LIMIT reached: %s", classifier.cost.total_usd)
                        stop.set()
                        return
            finally:
                local_db.close()

        ids = [p.id for p in candidates]
        chunk = max(1, len(ids) // (LLM_CONCURRENCY * 2))
        chunks = [ids[i : i + chunk] for i in range(0, len(ids), chunk)]

        with ThreadPoolExecutor(max_workers=LLM_CONCURRENCY) as pool:
            futures = [pool.submit(worker, c) for c in chunks]
            for f in as_completed(futures):
                try:
                    f.result()
                except Exception:
                    logger.exception("worker crashed")

        tracker.save()
        run.status = "success" if not stop.is_set() else "stopped(cost limit)"
        run.fetched_count = classified + failed
        run.new_count = confirmed
        run.updated_count = classified - confirmed
        run.failed_count = failed
        run.finished_at = datetime.utcnow()
        db.commit()

        logger.info(
            "classify done: %d classified, %d confirmed AI4SE, %d failed, cost $%.4f (total $%.4f)",
            classified,
            confirmed,
            failed,
            tracker.session_usd,
            tracker.total_usd,
        )
        return {
            "classified": classified,
            "confirmed": confirmed,
            "failed": failed,
            "cost_usd": round(tracker.session_usd, 4),
        }
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="关键词初筛 + DeepSeek 精标")
    parser.add_argument("--dry-run", action="store_true", help="只统计候选与成本估算，不调用 API")
    parser.add_argument("--limit", type=int, default=None, help="最多精标 N 篇（试跑）")
    parser.add_argument("--reclassify", action="store_true", help="重标已精标过的候选")
    args = parser.parse_args()
    stats = run_classify(dry_run=args.dry_run, limit=args.limit, reclassify=args.reclassify)
    logger.info("stats: %s", stats)
