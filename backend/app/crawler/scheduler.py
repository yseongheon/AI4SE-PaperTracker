"""APScheduler 定时任务：每日爬取 + 每周五周报（DR-008 + M6）。

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
_WEEKLY_REPORT_HOUR_BJ = 9  # 每周五 09:30（北京时间）
_WEEKLY_REPORT_MINUTE_BJ = 30


def run_crawl_job() -> None:
    """每日爬取执行体：独立 session，异常只记录不中断调度器。"""
    db = SessionLocal()
    try:
        run_pipeline(db)
    except Exception:
        logger.exception("scheduled crawl failed")
    finally:
        db.close()


def run_weekly_report_job() -> None:
    """每周五周报执行体（M6）：延迟导入 scripts 避免启动耦合。"""
    db = SessionLocal()
    try:
        from scripts.weekly_report import generate_weekly_report

        path = generate_weekly_report(db)
        logger.info("weekly report generated: %s", path)
    except Exception:
        logger.exception("scheduled weekly report failed")
    finally:
        db.close()


def run_personal_report_job() -> None:
    """每周五个人收藏周报执行体（M9）：为每个有收藏的用户生成。"""
    db = SessionLocal()
    try:
        from scripts.personal_report import generate_personal_reports

        written = generate_personal_reports(db)
        logger.info("personal reports generated: %d users", len(written))
    except Exception:
        logger.exception("scheduled personal report failed")
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
    # M6 周报 + M9 个人周报：每周五 09:30 北京时间 = UTC 周五 01:30
    scheduler.add_job(
        run_weekly_report_job,
        CronTrigger(
            hour=(_WEEKLY_REPORT_HOUR_BJ - _BEIJING_OFFSET_HOURS) % 24,
            minute=_WEEKLY_REPORT_MINUTE_BJ,
            day_of_week="fri",
        ),
        id="weekly_report",
        replace_existing=True,
    )
    scheduler.add_job(
        run_personal_report_job,
        CronTrigger(
            hour=(_WEEKLY_REPORT_HOUR_BJ - _BEIJING_OFFSET_HOURS) % 24,
            minute=(_WEEKLY_REPORT_MINUTE_BJ + 5) % 60,
            day_of_week="fri",
        ),
        id="personal_report",
        replace_existing=True,
    )
    logger.info(
        "scheduler: daily crawl at %02d:%02d Beijing time; weekly report at Fri %02d:%02d",
        settings.crawl_schedule_hour,
        settings.crawl_schedule_minute,
        _WEEKLY_REPORT_HOUR_BJ,
        _WEEKLY_REPORT_MINUTE_BJ,
    )
    return scheduler
