"""APScheduler 每日定时任务：挂载于 FastAPI 生命周期（DR-008）。

说明：CRAWL_SCHEDULE_HOUR/MINUTE 语义为北京时间；scheduler 内部用 UTC，
避免 Windows 上 tzdata 缺失导致时区解析失败（北京时间 09:30 = UTC 01:30）。
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.crawler.pipeline import run_pipeline
from app.db import SessionLocal

logger = logging.getLogger(__name__)

_BEIJING_OFFSET_HOURS = 8


def run_crawl_job() -> None:
    """定时任务的执行体：独立 session，异常只记录不中断调度器。"""
    db = SessionLocal()
    try:
        run_pipeline(db)
    except Exception:
        logger.exception("scheduled crawl failed")
    finally:
        db.close()


def create_scheduler() -> BackgroundScheduler:
    utc_hour = (settings.crawl_schedule_hour - _BEIJING_OFFSET_HOURS) % 24
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        run_crawl_job,
        CronTrigger(hour=utc_hour, minute=settings.crawl_schedule_minute),
        id="daily_crawl",
        replace_existing=True,
    )
    logger.info("scheduler: daily crawl at %02d:%02d Beijing time", settings.crawl_schedule_hour, settings.crawl_schedule_minute)
    return scheduler
