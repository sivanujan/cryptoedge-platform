import os
import logging
import requests
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


def _to_binance_futures_symbol(ccxt_symbol: str) -> str:
    """Convert CCXT symbol like 'BTC/USDT:USDT' → 'BTCUSDT' for Binance FAPI."""
    # Remove ':USDT' suffix, then remove '/'
    return ccxt_symbol.split(":")[0].replace("/", "")


def get_multiple_prices(symbols: List[str]) -> dict:
    """Get live prices for multiple symbols. Uses Binance FAPI REST for futures, spot exchange for spot."""
    if not symbols:
        return {}

    futures_symbols = [s for s in symbols if ":" in s]
    spot_symbols   = [s for s in symbols if ":" not in s]
    prices = {}

    # ── Futures via Binance FAPI REST (fast, no auth needed) ─────────────────
    if futures_symbols:
        try:
            resp = requests.get(
                "https://fapi.binance.com/fapi/v1/ticker/price",
                timeout=5
            )
            resp.raise_for_status()
            all_fapi = {item["symbol"]: float(item["price"]) for item in resp.json()}

            for ccxt_sym in futures_symbols:
                binance_sym = _to_binance_futures_symbol(ccxt_sym)
                if binance_sym in all_fapi:
                    prices[ccxt_sym] = all_fapi[binance_sym]
                else:
                    logger.warning(f"Symbol {binance_sym} not found in FAPI prices")
        except Exception as e:
            logger.warning(f"FAPI bulk price fetch failed: {e}. Falling back to CCXT...")
            # CCXT fallback for futures
            try:
                exchange = get_swap_exchange()
                tickers = exchange.fetch_tickers(futures_symbols)
                for sym, ticker in tickers.items():
                    if ticker.get("last"):
                        prices[sym] = float(ticker["last"])
            except Exception as e2:
                logger.error(f"CCXT swap fallback also failed: {e2}")
                for symbol in futures_symbols:
                    try:
                        exchange = get_swap_exchange()
                        ticker = exchange.fetch_ticker(symbol)
                        if ticker.get("last"):
                            prices[symbol] = float(ticker["last"])
                    except Exception:
                        pass

    # ── Spot via CCXT ─────────────────────────────────────────────────────────
    if spot_symbols:
        try:
            exchange = get_exchange()
            tickers = exchange.fetch_tickers(spot_symbols)
            for sym, ticker in tickers.items():
                if ticker.get("last"):
                    prices[sym] = float(ticker["last"])
        except Exception as e:
            logger.warning(f"Spot bulk price fetch failed: {e}")
            for symbol in spot_symbols:
                try:
                    ticker = get_exchange().fetch_ticker(symbol)
                    if ticker.get("last"):
                        prices[symbol] = float(ticker["last"])
                except Exception:
                    pass

    logger.info(f"Fetched prices for {len(prices)}/{len(symbols)} symbols")
    return prices

