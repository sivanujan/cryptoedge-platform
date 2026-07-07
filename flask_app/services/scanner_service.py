import asyncio
import logging
import math
from datetime import datetime
from typing import List, Set

import pandas as pd
from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models import CoinStrategyMap, Signal, Coin, Strategy
from services.binance_service import get_ohlcv, get_current_price
from services.indicator_service import add_all_indicators
from strategies.golden_cross import get_strategy
from services.telegram_service import send_telegram_message

logger = logging.getLogger(__name__)

# Global WebSocket broadcasting (Injected by app.py)
def broadcast_price(data: dict):
    """Placeholder for price broadcasting."""
    pass

def broadcast_signal(data: dict):
    """Placeholder for signal broadcasting."""
    pass

def register_price_ws(ws): pass
def unregister_price_ws(ws): pass
def register_signal_ws(ws): pass
def unregister_signal_ws(ws): pass


def register_price_ws(ws):
    _price_connections.add(ws)


def unregister_price_ws(ws):
    _price_connections.discard(ws)


def register_signal_ws(ws):
    _signal_connections.add(ws)


def unregister_signal_ws(ws):
    _signal_connections.discard(ws)


# Broadcasting logic updated above


def run_scanner():
    """
    Main scanner loop. Called by APScheduler every 15 minutes.
    Loads active coin-strategy mappings, runs strategies, saves signals.
    """
    logger.info("Scanner started...")
    db: Session = SessionLocal()
    try:
        from database.models import Setting
        setting = db.query(Setting).filter_by(key="signal_generation_enabled").first()
        if setting and setting.value == "false":
            logger.info("Signal generation is disabled. Skipping scan.")
            return

        from database.models import StrategyRanking
        rankings = db.query(StrategyRanking).all()

        targets = []
        if rankings:
            logger.info(f"Using {len(rankings)} ranked targets from StrategyRanking.")
            for r in rankings:
                # Clean up coin symbol from "ZEC/USDT:USDT" or "ZEC/USDT" to "ZECUSDT"
                clean_symbol = str(r.coin).replace("/", "").replace(":USDT", "").strip()
                if not clean_symbol.endswith("USDT"):
                    clean_symbol += "USDT"
                    
                targets.append({
                    "coin_symbol": clean_symbol,
                    "strategy_id": r.strategy_id,
                    "timeframe": r.timeframe
                })
        else:
            logger.info("No rankings found in StrategyRanking. Falling back to CoinStrategyMap.")
            mappings = (
                db.query(CoinStrategyMap)
                .filter_by(is_active=True)
                .all()
            )

            if not mappings:
                logger.info("No active coin-strategy mappings found. Auto-generating for top coins...")
                active_strats = db.query(Strategy).filter_by(is_active=True).all()
                top_coins = db.query(Coin).filter_by(is_active=True).order_by(Coin.id).limit(15).all()
                
                for strat in active_strats:
                    for c in top_coins:
                        for tf in ["15m", "1h", "4h"]:
                            cmap = CoinStrategyMap(
                                coin_id=c.id,
                                strategy_id=strat.id,
                                timeframe=tf,
                                is_active=True
                            )
                            db.add(cmap)
                db.commit()
                
                mappings = (
                    db.query(CoinStrategyMap)
                    .filter_by(is_active=True)
                    .all()
                )

            if not mappings:
                logger.warning("Still no active mappings, skipping scan.")
                return
                
            for m in mappings:
                targets.append({
                    "coin_symbol": m.coin.symbol,
                    "strategy_id": m.strategy_id,
                    "timeframe": m.timeframe
                })

        # Fetch global risk settings
        from database.models import Setting
        settings_rows = db.query(Setting).all()
        settings = {row.key: row.value for row in settings_rows}
        global_sl = float(settings.get("default_sl_pct", 2.0))
        global_tp = float(settings.get("default_tp_pct", 4.0))

        generated = 0
        for target in targets:
            try:
                coin_symbol = target["coin_symbol"]
                strategy_id = target["strategy_id"]
                timeframe = target["timeframe"]

                coin = db.query(Coin).filter_by(symbol=coin_symbol).first()
                strategy_obj = db.query(Strategy).filter_by(id=strategy_id).first()
                
                if not coin or not strategy_obj:
                    logger.warning(f"Target missing coin or strategy in DB: {coin_symbol}, Strategy ID: {strategy_id}")
                    continue

                df = get_ohlcv(coin.symbol, timeframe, limit=300)
                if df is None or len(df) < 50:
                    continue

                df = add_all_indicators(df)
                df = df.dropna()
                
                if df.empty or len(df) < 5:
                    logger.warning(f"Dataframe too small after indicators for {coin.symbol}, skipping.")
                    continue

                strategy = get_strategy(strategy_obj, strategy_obj.parameters)
                df = strategy.generate_signals(df)

                # Look for any non-zero signal in recent candles (not just last one)
                recent_signals = df[df['signal'] != 0].tail(3)
                if len(recent_signals) == 0:
                    last_signal = 0
                else:
                    # Get the most recent non-zero signal
                    last_sig_row = recent_signals.iloc[-1]
                    last_signal = int(last_sig_row['signal'])
                    # Use the price at that signal time
                    last_close = float(last_sig_row['close'])
                    # Get confidence/volatility from that row
                    try:
                        last_confidence = float(last_sig_row['confidence']) if 'confidence' in last_sig_row else 70.0
                    except (TypeError, ValueError):
                        last_confidence = 70.0
                    try:
                        last_volatility = float(last_sig_row['volatility_atr']) if 'volatility_atr' in last_sig_row and not math.isnan(float(last_sig_row['volatility_atr'])) else None
                    except (TypeError, ValueError):
                        last_volatility = None

                # If no signal in recent candles, get last close price
                if last_signal == 0:
                    try:
                        last_close = float(df["close"].iloc[-1])
                    except (TypeError, ValueError):
                        logger.warning(f"Could not extract close price for {coin.symbol}, skipping")
                        continue
                    last_confidence = 70.0
                    last_volatility = None

                if last_signal in (1, -1):
                    # Check trend first (uptrend/downtrend filter)
                    ema_21 = df.iloc[-1].get("ema_21")
                    ema_50 = df.iloc[-1].get("ema_50")
                    trend_str = "neutral"
                    if pd.notnull(ema_21) and pd.notnull(ema_50):
                        if last_close > ema_50 and ema_21 > ema_50:
                            trend_str = "uptrend"
                        elif last_close < ema_50 and ema_21 < ema_50:
                            trend_str = "downtrend"
                            
                    if last_signal == 1 and trend_str != "uptrend":
                        logger.info(f"Skipping strategy BUY signal for {coin.symbol} because market is not in a confirmed uptrend (Trend: {trend_str})")
                        continue
                    elif last_signal == -1 and trend_str != "downtrend":
                        logger.info(f"Skipping strategy SELL signal for {coin.symbol} because market is not in a confirmed downtrend (Trend: {trend_str})")
                        continue

                    signal_type = "BUY" if last_signal == 1 else "SELL"
                    
                    # Check gap between signal price and current price
                    current_market_price = get_current_price(coin.symbol)
                    if current_market_price:
                        gap_pct = abs(current_market_price - last_close) / last_close * 100
                        if gap_pct > 1.0: # Skip if gap is more than 1%
                            logger.info(f"Skipping signal for {coin.symbol} due to large gap ({gap_pct:.2f}%)")
                            continue
                            
                    # Calculate Structure-based SL/TP
                    from services.structure_service import calculate_structure_sl_tp
                    struct_data = calculate_structure_sl_tp(df, last_close, signal_type, global_sl, global_tp)
                    
                    sl = struct_data["structure_sl"]
                    tp = struct_data["structure_tp"]

                    # Filter out signals with low TP margin
                    if struct_data.get("tp_pct", 0) < 1.0:
                        logger.info(f"Skipping signal for {coin.symbol} - TP percentage too low: {struct_data.get('tp_pct')}% < 1%")
                        continue

                    # Avoid duplicate signals within same candle
                    recent = (
                        db.query(Signal)
                        .filter(
                            Signal.coin_id == coin.id,
                            Signal.strategy_id == strategy_obj.id,
                            Signal.signal_type == signal_type,
                            Signal.status.in_(["active", "wait"]),
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
                        volatility=round(last_volatility, 2) if last_volatility is not None else None,
                        timeframe=timeframe,
                        status="wait",
                        structure_sl=struct_data["structure_sl"],
                        structure_tp=struct_data["structure_tp"],
                        sl_pct=struct_data["sl_pct"],
                        tp_pct=struct_data["tp_pct"],
                        rr_ratio=struct_data["rr_ratio"],
                        sl_method=struct_data["sl_method"]
                    )
                    db.add(sig)
                    db.flush()
                    generated += 1

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
                        "timeframe": timeframe,
                        "created_at": datetime.utcnow().isoformat() + "Z",
                    })



                    # --- SEND TELEGRAM ALERT ---
                    emoji = "🟢" if signal_type == "BUY" else "🔴"
                    clean_symbol = coin.symbol.split(':')[0].replace('/', '')
                    tv_url = f"https://www.tradingview.com/chart/?symbol=BINANCE:{clean_symbol}.P"
                    
                    msg = (
                        f"🚨 <b>CRYPTOEDGE {signal_type} SIGNAL</b> 🚨\n\n"
                        f"{emoji} <b>Coin:</b> #{clean_symbol}\n"
                        f"⏱ <b>Timeframe:</b> {timeframe}\n"
                        f"📈 <b>Strategy:</b> {strategy_obj.name}\n"
                        f"🎯 <b>Price:</b> {last_close}\n\n"
                        f"🛑 <b>SL:</b> {sl}\n"
                        f"✅ <b>TP:</b> {tp}\n\n"
                        f"🔥 <i>Confidence: {round(last_confidence, 1)}%</i>\n\n"
                        f"🔗 <a href='{tv_url}'>View on TradingView</a>"
                    )
                    send_telegram_message(msg)

            except Exception as e:
                import traceback
                logger.warning(f"Scanner error for {coin.symbol}: {e}\n{traceback.format_exc()}")

        db.commit()
        logger.info(f"Scanner finished. Generated {generated} new signals from {len(targets)} targets.")

    except Exception as e:
        logger.error(f"Scanner fatal error: {e}")
        db.rollback()
    finally:
        db.close()
