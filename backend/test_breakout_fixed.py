import asyncio
import pandas as pd
from services.futures_analysis_service import analyze_symbol_technical, find_breakout_point

async def verify_breakout():
    symbol = "BTCUSDT"
    print(f"--- Verifying Breakout Analysis for {symbol} (15m) ---")
    
    # Analyze 15m
    result = analyze_symbol_technical(symbol, timeframe="15m")
    
    if result:
        print(f"Price: {result['price']}")
        print(f"Entry Signal: {result['entry_signal']}")
        print(f"Entry Quality: {result['entry_quality']}")
        
        if result['breakout']:
            b = result['breakout']
            print(f"Breakout Found: {b['type']} at ${b['price']} ({b['age']} candles ago)")
            print(f"Volume Multiplier: {b['vol_ratio']}x")
        else:
            print("No recent breakout found in the lookback window.")
            
        print("\n--- Technicals ---")
        if 'rsi' in result:
            print(f"RSI: {result['rsi']}")
        if 'vol_ratio' in result:
            print(f"Vol Ratio: {result['vol_ratio']}x")
        if 'trend' in result:
            print(f"Trend: {result['trend']}")
    else:
        print("Analysis failed.")

if __name__ == "__main__":
    asyncio.run(verify_breakout())
