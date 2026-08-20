"""导入机构别名库（机构功能：alias→canonical 数据驱动合并库）。

幂等：按 alias upsert，可重复执行。别名库是数据不是代码，课题组可直接增删改。
所有 key 均为 normalize_institution 归一化后的完整机构串（小写），与
paper_authors.affiliation 存值精确匹配——这是契约，不要写入未归一化字符串。

用法：cd backend && python -m scripts.seed_institution_aliases
"""
import logging

from app.db import SessionLocal
from app.models import InstitutionAlias

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# (alias, canonical, note) —— 全部来自真实库数据的精确变体
ALIASES = [
    (
        "school of computing, university of south china, hengyang, 421001, china",
        "school of computing, university of south china, hengyang, china",
        "邮政编号后缀变体",
    ),
    (
        "university of belgrade, faculty of organizational sciences, belgrade, serbia",
        "university of belgrade, faculty of organizational sciences",
        "城市/国家后缀变体",
    ),
    ("the university of warwick", "university of warwick", "冠词 the 变体"),
    ("ip paris, aces, ltci, infres", "ip paris, ltci, aces, infres", "实验室排列变体"),
    ("ip paris, ltci", "ip paris, ltci, aces, infres", "实验室简写变体"),
    ("epita, lre", "lre, epita", "实验室排列变体"),
    ("lre", "lre, epita", "实验室简写变体"),
    ("diverse, ur, cnrs, irisa", "ur, cnrs, irisa, diverse", "实验室排列变体"),
    ("ur, irisa, diverse", "ur, cnrs, irisa, diverse", "实验室排列变体"),
    ("cnrs, iuf, irisa, ur, diverse", "ur, cnrs, irisa, diverse", "实验室排列变体"),
]


def seed_institution_aliases(db) -> int:
    upserted = 0
    for alias, canonical, note in ALIASES:
        row = db.query(InstitutionAlias).filter_by(alias=alias).first()
        if row is None:
            db.add(InstitutionAlias(alias=alias, canonical=canonical, note=note))
            upserted += 1
            logger.info("added alias: %s -> %s", alias, canonical)
        elif row.canonical != canonical:
            row.canonical = canonical  # 幂等：已存在但 canonical 变了则更新
            upserted += 1
            logger.info("updated alias: %s -> %s", alias, canonical)
    db.commit()
    return upserted


if __name__ == "__main__":
    db = SessionLocal()
    try:
        n = seed_institution_aliases(db)
        logger.info("seed_institution_aliases done: %d added/updated", n)
    finally:
        db.close()
