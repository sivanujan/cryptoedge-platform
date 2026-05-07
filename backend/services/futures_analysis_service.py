import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from services.binance_service import get_swap_exchange, get_ohlcv, get_all_usdt_pairs
import pandas as pd
from services.indicator_service import add_all_indicators

logger = logging.getLogger(__name__)


def get_top_gainers_losers(limit: int = 20, min_volume: float = 0) -> Dict[str, List[Dict]]:
    """
    Fetch top gainers (longs) and losers (shorts) from Binance Futures.
    Based on 24h price change percentage.

    Args:
        limit: Number of top gainers/losers to return (default 20)
        min_volume: Minimum 24h volume in USDT to include

    Returns:
        Dict with 'longs' and 'shorts' lists
    """
    try:
        exchange = get_swap_exchange()

        # Fetch all 24h tickers
        tickers = exchange.fetch_tickers()

        # Filter for USDT pairs and calculate 24h change
        usdt_pairs = []
        all_usdt_pairs = get_all_usdt_pairs()
        
        for symbol in all_usdt_pairs:
            ticker = tickers.get(symbol)
            if not ticker:
                continue
            
            # Get 24h quote volume from the ccxt unified ticker object
            quote_volume = float(ticker.get("quoteVolume", 0))
            if quote_volume < min_volume:
                continue

            change_pct = float(ticker.get("percentage", 0) or 0)
            price = float(ticker.get("last", 0))

            usdt_pairs.append({
                "symbol": symbol,
                "price": price,
                "change_24h": change_pct,
                "volume_24h": quote_volume,
                "high_24h": float(ticker.get("high", 0)),
                "low_24h": float(ticker.get("low", 0)),
            })

        # Sort by change percentage
        usdt_pairs.sort(key=lambda x: x["change_24h"], reverse=True)

        # Get top gainers (longs) and losers (shorts)
        longs = usdt_pairs[:limit]
        shorts = usdt_pairs[-limit:][::-1]  # Reverse to get biggest losers first

        logger.info(f"Fetched {len(longs)} longs and {len(shorts)} shorts from Binance Futures")

        return {
            "longs": longs,
            "shorts": shorts,
        }

    except Exception as e:
        logger.error(f"Error fetching top gainers/losers: {e}")
        return {"longs": [], "shorts": []}


def find_breakout_point(df: pd.DataFrame, window: int = 20) -> Optional[Dict[str, Any]]:
    """
    Find the most recent significant breakout point.
    A breakout is defined as a close outside Bollinger Bands with high volume.
    """
    try:
        if df.empty or len(df) < window:
            return None

        # Look at the last 'window' candles (excluding the current one)
        subset = df.iloc[-window:-1].iloc[::-1]  # Reverse to find most recent
        
        for i, (idx, row) in enumerate(subset.iterrows()):
            price = float(row["close"])
            bb_upper = row.get("bb_upper")
            bb_lower = row.get("bb_lower")
            vol = row.get("volume", 0)
            vol_sma = row.get("volume_sma", 1)
            vol_ratio = vol / vol_sma if vol_sma > 0 else 0

            # Long Breakout: Close > BB Upper + High Volume
            if bb_upper and price > bb_upper and vol_ratio > 1.3:
                return {
                    "type": "LONG",
                    "price": round(price, 6),
                    "age": i + 1,  # How many candles ago
                    "vol_ratio": round(vol_ratio, 2),
                    "timestamp": idx.isoformat() if hasattr(idx, 'isoformat') else str(idx)
                }
            
            # Short Breakout: Close < BB Lower + High Volume
            if bb_lower and price < bb_lower and vol_ratio > 1.3:
                return {
                    "type": "SHORT",
                    "price": round(price, 6),
                    "age": i + 1,
                    "vol_ratio": round(vol_ratio, 2),
                    "timestamp": idx.isoformat() if hasattr(idx, 'isoformat') else str(idx)
                }
        
        return None
    except Exception as e:
        logger.warning(f"Error in find_breakout_point: {e}")
        return None


