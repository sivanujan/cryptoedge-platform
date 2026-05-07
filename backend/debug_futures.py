import asyncio
import logging
from services.futures_analysis_service import analyze_symbol_technical, get_top_gainers_losers

logging.basicConfig(level=logging.INFO)

async def test_analysis():
    # 1. Test fetching top coins
    print("\n--- Testing get_top_gainers_losers ---")
    result = get_top_gainers_losers(limit=5, min_volume=10000000)
    print(f"Fetched {len(result['longs'])} longs and {len(result['shorts'])} shorts")
    
    if result['longs']:
        symbol = result['longs'][0]['symbol']
        print(f"\n--- Testing analyze_symbol_technical for {symbol} ---")
        tech = analyze_symbol_technical(symbol, timeframe="1h")
        if tech:
            print(f"Technical analysis successful for {symbol}")
            print(f"Price: {tech['price']}, Signal: {tech['entry_signal']}, Quality: {tech['entry_quality']}")
        else:
            print(f"Technical analysis FAILED for {symbol}")

if __name__ == "__main__":
    asyncio.run(test_analysis())
