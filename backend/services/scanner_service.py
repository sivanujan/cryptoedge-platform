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


def run_scanner():
    """
    Main scanner loop. Called by APScheduler every 15 minutes.
    Loads active coin-strategy mappings, runs strategies, saves signals.
    """
    logger.info("Scanner started...")
    db: Session = SessionLocal()
    try:
        mappings = (
            db.query(CoinStrategyMap)
            .filter_by(is_active=True)
            .all()
        )

        if not mappings:
            logger.warning("No active coin-strategy mappings found, skipping scan.")
            return

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

                strategy = get_strategy(strategy_obj.name, strategy_obj.parameters)
                df = strategy.generate_signals(df)

                last_signal = int(df["signal"].iloc[-1])
                # Use .item() to safely convert numpy/Series to Python scalar
                try:
                    last_confidence = float(df["confidence"].iloc[-1]) if "confidence" in df.columns else 70.0
                except (TypeError, ValueError):
                    last_confidence = 70.0
                try:
                    last_close = float(df["close"].iloc[-1])
                except (TypeError, ValueError):
                    logger.warning(f"Could not extract close price for {coin.symbol}, skipping")
                    continue

                if last_signal in (1, -1):
                    signal_type = "BUY" if last_signal == 1 else "SELL"
                    sl = strategy.calculate_stop_loss(last_close)
                    tp = strategy.calculate_take_profit(last_close)

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

                    sig = Signal(
                        coin_id=coin.id,
                        strategy_id=strategy_obj.id,
                        signal_type=signal_type,
                        entry_price=last_close,
                        stop_loss=sl,
                        take_profit=tp,
                        confidence=round(last_confidence, 1),
                        timeframe=mapping.timeframe,
                        status="active",
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
                                "timeframe": mapping.timeframe,
                                "created_at": datetime.utcnow().isoformat(),
                            }),
                            main_loop
                        )

                    # --- SEND TELEGRAM ALERT ---
                    emoji = "🟢" if signal_type == "BUY" else "🔴"
                    msg = (
                        f"🚨 <b>CRYPTOEDGE {signal_type} SIGNAL</b> 🚨\n\n"
                        f"{emoji} <b>Coin:</b> #{coin.symbol.replace('/', '')}\n"
                        f"⏱ <b>Timeframe:</b> {mapping.timeframe}\n"
                        f"📈 <b>Strategy:</b> {strategy_obj.name}\n"
                        f"🎯 <b>Price:</b> {last_close}\n\n"
                        f"🛑 <b>SL:</b> {sl}\n"
                        f"✅ <b>TP:</b> {tp}\n\n"
                        f"🔥 <i>Confidence: {round(last_confidence, 1)}%</i>"
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
