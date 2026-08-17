"""导入关键词初筛规则（keyword_rules 表，M2 启用）。

设计（DR-019 授权内自主决策）：
- 每个主题配「强词」规则，命中任一即标记 is_ai4se_candidate 并打该主题标签（method=keyword）
- pattern 支持用 | 分隔同义多词；field: title/abstract/any
- 规则是数据：入库后可增删改，无需改代码；重跑幂等（按 pattern+field 去重）
- llm4se_general 使用 LLM 相关强词而非泛化词（deep learning 等），控制候选规模与噪声
- other 主题不设规则：由 LLM 精标兜底（AI4SE 但无合适主题时归入）

用法：cd backend && python -m scripts.seed_keyword_rules
"""
import logging

from app.db import SessionLocal
from app.models import KeywordRule, Topic

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# (topic_slug, pattern, field) —— pattern 中 | 分隔同义词，匹配任一即命中
RULES: list[tuple[str, str, str]] = [
    # ---- 代码生成 ----
    ("code_generation", "code generation | code-generation | codegen", "any"),
    ("code_generation", "program synthesis", "any"),
    ("code_generation", "code completion", "any"),
    ("code_generation", "text to code | text-to-code", "any"),
    ("code_generation", "generating code", "any"),
    # ---- 代码修复 ----
    ("code_repair", "program repair", "any"),
    ("code_repair", "bug fix | bugfix | bug fixing | fixing bugs", "any"),
    ("code_repair", "automated repair | auto repair", "any"),
    ("code_repair", "code repair", "any"),
    ("code_repair", "patch generation", "any"),
    # ---- 代码翻译 ----
    ("code_translation", "code translation", "any"),
    ("code_translation", "code migration | program migration", "any"),
    ("code_translation", "transpil", "any"),
    ("code_translation", "cross-language | cross language", "any"),
    # ---- 代码摘要 ----
    ("code_summarization", "code summarization | code summary", "any"),
    ("code_summarization", "comment generation", "any"),
    ("code_summarization", "docstring", "any"),
    ("code_summarization", "code documentation", "any"),
    ("code_summarization", "code explanation", "any"),
    # ---- 缺陷检测与定位 ----
    ("defect_detection", "defect prediction", "any"),
    ("defect_detection", "vulnerability detection | vulnerability discovery | vulnerability prediction", "any"),
    ("defect_detection", "fault localization | bug localization", "any"),
    ("defect_detection", "bug detection | defect detection", "any"),
    ("defect_detection", "crash reproduction", "any"),
    ("defect_detection", "security vulnerability", "any"),
    # ---- 自动化测试 ----
    ("testing", "test generation | test case generation", "any"),
    ("testing", "automated testing | automated test", "any"),
    ("testing", "fuzz", "any"),
    ("testing", "unit test", "any"),
    ("testing", "test oracle", "any"),
    ("testing", "metamorphic testing", "any"),
    ("testing", "test repair", "any"),
    ("testing", "test prioritization | test selection", "any"),
    # ---- 软件分析 ----
    ("analysis", "program analysis", "any"),
    ("analysis", "static analysis", "any"),
    ("analysis", "dynamic analysis", "any"),
    ("analysis", "symbolic execution", "any"),
    ("analysis", "type inference", "any"),
    ("analysis", "code analysis", "any"),
    # ---- 需求工程 ----
    ("requirements", "requirements engineering", "any"),
    ("requirements", "requirement generation | requirements generation", "any"),
    ("requirements", "specification generation", "any"),
    ("requirements", "requirements analysis", "any"),
    ("requirements", "user story", "any"),
    # ---- LLM4SE 通用 ----
    ("llm4se_general", "large language model | llm | llms", "any"),
    ("llm4se_general", "foundation model", "any"),
    ("llm4se_general", "chatgpt | gpt-4 | gpt-3.5 | gpt4", "any"),
    ("llm4se_general", "code llm | llm-based | llm based", "any"),
    ("llm4se_general", "codebert | codegpt | codet5 | codex", "any"),
]


def seed_keyword_rules(db) -> tuple[int, int]:
    """幂等 upsert：返回 (新增数, 已存在数)。"""
    added = 0
    existing = 0
    slug_to_id = {t.slug: t.id for t in db.query(Topic).all()}
    for slug, pattern, field in RULES:
        topic_id = slug_to_id.get(slug)
        if topic_id is None:
            logger.warning("topic %s not found, skip rule %s", slug, pattern)
            continue
        rule = (
            db.query(KeywordRule)
            .filter_by(pattern=pattern, field=field, topic_id=topic_id)
            .first()
        )
        if rule is None:
            db.add(KeywordRule(topic_id=topic_id, pattern=pattern, field=field))
            added += 1
        else:
            existing += 1
    db.commit()
    return added, existing


if __name__ == "__main__":
    db = SessionLocal()
    try:
        added, existing = seed_keyword_rules(db)
        logger.info("seed_keyword_rules done: %d added, %d existed", added, existing)
    finally:
        db.close()
