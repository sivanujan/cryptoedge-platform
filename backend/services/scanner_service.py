import asyncio
import logging
from datetime import datetime
from typing import List, Set

from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models import CoinStrategyMap, Signal, Coin, Strategy
from services.binance_service import get_ohlcv, get_current_price
from services.indicator_service import add_all_indicators
from strategies.golden_cross import get_strategy
from services.telegram_service import send_telegram_message

logger = logging.getLogger(__name__)

# Global WebSocket client registry
_price_connections: Set = set()
_signal_connections: Set = set()

main_loop = None
def set_main_loop(loop):
    global main_loop
    main_loop = loop


def register_price_ws(ws):
    _price_connections.add(ws)


def unregister_price_ws(ws):
    _price_connections.discard(ws)


def register_signal_ws(ws):
    _signal_connections.add(ws)


def unregister_signal_ws(ws):
    _signal_connections.discard(ws)


async def broadcast_price(data: dict):
    """Send price update to all connected WebSocket clients."""
    dead = set()
    for ws in _price_connections.copy():
        try:
            await ws.send_json(data)
        except Exception:
            dead.add(ws)
    _price_connections -= dead


async def broadcast_signal(data: dict):
    """Send new signal to all connected WebSocket clients."""
    dead = set()
    for ws in _signal_connections.copy():
        try:
            await ws.send_json(data)
        except Exception:
            dead.add(ws)
    _signal_connections -= dead


def get_elite_picks_mappings(db: Session):
    """
    Replicates the 'Elite Picks' logic from the frontend.
    Returns a list of mock mapping objects with coin, strategy, and timeframe.
    """
    from database.models import BacktestResult
    from types import SimpleNamespace
    
    results = db.query(BacktestResult).filter(BacktestResult.win_rate.isnot(None)).all()
    
    valid_rows = []
    for r in results:
        if r.win_rate >= 50 and r.total_trades >= 5 and r.total_return > 0:
            trades = r.total_trades
            weight = 0.0
            if trades >= 100: weight = 1.00
            elif trades >= 50: weight = 0.90
            elif trades >= 30: weight = 0.75
            elif trades >= 20: weight = 0.60
            elif trades >= 5: weight = 0.40
            
            effective_win = r.win_rate * weight
            return_score = min(r.total_return / 40.0, 1.0) * 20.0
            final_score = effective_win + return_score
            
            valid_rows.append({
                "coin": r.coin,
                "strategy": r.strategy,
                "timeframe": r.timeframe,
                "final_score": final_score
            })
            
    coin_groups = {}
    for row in valid_rows:
        coin_id = row["coin"].id
        if coin_id not in coin_groups:
            coin_groups[coin_id] = []
        coin_groups[coin_id].append(row)
        
    final_mappings = []
    for coin_id, rows in coin_groups.items():
        best_score = max(r["final_score"] for r in rows)
        threshold = best_score * 0.70
        
        for r in rows:
            if r["final_score"] >= threshold:
                final_mappings.append(SimpleNamespace(
                    coin=r["coin"],
                    strategy=r["strategy"],
                    timeframe=r["timeframe"]
                ))
                
    return final_mappings


