"""
signal_filter.py — Breakout Signal Filters & Scorer.
Evaluates whether a coin passes the confluence checklist for trade entry.
"""
from typing import Dict, Any


# ─────────────────────────────────────────────
#  Individual Filter Functions (return bool)
# ─────────────────────────────────────────────

def check_volume_ratio(volume_ratio: float) -> bool:
    """Volume spike check: current volume must be >= 2x average."""
    return volume_ratio >= 2.0


def check_rs_vs_btc(rs: float, direction: str) -> bool:
    """
    Relative Strength vs BTC:
    LONG  → coin outperforming BTC by > 3%
    SHORT → coin underperforming BTC by > 3%
    """
    if direction == "LONG":
        return rs > 3.0
    elif direction == "SHORT":
        return rs < -3.0
    return False


def check_key_level_break(price: float, levels: Dict[str, float], direction: str) -> bool:
    """
    Price must break through a key structural level:
    LONG  → price > resistance (breakout above)
    SHORT → price < support    (breakdown below)
    """
    if direction == "LONG":
        return price > levels.get("resistance", float("inf"))
    elif direction == "SHORT":
        return price < levels.get("support", 0.0)
    return False


def check_rsi(rsi: float, direction: str) -> bool:
    """
    RSI momentum filter:
    LONG  → 45 <= RSI <= 72 (strong but not overbought)
    SHORT → 28 <= RSI <= 55 (weak but not oversold)
    """
    if direction == "LONG":
        return 45 <= rsi <= 72
    elif direction == "SHORT":
        return 28 <= rsi <= 55
    return False


def check_vwap(price: float, vwap: float, direction: str) -> bool:
    """
    VWAP position filter:
    LONG  → price is above VWAP (bullish bias)
    SHORT → price is below VWAP (bearish bias)
    """
    if direction == "LONG":
        return price > vwap
    elif direction == "SHORT":
        return price < vwap
    return False


# ─────────────────────────────────────────────
#  Main Evaluation Function
# ─────────────────────────────────────────────

def evaluate_signal(
    indicators_dict: Dict[str, Any],
    current_price: float,
    direction: str,
) -> Dict[str, Any]:
    """
    Run all 5 checks and calculate a confluence score.
    A signal is valid only if score >= 4 (out of 5).

    indicators_dict keys expected:
      - volume_ratio: float
      - rs_vs_btc: float
      - key_levels: {resistance: float, support: float}
      - rsi: float
      - vwap: float
      - atr: float

    Returns:
      {
        valid: bool,     # True only if score >= 4
        score: int,      # 0-5
        checks: dict,    # individual check results
        sl: float,       # stop loss price
        tp1: float,      # take profit 1 (2R)
        tp2: float,      # take profit 2 (3R)
      }
    """
    vr = indicators_dict.get("volume_ratio", 0.0)
    rs = indicators_dict.get("rs_vs_btc", 0.0)
    levels = indicators_dict.get("key_levels", {"resistance": 0.0, "support": 0.0})
    rsi = indicators_dict.get("rsi", 50.0)
    vwap = indicators_dict.get("vwap", current_price)
    atr = indicators_dict.get("atr", current_price * 0.01)

    checks = {
        "volume_ratio": check_volume_ratio(vr),
        "rs_vs_btc": check_rs_vs_btc(rs, direction),
        "key_level_break": check_key_level_break(current_price, levels, direction),
        "rsi": check_rsi(rsi, direction),
        "vwap": check_vwap(current_price, vwap, direction),
    }

    score = sum(1 for v in checks.values() if v)
    valid = score >= 4

    # Risk = 1R = distance to stop loss
    if direction == "LONG":
        sl = current_price - 1.5 * atr
        tp1 = current_price + 2 * (current_price - sl)
        tp2 = current_price + 3 * (current_price - sl)
    else:  # SHORT
        sl = current_price + 1.5 * atr
        tp1 = current_price - 2 * (sl - current_price)
        tp2 = current_price - 3 * (sl - current_price)

    return {
        "valid": valid,
        "score": score,
        "checks": checks,
        "sl": round(sl, 8),
        "tp1": round(tp1, 8),
        "tp2": round(tp2, 8),
    }
