import asyncio
import logging
from services.binance_service import get_swap_exchange

logging.basicConfig(level=logging.INFO)

async def debug_tickers():
    exchange = get_swap_exchange()
    print("\n--- Fetching Tickers from Binance Futures ---")
    tickers = exchange.fetch_tickers()
    print(f"Total tickers found: {len(tickers)}")
    
    usdt_tickers = [s for s in tickers.keys() if s.endswith("USDT")]
    print(f"USDT tickers: {len(usdt_tickers)}")
    
    if usdt_tickers:
        symbol = usdt_tickers[0]
        ticker = tickers[symbol]
        print(f"\n--- Example Ticker Info for {symbol} ---")
        print(f"Ticker keys: {list(ticker.keys())}")
        print(f"Ticker info keys: {list(ticker['info'].keys())}")
        print(f"Quote Volume (from info): {ticker['info'].get('quoteVolume', 'MISSING')}")
        print(f"Quote Volume (from root): {ticker.get('quoteVolume', 'MISSING')}")
        print(f"Base Volume (from root): {ticker.get('baseVolume', 'MISSING')}")

if __name__ == "__main__":
    asyncio.run(debug_tickers())
