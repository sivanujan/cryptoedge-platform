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
            wait_signals = db.query(Signal).filter_by(status='wait').all()
            for sig in active_signals + wait_signals:
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

            # --- Check if wait signals should become active ---
            for sig in wait_signals:
                if not sig.coin or sig.coin.symbol not in enhanced_data:
                    continue
                
                curr_price = enhanced_data[sig.coin.symbol]["last"]
                if not curr_price or not sig.entry_price:
                    continue
                
                is_buy = sig.signal_type == "BUY"
                activated = False
                cancelled = False
                
                # 1. Historical check (catches hits while offline/overnight)
                try:
                    from services.binance_service import get_ohlcv
                    import pandas as pd
                    # 15m candles to cover past 2 days
                    df = get_ohlcv(sig.coin.symbol, timeframe="15m", limit=200)
                    if df is not None and not df.empty and sig.created_at:
                        # timezone naive created_at
                        recent_df = df[df.index >= pd.to_datetime(sig.created_at).tz_localize(None)]
                        for _, row in recent_df.iterrows():
                            high = float(row["high"])
                            low = float(row["low"])
                            if is_buy:
                                if sig.stop_loss and low <= sig.stop_loss:
                                    cancelled = True
                                    break
                                elif low <= sig.entry_price:
                                    activated = True
                                    break
                            else: # SELL
                                if sig.stop_loss and high >= sig.stop_loss:
                                    cancelled = True
                                    break
                                elif high >= sig.entry_price:
                                    activated = True
                                    break
                except Exception as e:
                    logger.warning(f"Historical check error for {sig.coin.symbol}: {e}")
                
                # 2. Live check if not triggered historically
                if not activated and not cancelled:
                    if is_buy:
                        if sig.stop_loss and curr_price <= sig.stop_loss:
                            cancelled = True
                        elif curr_price <= sig.entry_price:
                            activated = True
                    else: # SELL
                        if sig.stop_loss and curr_price >= sig.stop_loss:
                            cancelled = True
                        elif curr_price >= sig.entry_price:
                            activated = True
                        
                if cancelled:
                    sig.status = "cancelled"
                    logger.info(f"Signal {sig.id} for {sig.coin.symbol} cancelled because SL was reached before entry.")
                elif activated:
                    sig.status = "active"
                    logger.info(f"Signal {sig.id} for {sig.coin.symbol} activated at price {curr_price}")
                    active_signals.append(sig)

            # --- Check TP / SL for active signals ---
            from services.telegram_service import send_telegram_message
            from database.models import Trade
            from datetime import datetime

            for sig in active_signals:
                if not sig.coin or sig.coin.symbol not in enhanced_data:
                    continue
                
                curr_price = enhanced_data[sig.coin.symbol]["last"]
                if not curr_price or not sig.entry_price:
                    continue
                
                is_buy = sig.signal_type == "BUY"
                hit_tp = False
                hit_sl = False
                exit_price = curr_price

                # 1. Historical check (catches TP/SL hits while offline/overnight)
                try:
                    from services.binance_service import get_ohlcv
                    import pandas as pd
                    df = get_ohlcv(sig.coin.symbol, timeframe="15m", limit=200)
                    if df is not None and not df.empty and sig.created_at:
                        # Only check candles since signal was created
                        recent_df = df[df.index >= pd.to_datetime(sig.created_at).tz_localize(None)]
                        for _, row in recent_df.iterrows():
                            high = float(row["high"])
                            low = float(row["low"])
                            if is_buy:
                                if sig.take_profit and high >= sig.take_profit:
                                    hit_tp = True
                                    exit_price = sig.take_profit
                                    break
                                elif sig.stop_loss and low <= sig.stop_loss:
                                    hit_sl = True
                                    exit_price = sig.stop_loss
                                    break
                            else: # SELL
                                if sig.take_profit and low <= sig.take_profit:
                                    hit_tp = True
                                    exit_price = sig.take_profit
                                    break
                                elif sig.stop_loss and high >= sig.stop_loss:
                                    hit_sl = True
                                    exit_price = sig.stop_loss
                                    break
                except Exception as e:
                    logger.warning(f"Historical TP/SL check error for {sig.coin.symbol}: {e}")

                # 2. Live check if not triggered historically
                if not hit_tp and not hit_sl:
                    if is_buy:
                        if sig.take_profit and curr_price >= sig.take_profit:
                            hit_tp = True
                            exit_price = sig.take_profit
                        elif sig.stop_loss and curr_price <= sig.stop_loss:
                            hit_sl = True
                            exit_price = sig.stop_loss
                    else: # SELL
                        if sig.take_profit and curr_price <= sig.take_profit:
                            hit_tp = True
                            exit_price = sig.take_profit
                        elif sig.stop_loss and curr_price >= sig.stop_loss:
                            hit_sl = True
                            exit_price = sig.stop_loss

                if hit_tp or hit_sl:
                    # Calculate PnL
                    if is_buy:
                        pnl_pct = (exit_price - sig.entry_price) / sig.entry_price * 100
                    else:
                        pnl_pct = (sig.entry_price - exit_price) / sig.entry_price * 100

                    # Update signal
                    new_status = "closed" if hit_tp else "stopped"
                    sig.status = new_status

                    # Create trade record
                    trade = Trade(
                        coin_id=sig.coin.id,
                        signal_id=sig.id,
                        entry_price=sig.entry_price,
                        exit_price=exit_price,
                        pnl_percent=round(pnl_pct, 2),
                        status=new_status,
                        opened_at=sig.created_at or datetime.utcnow(),
                        closed_at=datetime.utcnow()
                    )
                    db.add(trade)

                    # Send Telegram Notification
                    emoji = "✅" if hit_tp else "❌"
                    target_hit = "TAKE PROFIT" if hit_tp else "STOP LOSS"
                    clean_symbol = sig.coin.symbol.split(':')[0].replace('/', '')
                    
                    msg = (
                        f"{emoji} <b>{target_hit} HIT</b> {emoji}\n\n"
                        f"<b>Coin:</b> #{clean_symbol}\n"
                        f"<b>Type:</b> {sig.signal_type}\n"
                        f"<b>Strategy:</b> {sig.strategy.name if sig.strategy else 'Unknown'}\n\n"
                        f"🎯 <b>Entry:</b> ${sig.entry_price:,.4f}\n"
                        f"💰 <b>Exit:</b> ${exit_price:,.4f}\n"
                        f"📊 <b>P&L:</b> {pnl_pct:+.2f}%\n"
                    )
                    try:
                        send_telegram_message(msg)
                    except Exception as e:
                        logger.error(f"Failed to send TP/SL Telegram alert: {e}")
            
            db.commit()
            # --- End TP / SL check ---

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