def analyze_symbol_technical(symbol: str, timeframe: str = "1h") -> Optional[Dict[str, Any]]:
    """
    Perform technical analysis on a single symbol, including breakout detection.
    """
    try:
        df = get_ohlcv(symbol, timeframe, limit=500)
        if df is None or len(df) < 100:
            return None

        # Add indicators
        df = add_all_indicators(df)
        df = df.dropna()

        if df.empty:
            return None

        last = df.iloc[-1]
        price = float(last["close"])
        
        # Find Breakout Point
        breakout = find_breakout_point(df)

        # Extract key indicators
        rsi = last.get("rsi_14", 50)
        ema_21 = last.get("ema_21", price)
        ema_50 = last.get("ema_50", price)
        ema_200 = last.get("ema_200", price)
        macd = last.get("macd", 0)
        macd_signal = last.get("macd_signal", 0)
        macd_hist = last.get("macd_hist", 0)
        bb_upper = last.get("bb_upper", price * 1.02)
        bb_lower = last.get("bb_lower", price * 0.98)
        bb_mid = last.get("bb_mid", price)
        volatility = last.get("volatility_atr", 1)
        vol_ratio = last.get("volume_ratio", 1)

        # Determine trend
        trend = "NEUTRAL"
        if ema_21 > ema_50 and (ema_200 == 0 or ema_50 > ema_200):
            trend = "BULLISH"
        elif ema_21 < ema_50 and (ema_200 == 0 or ema_50 < ema_200):
            trend = "BEARISH"

        # RSI conditions
        rsi_signal = "NEUTRAL"
        if rsi > 70:
            rsi_signal = "OVERBOUGHT"
        elif rsi < 30:
            rsi_signal = "OVERSOLD"

        # Entry signal refined logic
        entry_signal = "WAIT"
        entry_quality = "NORMAL"
        
        if breakout:
            b_price = breakout["price"]
            b_type = breakout["type"]
            
            # Distance to breakout point
            dist_pct = abs(price - b_price) / b_price * 100
            
            if b_type == "LONG":
                if dist_pct < 0.5: # Retest zone
                    entry_signal = "STRONG_LONG_RETEST"
                    entry_quality = "STRONG"
                elif price > b_price and dist_pct < 2.0: # Momentum zone
                    entry_signal = "LONG_MOMENTUM"
                    entry_quality = "GOOD"
                elif price < b_price * 0.98: # Failed/Too deep
                    entry_signal = "BREAKOUT_FAILED"
            
            elif b_type == "SHORT":
                if dist_pct < 0.5: # Retest zone
                    entry_signal = "STRONG_SHORT_RETEST"
                    entry_quality = "STRONG"
                elif price < b_price and dist_pct < 2.0: # Momentum zone
                    entry_signal = "SHORT_MOMENTUM"
                    entry_quality = "GOOD"
                elif price > b_price * 1.02: # Failed/Too deep
                    entry_signal = "BREAKOUT_FAILED"

        # Fallback to standard signals if no breakout logic triggered
        if entry_signal == "WAIT":
            if trend == "BULLISH" and rsi < 65 and macd_hist > 0:
                entry_signal = "POURING_LONG"
            elif trend == "BEARISH" and rsi > 35 and macd_hist < 0:
                entry_signal = "POURING_SHORT"

        return {
            "price": round(price, 6),
            "trend": trend,
            "rsi": round(rsi, 2),
            "rsi_signal": rsi_signal,
            "bb_position": "ABOVE" if price > bb_upper else "BELOW" if price < bb_lower else "INSIDE",
            "volatility_pct": round(volatility, 2),
            "vol_ratio": round(vol_ratio, 2),
            "entry_signal": entry_signal,
            "entry_quality": entry_quality,
            "breakout": breakout,
            "technical": {
                "ema_21": round(ema_21, 6),
                "ema_50": round(ema_50, 6),
                "bb_upper": round(bb_upper, 6),
                "bb_lower": round(bb_lower, 6),
                "macd_hist": round(macd_hist, 6),
            }
        }

    except Exception as e:
        logger.warning(f"Technical analysis failed for {symbol}: {e}")
        return None

    except Exception as e:
        logger.warning(f"Technical analysis failed for {symbol}: {e}")
        return None


async def get_futures_top_long_short(
    limit: int = 20,
    min_volume: float = 10000000,
    timeframe: str = "1h"
) -> Dict[str, Any]:
    """
    Get top longs and shorts with technical analysis.

    Args:
        limit: Number of top gainers/losers to return (default 20)
        min_volume: Minimum 24h volume in USDT (default 10M)
        timeframe: Timeframe for technical analysis (default 1h)

    Returns:
        Dict with longs and shorts analysis
    """
    try:
        # Get top gainers/losers
        result = get_top_gainers_losers(limit=limit, min_volume=min_volume)
        longs = result["longs"]
        shorts = result["shorts"]

        logger.info(f"Analyzing {len(longs)} longs and {len(shorts)} shorts...")

        # Analyze each symbol
        analyzed_longs = []
        analyzed_shorts = []

        # Process longs (parallel for performance)
        async def analyze_long(item):
            symbol = item["symbol"]
            tech = analyze_symbol_technical(symbol, timeframe)
            return {
                **item,
                "technical": tech,
            }

        # Process shorts (parallel for performance)
        async def analyze_short(item):
            symbol = item["symbol"]
            tech = analyze_symbol_technical(symbol, timeframe)
            return {
                **item,
                "technical": tech,
            }

        # Run analysis concurrently
        long_tasks = [analyze_long(item) for item in longs]
        short_tasks = [analyze_short(item) for item in shorts]

        analyzed_longs = await asyncio.gather(*long_tasks)
        analyzed_shorts = await asyncio.gather(*short_tasks)

        # No longer filtering out None results as everything should return a dict now

        return {
            "longs": analyzed_longs,
            "shorts": analyzed_shorts,
            "count": {
                "longs": len(analyzed_longs),
                "shorts": len(analyzed_shorts),
            },
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "filters": {
                "limit": limit,
                "min_volume": min_volume,
                "timeframe": timeframe,
            }
        }

    except Exception as e:
        logger.error(f"Error in get_futures_top_long_short: {e}")
        return {"error": str(e), "longs": [], "shorts": []}