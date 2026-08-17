"""导入 CCF-A 软件工程会议名单（DR-003：ICSE/FSE/ASE/ISSTA）。

幂等：按 dblp_key upsert，可重复执行。
用法：cd backend && python -m scripts.seed_venues
"""
import logging

from app.db import SessionLocal
from app.models import Venue

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# short_name | full_name | dblp_key（DBLP stream 名，匹配器按此批量拉取）
CCF_A_SE_VENUES = [
    (
        "ICSE",
        "International Conference on Software Engineering",
        "conf/icse",
    ),
    (
        "FSE",
        "ACM International Conference on the Foundations of Software Engineering (ESEC/FSE)",
        "conf/fse",
    ),
    (
        "ASE",
        "IEEE/ACM International Conference on Automated Software Engineering",
        "conf/ase",
    ),
    (
        "ISSTA",
        "ACM SIGSOFT International Symposium on Software Testing and Analysis",
        "conf/issta",
    ),
]


def seed_venues(db) -> int:
    upserted = 0
    for short_name, full_name, dblp_key in CCF_A_SE_VENUES:
        venue = db.query(Venue).filter_by(dblp_key=dblp_key).first()
        if venue is None:
            db.add(
                Venue(
                    short_name=short_name,
                    full_name=full_name,
                    type="conference",
                    rank="A",
                    dblp_key=dblp_key,
                )
            )
            upserted += 1
            logger.info("added venue: %s (%s)", short_name, dblp_key)
        else:
            logger.info("venue exists: %s (%s)", short_name, dblp_key)
    db.commit()
    return upserted


if __name__ == "__main__":
    db = SessionLocal()
    try:
        n = seed_venues(db)
        logger.info("seed_venues done: %d added", n)
    finally:
        db.close()
