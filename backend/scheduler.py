import logging
import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
    return _scheduler


def start_scheduler():
    """Start APScheduler with the scanner job."""
    from services.scanner_service import run_scanner

    interval_minutes = int(os.getenv("SCANNER_INTERVAL_MINUTES", 15))
    scheduler = get_scheduler()

    if scheduler.running:
        logger.info("Scheduler already running.")
        return

    scheduler.add_job(
        run_scanner,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="scanner_job",
        name="Live Market Scanner",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info(f"Scheduler started. Scanner runs every {interval_minutes} minutes.")


def stop_scheduler():
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
