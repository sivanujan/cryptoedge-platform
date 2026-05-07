import os
import logging
from typing import List, Optional, Dict
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


_delivery_exchange = None


def get_delivery_exchange() -> ccxt.binance:
    """Returns a cached ccxt instance configured for Binance delivery futures markets."""
    global _delivery_exchange
    if _delivery_exchange is None:
        _delivery_exchange = ccxt.binance({
            "apiKey": os.getenv("BINANCE_API_KEY", ""),
            "secret": os.getenv("BINANCE_SECRET_KEY", ""),
            "enableRateLimit": True,
            "options": {"defaultType": "future"},
        })
    return _delivery_exchange


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
    ticker = get_ticker_info(symbol)
    return ticker.get("last") if ticker else None


def get_ticker_info(symbol: str) -> Optional[Dict]:
    """Get full ticker data for a symbol (last price, 24h change, etc)."""
    try:
        exchange = get_exchange()
        ticker = exchange.fetch_ticker(symbol)
        return {
            "last": float(ticker["last"]),
            "percentage": float(ticker.get("percentage", 0)),
            "high": float(ticker.get("high", 0)),
            "low": float(ticker.get("low", 0)),
            "quoteVolume": float(ticker.get("quoteVolume", 0)),
        }
    except Exception as e:
        logger.warning(f"Error fetching ticker for {symbol}: {e}")
        return None


def get_multiple_prices(symbols: List[str]) -> dict:
    """Get prices for multiple symbols efficiently. Detects if swap exchange should be used."""
    if not symbols:
        return {}
    
    prices = {}
    try:
        # Detect if we should use swap exchange based on symbol format
        # CCXT swap symbols usually contain ':' or the first symbol in list might give a hint
        use_swap = any(":" in s for s in symbols)
        exchange = get_swap_exchange() if use_swap else get_exchange()
        
        tickers = exchange.fetch_tickers(symbols)
        for symbol, ticker in tickers.items():
            last_price = float(ticker.get("last", 0))
            if last_price > 0:
                prices[symbol] = last_price
    except Exception as e:
        logger.warning(f"Error fetching multiple prices: {e}. Trying fallback...")
        # Fallback: fetch one by one using the appropriate exchange per symbol
        for symbol in symbols:
            try:
                exchange = get_swap_exchange() if ":" in symbol else get_exchange()
                ticker = exchange.fetch_ticker(symbol)
                last_price = float(ticker.get("last", 0))
                if last_price > 0:
                    prices[symbol] = last_price
            except:
                continue
    return prices


def get_multiple_tickers(symbols: List[str]) -> dict:
    """
    Get detailed ticker info (last price and percentage change) for multiple symbols efficiently.
    Returns: { symbol: { "last": float, "percentage": float } }
    """
    if not symbols:
        return {}
    
    results = {}
    try:
        # Group symbols by their Binance type
        # Spot: No ':'
        # Perp: Has ':', no delivery date (e.g. BTC/USDT:USDT)
        # Delivery: Has ':', has delivery date (e.g. BTC/USDT:USDT-241227)
        
        spot_symbols = [s for s in symbols if ":" not in s]
        swap_symbols = [s for s in symbols if ":" in s]
        
        # Further split swap into perps and delivery to avoid Binance mixed-type errors
        perp_symbols = []
        delivery_symbols = []
        for s in swap_symbols:
            # Delivery symbols usually have a date at the end like -241227
            parts = s.split("-")
            if len(parts) > 1 and parts[-1].isdigit():
                delivery_symbols.append(s)
            else:
                perp_symbols.append(s)
        
        groups = [
            (get_exchange(), spot_symbols),
            (get_swap_exchange(), perp_symbols),
            (get_delivery_exchange(), delivery_symbols)
        ]
        
        for exchange, group in groups:
            if not group:
                continue
            try:
                # Optimized: Requesting specific symbols is generally faster than fetching ALL 
                # unless the list is extremely large (>100).
                if len(group) > 100:
                    all_tickers = exchange.fetch_tickers()
                    for s in group:
                        if s in all_tickers:
                            t = all_tickers[s]
                            results[s] = {
                                "last": float(t.get("last", 0)),
                                "percentage": float(t.get("percentage", 0))
                            }
                else:
                    # Request only the needed symbols - very efficient and fast
                    tickers = exchange.fetch_tickers(group)
                    for s, t in tickers.items():
                        results[s] = {
                            "last": float(t.get("last", 0)),
                            "percentage": float(t.get("percentage", 0))
                        }
            except Exception as e:
                logger.warning(f"Batch fetch failed for group {group[:2]}...: {e}. Falling back to single fetches.")
                for s in group:
                    if s in results: continue
                    try:
                        t = exchange.fetch_ticker(s)
                        results[s] = {
                            "last": float(t.get("last", 0)),
                            "percentage": float(t.get("percentage", 0))
                        }
                    except Exception as single_e:
                        logger.debug(f"Individual fetch failed for {s}: {single_e}")
                        continue
                        
    except Exception as e:
        logger.error(f"Error in get_multiple_tickers: {e}")
        
    return results
