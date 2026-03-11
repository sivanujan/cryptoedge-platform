import os
import logging
from typing import List, Optional
import ccxt
import pandas as pd
from dotenv import load_dotenv
from cachetools import TTLCache, cached
import threading

load_dotenv()

logger = logging.getLogger(__name__)

_exchange = None
_swap_exchange = None


def get_exchange() -> ccxt.binance:
    global _exchange
    if _exchange is None:
        _exchange = ccxt.binance({
            "apiKey": os.getenv("BINANCE_API_KEY", ""),
            "secret": os.getenv("BINANCE_SECRET_KEY", ""),
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        })
    return _exchange


def get_swap_exchange() -> ccxt.binance:
    """Returns a cached ccxt instance configured for Binance futures (swap) markets."""
    global _swap_exchange
    if _swap_exchange is None:
        _swap_exchange = ccxt.binance({
            "apiKey": os.getenv("BINANCE_API_KEY", ""),
            "secret": os.getenv("BINANCE_SECRET_KEY", ""),
            "enableRateLimit": True,
            "options": {"defaultType": "swap"},
        })
    return _swap_exchange


def get_all_usdt_pairs() -> List[str]:
    """Fetch all active USDT trading pairs from Binance."""
    try:
        # Use swap exchange instance to get linear futures
        exchange = get_swap_exchange()
        markets = exchange.fetch_markets()
        pairs = [
            m["symbol"]
            for m in markets
            if m.get("quote") == "USDT" 
            and m.get("active", True)
            and m.get("linear") == True # Linear USDT-margined perp
        ]
        logger.info(f"Fetched {len(pairs)} USDT pairs from Binance")
        return pairs
    except Exception as e:
        logger.error(f"Error fetching USDT pairs: {e}")
        return []


# Cache candle data for 15 minutes to make backtests instantly fast after first load
# Use a threading.Lock to make the cache thread-safe (multiple threads fetch data simultaneously)
_ohlcv_cache = TTLCache(maxsize=5000, ttl=900)
_ohlcv_lock = threading.Lock()

@cached(cache=_ohlcv_cache, lock=_ohlcv_lock)
def get_ohlcv(symbol: str, timeframe: str = "1h", limit: int = 1000) -> Optional[pd.DataFrame]:
    """
    Fetch OHLCV candle data for a symbol.
    Returns a DataFrame with columns: open_time, open, high, low, close, volume
    """
    try:
        exchange = get_swap_exchange()
        raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if not raw:
            return None

        df = pd.DataFrame(raw, columns=["open_time", "open", "high", "low", "close", "volume"])
        df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
        df = df.set_index("open_time")
        df = df.astype(float)
        return df
    except Exception as e:
        logger.warning(f"Error fetching OHLCV for {symbol} [{timeframe}]: {e}")
        return None


def get_current_price(symbol: str) -> Optional[float]:
    """Get latest ticker price for a symbol."""
    try:
        exchange = get_exchange()
        ticker = exchange.fetch_ticker(symbol)
        return float(ticker["last"])
    except Exception as e:
        logger.warning(f"Error fetching price for {symbol}: {e}")
        return None


def get_multiple_prices(symbols: List[str]) -> dict:
    """Get prices for multiple symbols efficiently."""
    prices = {}
    try:
        exchange = get_exchange()
        tickers = exchange.fetch_tickers(symbols)
        for symbol, ticker in tickers.items():
            prices[symbol] = float(ticker.get("last", 0))
    except Exception as e:
        logger.warning(f"Error fetching multiple prices: {e}")
        # Fallback: fetch one by one
        for symbol in symbols:
            price = get_current_price(symbol)
            if price:
                prices[symbol] = price
    return prices
