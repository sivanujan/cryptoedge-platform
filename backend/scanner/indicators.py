"""
indicators.py — Pure pandas/numpy technical indicators for the Breakout Scanner.
No ta-lib required.
"""
import numpy as np
import pandas as pd
from typing import Dict


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average using pandas ewm (wilder=False)."""
    return series.ewm(span=period, adjust=False).mean()


def calculate_rsi(series: pd.Series, period: int = 14) -> float:
    """
    RSI using Wilder's smoothing method.
    Returns the last RSI value as a float.
    """
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    # Wilder's smoothing = EMA with alpha = 1/period
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1])


def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """
    Average True Range using EMA of True Range.
    TR = max(High-Low, |High-PrevClose|, |Low-PrevClose|)
    Returns the last ATR value as a float.
    """
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)

    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    atr = tr.ewm(alpha=1 / period, adjust=False).mean()
    return float(atr.iloc[-1])


def calculate_vwap(df: pd.DataFrame) -> float:
    """
    Volume Weighted Average Price.
    TP = (High + Low + Close) / 3
    VWAP = sum(TP * Volume) / sum(Volume)
    Returns the cumulative VWAP over the entire provided DataFrame.
    """
    tp = (df["high"] + df["low"] + df["close"]) / 3
    vwap = (tp * df["volume"]).sum() / df["volume"].sum()
    return float(vwap)


def calculate_volume_ratio(df: pd.DataFrame, period: int = 20) -> float:
    """
    Current volume / average volume of last N candles (excluding current).
    Returns a ratio >= 0.
    """
    if len(df) < period + 1:
        return 1.0
    avg_vol = df["volume"].iloc[-(period + 1):-1].mean()
    current_vol = df["volume"].iloc[-1]
    if avg_vol == 0:
        return 1.0
    return float(current_vol / avg_vol)


def calculate_key_level(df: pd.DataFrame, lookback: int = 20) -> Dict[str, float]:
    """
    Identify the highest high (resistance) and lowest low (support)
    over the last `lookback` candles (excluding the current candle).
    Returns dict: {resistance: float, support: float}
    """
    subset = df.iloc[-(lookback + 1):-1]
    resistance = float(subset["high"].max())
    support = float(subset["low"].min())
    return {"resistance": resistance, "support": support}


def calculate_rs_vs_btc(coin_change_pct: float, btc_change_pct: float) -> float:
    """
    Simple Relative Strength vs BTC:
    RS = coin_change_pct - btc_change_pct
    Positive = outperforming BTC, Negative = underperforming.
    """
    return float(coin_change_pct - btc_change_pct)
