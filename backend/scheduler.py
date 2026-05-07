import logging
import os
import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler = None


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
    return _scheduler


def _run_breakout_scanner_sync():
    """Sync wrapper for the async breakout scanner (APScheduler is sync)."""
    try:
        asyncio.run(_run_breakout_async())
    except Exception as e:
        logger.error(f"[BREAKOUT JOB] Error: {e}")


async def _run_breakout_async():
    from scanner.breakout_scanner import run_breakout_scanner
    await run_breakout_scanner()


def start_scheduler():
    """Start APScheduler with the scanner job."""
    from services.scanner_service import run_scanner

    interval_minutes = int(os.getenv("SCANNER_INTERVAL_MINUTES", 15))
    scheduler = get_scheduler()

    if scheduler.running:
        logger.info("Scheduler already running.")
        return

    # ── Existing live signal scanner ───────────────────────────
    scheduler.add_job(
        run_scanner,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="scanner_job",
        name="Live Market Scanner",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    # ── Breakout Scanner ───────────────────────────────────────
    scheduler.add_job(
        _run_breakout_scanner_sync,
        trigger=IntervalTrigger(minutes=15),
        id="breakout_scanner",
        name="Breakout Signal Scanner",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()
    logger.info(f"Scheduler started. Main scanner runs every {interval_minutes} min. Breakout scanner runs every 15 min.")


def stop_scheduler():
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
