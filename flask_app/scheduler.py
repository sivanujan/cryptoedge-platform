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

    # ── Active Prices Broadcaster (15s) ────────────────────────
    scheduler.add_job(
        _broadcast_active_prices_sync,
        trigger=IntervalTrigger(seconds=15),
        id="price_broadcaster",
        name="Active Prices Broadcaster",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(f"Scheduler started. Main scanner runs every {interval_minutes} min. Breakout scanner runs every 15 min. Price job runs every 15s.")

def _broadcast_active_prices_sync():
    """Fetch and broadcast prices for BTC and all active signal symbols."""
    import time
    from services.binance_service import get_multiple_tickers
    from services.scanner_service import broadcast_price
    from database.connection import SessionLocal
    from database.models import Signal, Coin
    
    start_time = time.time()
    db = SessionLocal()
    try:
        # Always include BTC/USDT for context, plus symbols for all active signals
        symbols = {"BTC/USDT"}
        try:
            active_signals = db.query(Signal).filter_by(status='active').all()
            for sig in active_signals:
                if sig.coin and sig.coin.symbol:
                    symbols.add(sig.coin.symbol)
        except Exception as e:
            logger.error(f"Error querying active signals for price job: {e}")

        symbols_list = list(symbols)
        logger.info(f"Price job: Fetching {len(symbols_list)} symbols...")
        
        ticker_data = get_multiple_tickers(symbols_list)
        
        if ticker_data:
            # Map ticker data to include multiple field names for frontend compatibility (last, price, current_price)
            enhanced_data = {}
            for sym, data in ticker_data.items():
                price = data.get('last')
                pct = data.get('percentage')
                enhanced_data[sym] = {
                    "last": price,
                    "price": price,
                    "current_price": price,
                    "percentage": pct,
                    "change": pct,
                    "price_change_percent": pct
                }
            
            broadcast_price({
                "type": "prices",
                "data": enhanced_data
            })
            duration = time.time() - start_time
            has_evaa = "EVAA/USDT:USDT" in enhanced_data
            evaa_p = enhanced_data.get("EVAA/USDT:USDT") if has_evaa else "N/A"
            logger.info(f"Price job: Broadcasted {len(enhanced_data)} tickers in {duration:.2f}s. EVAA: {evaa_p}")
        else:
            logger.warning("Price job: No ticker data fetched.")
            
    except Exception as e:
        logger.error(f"[PRICE JOB] Error: {e}")
    finally:
        db.close()


def stop_scheduler():
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
