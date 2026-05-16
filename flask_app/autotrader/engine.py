import time
import logging
import threading
import json
from datetime import datetime
from database.connection import SessionLocal
from database.models import AutoTradeSetting, AutoTrade
from services.binance_service import get_ohlcv
from services.indicator_service import add_all_indicators
from . import binance_executor
from . import risk_manager
from .strategies import AVAILABLE_STRATEGIES

logger = logging.getLogger(__name__)

engine_running = False
engine_thread = None

def get_settings(db):
    settings = db.query(AutoTradeSetting).first()
    if not settings:
        settings = AutoTradeSetting()
        db.add(settings)
        db.commit()
    return settings

def auto_trade_loop():
    global engine_running
    while engine_running:
        db = SessionLocal()
        try:
            settings = get_settings(db)
            if not settings.is_enabled:
                time.sleep(10)
                continue
                
            total_bal, avail_bal, unrealized_pnl = binance_executor.get_futures_balance()
            if total_bal <= 0:
                logger.warning("No futures balance! Skipping trade cycle.")
                time.sleep(10)
                continue

            if risk_manager.check_daily_loss_limit(db, settings.daily_loss_limit, total_bal):
                logger.warning("Daily loss limit hit! Halting auto trading.")
                settings.is_enabled = False
                db.commit()
                continue
                
            open_trades = db.query(AutoTrade).filter_by(status="OPEN").all()
            if len(open_trades) < settings.max_open_trades:
                try:
                    enabled_strats = json.loads(settings.enabled_strategies)
                except:
                    enabled_strats = []
                from strategies.golden_cross import get_strategy
                from database.models import Strategy
                
                for strat_name in enabled_strats:
                    for symbol in ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]:
                        if any(t.symbol == symbol for t in open_trades): continue
                        
                        trade_opened_for_symbol = False
                        for tf in ["1m", "5m", "15m", "1h"]:
                            if len(open_trades) >= settings.max_open_trades:
                                break
                            if trade_opened_for_symbol:
                                break
                                
                            df = get_ohlcv(symbol, tf, 100)
                            if df is None: continue
                            df = add_all_indicators(df)
                            import pandas as pd
                            for col in ['ema_21', 'ema_50', 'ema_200', 'rsi_14']:
                                if col in df.columns:
                                    df[col] = pd.to_numeric(df[col], errors='coerce')
                            
                            sig = None
                            db_strat = db.query(Strategy).filter_by(name=strat_name, is_active=True).first()
                            if db_strat:
                                try:
                                    strategy_inst = get_strategy(db_strat)
                                    df_with_sig = strategy_inst.generate_signals(df)
                                    last_row = df_with_sig.iloc[-1]
                                    
                                    signal_val = 0
                                    if 'signal' in last_row:
                                        signal_val = last_row['signal']
                                    elif 'signals' in last_row:
                                        signal_val = last_row['signals']
                                        
                                    if signal_val == 1 or signal_val == "LONG":
                                        sig = {"signal": "LONG", "confidence": 70, "reason": f"Dynamic Strategy ({tf})"}
                                    elif signal_val == -1 or signal_val == "SHORT":
                                        sig = {"signal": "SHORT", "confidence": 70, "reason": f"Dynamic Strategy ({tf})"}
                                except Exception as e:
                                    logger.error(f"Error executing dynamic strategy {strat_name} on {tf}: {e}")
                                        
                            if sig:
                                # Enter Trade
                                price = df['close'].iloc[-1]
                                qty = risk_manager.calculate_position_size(avail_bal, settings.per_trade_percent, price, settings.leverage)
                                logger.info(f"Signal detected for {symbol} ({tf}): {sig['signal']}. Calculated qty: {qty} at price {price}")
                                sl = risk_manager.calculate_stop_loss(price, sig['signal'], settings.leverage)
                                tp1, tp2, tp3 = risk_manager.calculate_take_profits(price, sig['signal'], settings.leverage)
                                symbol_base = symbol.replace('/USDT:USDT', 'USDT')
                                
                                binance_executor.set_leverage(symbol_base, settings.leverage)
                                side = 'BUY' if sig['signal'] == 'LONG' else 'SELL'
                                binance_side = 'BUY' if sig['signal'] == 'LONG' else 'SELL'
                                order_result = binance_executor.place_market_order(symbol_base, binance_side, qty)
                                
                                if order_result:
                                    logger.info(f"Placed {sig['signal']} order on {tf}: {qty} {symbol_base} at {price}")
                                    binance_executor.place_stop_market_order(symbol_base, side, qty, sl)
                                    binance_executor.place_take_profit_market_order(symbol_base, side, qty, tp1)
                                    
                                    new_trade = AutoTrade(
                                        symbol=symbol, side=sig['signal'], entry_price=price, quantity=qty,
                                        leverage=settings.leverage, margin_used=(qty*price)/settings.leverage,
                                        strategy_name=f"{strat_name} ({tf})", sl_price=sl, tp1=tp1, tp2=tp2, tp3=tp3
                                    )
                                    db.add(new_trade)
                                    db.commit()
                                    open_trades.append(new_trade)
                                    trade_opened_for_symbol = True
                                    break
                                else:
                                    logger.warning(f"Failed to execute order for {symbol_base}")
            
            # Trailing SL
            open_trades = db.query(AutoTrade).filter_by(status="OPEN").all()
            for trade in open_trades:
                df = get_ohlcv(trade.symbol, "1m", 1)
                if df is not None:
                    curr_price = df['close'].iloc[-1]
                    if risk_manager.trailing_sl_logic(trade, curr_price):
                        db.commit()
                        
        except Exception as e:
            logger.error(f"Auto engine error: {e}")
            db.rollback()
        finally:
            db.close()
            
        time.sleep(30)
        engine_running = False

def start_engine():
    global engine_running, engine_thread
    if not engine_running:
        engine_running = True
        engine_thread = threading.Thread(target=auto_trade_loop, daemon=True)
        engine_thread.start()

def stop_engine():
    global engine_running
    engine_running = False
