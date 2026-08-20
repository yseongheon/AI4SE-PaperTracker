"""关键词初筛（管线阶段④，M2）：keyword_rules 表驱动，免费、可解释。

规则数据存库（seed_keyword_rules 导入），匹配逻辑：
- pattern 用 | 分隔同义多词，任一子串命中即算命中（大小写不敏感）
- field: title 只匹配标题 / abstract 只匹配摘要 / any 两者皆可
- 命中任一规则 → is_ai4se_candidate=True，并按命中的主题写 paper_topics
  （method=keyword, confidence=0.6）——多标签，可追溯，重跑幂等（先清后写）
"""
import logging
from collections import Counter

from sqlalchemy.orm import Session

from app.models import KeywordRule, Paper, PaperTopic, Topic

logger = logging.getLogger(__name__)

KEYWORD_CONFIDENCE = 0.6  # 关键词命中置信度（LLM 精标会覆盖为更高置信度）


def load_rules(db: Session) -> list[KeywordRule]:
    """加载全部启用规则（join Topic 拿 slug）。"""
    return (
        db.query(KeywordRule)
        .filter(KeywordRule.enabled.is_(True))
        .order_by(KeywordRule.id)
        .all()
    )


def _normalized_patterns(pattern: str) -> list[str]:
    """pattern 按 | 拆分、去空白、小写（匹配用子串，大小写不敏感）。"""
    return [p.strip().lower() for p in pattern.split("|") if p.strip()]


def match_paper(
    title: str | None, abstract: str | None, rules: list[KeywordRule]
) -> dict[int, list[str]]:
    """对单篇论文跑全部规则：返回 {topic_id: [命中词...]}（可多主题多词命中）。"""
    title_l = (title or "").lower()
    abstract_l = (abstract or "").lower()
    hits: dict[int, list[str]] = {}
    for rule in rules:
        if rule.topic_id is None:
            continue
        for word in _normalized_patterns(rule.pattern):
            if rule.field == "title":
                matched = word in title_l
            elif rule.field == "abstract":
                matched = word in abstract_l
            else:  # any
                matched = word in title_l or word in abstract_l
            if matched:
                hits.setdefault(rule.topic_id, []).append(rule.pattern)
                break  # 该规则任一词命中即可，避免同规则多词重复计数
    return hits


def run_keyword_screen(db: Session, only_candidates: bool = False) -> dict:
    """全量（或仅候选）扫描论文执行初筛，返回统计。

    幂等：对每篇论文先清除旧的 keyword 标签再写入新命中的；重复运行结果一致。
    """
    rules = load_rules(db)
    if not rules:
        logger.warning("keyword_rules 为空，请先运行 seed_keyword_rules")
        return {"scanned": 0, "candidates": 0, "by_topic": {}}

    query = db.query(Paper)
    if only_candidates:
        query = query.filter(Paper.is_ai4se_candidate.is_(True))
    # 已分类论文的 LLM 标签即最终结果，跳过以免重插 keyword 标签撞 (paper_id, topic_id) 唯一约束
    query = query.filter(Paper.status != "classified")
    papers = query.all()

    topic_counts: Counter = Counter()
    screened = 0
    for paper in papers:
        hits = match_paper(paper.title, paper.abstract, rules)
        # 清旧 keyword 标签再写新命中（幂等重跑）
        db.query(PaperTopic).filter(
            PaperTopic.paper_id == paper.id, PaperTopic.method == "keyword"
        ).delete(synchronize_session=False)
        if hits:
            paper.is_ai4se_candidate = True
            for topic_id, words in hits.items():
                db.add(
                    PaperTopic(
                        paper_id=paper.id,
                        topic_id=topic_id,
                        confidence=KEYWORD_CONFIDENCE,
                        method="keyword",
                    )
                )
                topic_counts[topic_id] += 1
            screened += 1
        else:
            # 未命中保持候选状态不变（LLM 已判定过的论文不因初筛重跑降级）
            pass
    db.commit()

    slug_counts = _topic_slugs(db, topic_counts)
    logger.info(
        "keyword screen done: scanned=%d candidates=%d topics=%s",
        len(papers),
        screened,
        dict(slug_counts),
    )
    return {
        "scanned": len(papers),
        "candidates": screened,
        "by_topic": dict(slug_counts),
    }


def _topic_slugs(db: Session, counts: Counter) -> dict[str, int]:
    if not counts:
        return {}
    slug_by_id = {t.id: t.slug for t in db.query(Topic).all()}
    return {slug_by_id.get(tid, str(tid)): n for tid, n in counts.most_common()}
