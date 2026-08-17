"""导入初版主题分类法（10 主题，见 CLAUDE.md 第 5 章 topics 表）。

幂等：按 slug upsert，可重复执行；主题分类法是数据，可增删改。
用法：cd backend && python -m scripts.seed_topics
"""
import logging

from app.db import SessionLocal
from app.models import Topic

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TOPICS = [
    ("code_generation", "代码生成", "用 LLM/深度学习生成代码、程序合成"),
    ("code_repair", "代码修复", "自动化程序修复、缺陷修复、错误定位修复"),
    ("code_translation", "代码翻译", "跨语言代码转换、迁移"),
    ("code_summarization", "代码摘要", "代码注释生成、文档生成、摘要"),
    ("defect_detection", "缺陷检测与定位", "缺陷预测、漏洞检测、故障定位"),
    ("testing", "自动化测试", "测试用例生成、测试优化、模糊测试"),
    ("analysis", "软件分析", "程序分析、静态分析、类型推断"),
    ("requirements", "需求工程", "需求建模、需求分析、规格生成"),
    ("llm4se_general", "LLM4SE 通用", "大模型应用于软件工程的综合/框架/调研类"),
    ("other", "其他", "其他 AI4SE 相关主题"),
]


def seed_topics(db) -> int:
    upserted = 0
    for slug, name_zh, description in TOPICS:
        topic = db.query(Topic).filter_by(slug=slug).first()
        if topic is None:
            db.add(Topic(slug=slug, name_zh=name_zh, description=description))
            upserted += 1
            logger.info("added topic: %s (%s)", slug, name_zh)
        else:
            logger.info("topic exists: %s", slug)
    db.commit()
    return upserted


if __name__ == "__main__":
    db = SessionLocal()
    try:
        n = seed_topics(db)
        logger.info("seed_topics done: %d added", n)
    finally:
        db.close()
