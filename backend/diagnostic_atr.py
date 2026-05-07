
import sys
import os
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from database.connection import SessionLocal
from database.models import Strategy, Coin, CoinStrategyMap
from strategies.golden_cross import get_strategy
from services.binance_service import get_ohlcv
from services.indicator_service import add_all_indicators

def diagnostic_scan():
    db = SessionLocal()
    try:
        # Get Strategy ID 7
        strat_obj = db.query(Strategy).get(7)
        if not strat_obj:
            print("Strategy ID 7 not found!")
            return

        # Get first assignment
        mapping = db.query(CoinStrategyMap).filter_by(strategy_id=7, is_active=True).first()
        if not mapping:
            print("No active mappings for Strategy ID 7!")
            return

        coin = mapping.coin
        print(f"Scanning {coin.symbol} ({mapping.timeframe}) with {strat_obj.name}")
        
        # Fetch REAL OHLCV data
        df = get_ohlcv(coin.symbol, mapping.timeframe, limit=500)
        if df is None or len(df) < 50:
            print(f"Failed to fetch data for {coin.symbol}")
            return
            
        # Add indicators
        df = add_all_indicators(df)
        df = df.dropna()
        
        # Instantiate strategy
        strategy = get_strategy(strat_obj, strat_obj.parameters)
        
        # Generate signals
        df = strategy.generate_signals(df)
        
        if 'signal' in df.columns:
            all_sigs = df[df['signal'] != 0]
            print(f"Found {len(all_sigs)} signals in the last 500 candles.")
            if len(all_sigs) > 0:
                print("Latest Signal:")
                print(all_sigs.tail(1)[['close', 'signal']])
                # Check the VERY LATEST candle (which scanner uses)
                last_sig = df['signal'].iloc[-1]
                print(f"Signal on current/final candle: {last_sig}")
            else:
                print("No signals found in the entire 500-candle history for this coin.")
                # Print a summary of the indicator values for debugging
                print("Last few candles indicator state:")
                cols = ['close'] + [c for c in df.columns if 'ema' in c or 'rsi' in c]
                print(df[cols].tail(3))
        else:
            print("ERROR: 'signal' column missing!")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    diagnostic_scan()