def run_scanner():
    """
    Main scanner loop. Called by APScheduler every 15 minutes.
    Loads elite picks mappings, runs strategies, saves signals.
    """
    logger.info("Scanner started (using Elite Picks)...")
    db: Session = SessionLocal()
    try:
        mappings = get_elite_picks_mappings(db)

        if not mappings:
            logger.warning("No elite picks mappings found, skipping scan.")
            return

        # Fetch global risk settings
        from database.models import Setting
        settings_rows = db.query(Setting).all()
        settings = {row.key: row.value for row in settings_rows}
        global_sl = float(settings.get("default_sl_pct", 2.0))
        global_tp = float(settings.get("default_tp_pct", 4.0))

        generated = 0
        for mapping in mappings:
            try:
                coin: Coin = mapping.coin
                strategy_obj: Strategy = mapping.strategy

                df = get_ohlcv(coin.symbol, mapping.timeframe, limit=300)
                if df is None or len(df) < 50:
                    continue

                df = add_all_indicators(df)
                df = df.dropna()

                strategy = get_strategy(strategy_obj, strategy_obj.parameters)
                df = strategy.generate_signals(df)

                last_signal = int(df["signal"].iloc[-1])
                # Use .item() to safely convert numpy/Series to Python scalar
                try:
                    last_confidence = float(df["confidence"].iloc[-1]) if "confidence" in df.columns else 70.0
                except (TypeError, ValueError):
                    last_confidence = 70.0

                try:
                    last_volatility = float(df["volatility_atr"].iloc[-1]) if "volatility_atr" in df.columns else None
                except (TypeError, ValueError):
                    last_volatility = None

                try:
                    last_close = float(df["close"].iloc[-1])
                except (TypeError, ValueError):
                    logger.warning(f"Could not extract close price for {coin.symbol}, skipping")
                    continue

                if last_signal in (1, -1):
                    signal_type = "BUY" if last_signal == 1 else "SELL"
                    
                    # Update strategy params with global defaults if not present
                    if "maxDrawdownPct" not in strategy.params:
                        strategy.params["maxDrawdownPct"] = global_sl

                    sl = strategy.calculate_stop_loss(last_close, signal_type)
                    # Adjust TP ratio if global TP is set
                    tp_ratio = global_tp / global_sl if global_sl > 0 else 2.0
                    tp = strategy.calculate_take_profit(last_close, signal_type, ratio=tp_ratio)

                    # Avoid duplicate signals within same candle
                    recent = (
                        db.query(Signal)
                        .filter(
                            Signal.coin_id == coin.id,
                            Signal.strategy_id == strategy_obj.id,
                            Signal.signal_type == signal_type,
                            Signal.status == "active",
                        )
                        .order_by(Signal.created_at.desc())
                        .first()
                    )
                    if recent:
                        continue

                    # --- AI SIGNAL ANALYSIS ---
                    from services.ai_service import analyze_signal_with_ai
                    
                    # Prepare metrics for AI context
                    metrics_context = {
                        "rsi": round(float(df["rsi_14"].iloc[-1]), 2) if "rsi_14" in df.columns else "N/A",
                        "macd": round(float(df["macd"].iloc[-1]), 4) if "macd" in df.columns else "N/A",
                        "bb_width": round(float(df["bb_width"].iloc[-1]), 2) if "bb_width" in df.columns else "N/A",
                        "ema_21": round(float(df["ema_21"].iloc[-1]), 2) if "ema_21" in df.columns else "N/A",
                        "ema_200": round(float(df["ema_200"].iloc[-1]), 2) if "ema_200" in df.columns else "N/A",
                    }

                    ai_result = analyze_signal_with_ai({
                        "symbol": coin.symbol,
                        "signal_type": signal_type,
                        "price": last_close,
                        "sl": sl,
                        "tp": tp,
                        "strategy": strategy_obj.name,
                        "metrics": metrics_context
                    })

                    sig = Signal(
                        coin_id=coin.id,
                        strategy_id=strategy_obj.id,
                        signal_type=signal_type,
                        entry_price=last_close,
                        stop_loss=sl,
                        take_profit=tp,
                        confidence=round(last_confidence, 1),
                        volatility=round(last_volatility, 2) if last_volatility is not None else None,
                        timeframe=mapping.timeframe,
                        status="active",
                        ai_analysis=ai_result.get("analysis"),
                        ai_score=ai_result.get("score", 50)
                    )
                    db.add(sig)
                    db.flush()
                    generated += 1

                    # Safely dispatch async broadcast to main event loop
                    global main_loop
                    if main_loop:
                        asyncio.run_coroutine_threadsafe(
                            broadcast_signal({
                                "id": sig.id,
                                "symbol": coin.symbol,
                                "strategy": strategy_obj.name,
                                "signal_type": signal_type,
                                "entry_price": last_close,
                                "stop_loss": sl,
                                "take_profit": tp,
                                "confidence": round(last_confidence, 1),
                                "volatility": round(last_volatility, 2) if last_volatility is not None else None,
                                "timeframe": mapping.timeframe,
                                "ai_analysis": ai_result.get("analysis"),
                                "ai_score": ai_result.get("score", 50),
                                "created_at": datetime.utcnow().isoformat() + "Z",
                            }),
                            main_loop
                        )

                    # --- SEND TELEGRAM ALERT ---
                    emoji = "🟢" if signal_type == "BUY" else "🔴"
                    clean_symbol = coin.symbol.split(':')[0].replace('/', '')
                    tv_url = f"https://www.tradingview.com/chart/?symbol=BINANCE:{clean_symbol}.P"
                    
                    msg = (
                        f"🚨 <b>CRYPTOEDGE {signal_type} SIGNAL</b> 🚨\n\n"
                        f"{emoji} <b>Coin:</b> #{clean_symbol}\n"
                        f"⏱ <b>Timeframe:</b> {mapping.timeframe}\n"
                        f"📈 <b>Strategy:</b> {strategy_obj.name}\n"
                        f"🎯 <b>Price:</b> {last_close}\n\n"
                        f"🤖 <b>AI Analysis:</b> {ai_result.get('analysis')}\n"
                        f"📊 <b>AI Score:</b> {ai_result.get('score')}/100\n\n"
                        f"🛑 <b>SL:</b> {sl}\n"
                        f"✅ <b>TP:</b> {tp}\n\n"
                        f"🔥 <i>Confidence: {round(last_confidence, 1)}%</i>\n\n"
                        f"🔗 <a href='{tv_url}'>View on TradingView</a>"
                    )
                    send_telegram_message(msg)

            except Exception as e:
                logger.warning(f"Scanner error for {mapping.coin.symbol}: {e}")

        db.commit()
        logger.info(f"Scanner finished. Generated {generated} new signals from {len(mappings)} coins.")

    except Exception as e:
        logger.error(f"Scanner fatal error: {e}")
        db.rollback()
    finally:
        db.close()
