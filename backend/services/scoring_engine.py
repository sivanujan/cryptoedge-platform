import pandas as pd
from datetime import datetime, timezone

def calculate_signal_score(df: pd.DataFrame, current_price: float, direction_bias: str) -> dict:
    """
    Pure Python implementation of the CryptoEdge Signal Engine.
    Evaluates LONG and SHORT scores out of 100 based on the 100-point 
    strict multi-layer evaluation system (Trend, Momentum, Volume, Price Action, ICT Concepts).
    """
    if df is None or df.empty:
        return {"grade": "NO_SIGNAL", "final_score": 0, "direction": "NO_SIGNAL"}
        
    last_row = df.iloc[-1]
    
    # ───────────────────────────────────────
    # EXTRACT INDICATORS (with safe fallbacks)
    # ───────────────────────────────────────
    ema_21 = last_row.get("ema_21", None)
    ema_50 = last_row.get("ema_50", None)
    ema_200 = last_row.get("ema_200", None)
    adx = last_row.get("adx", None)
    supertrend = last_row.get("supertrend_dir", None) # 1 for bull, -1 for bear
    
    rsi = last_row.get("rsi_14", None)
    macd = last_row.get("macd", None)
    macd_signal = last_row.get("macd_signal", None)
    stoch_rsi = last_row.get("stoch_rsi", None)
    
    vol = last_row.get("volume", 0)
    vol_sma = last_row.get("volume_sma", vol)
    cvd = last_row.get("cvd", None)
    vwap = last_row.get("vwap", None)
    
    # Price action / ICT proxies
    near_support = last_row.get("near_support", False)
    near_resistance = last_row.get("near_resistance", False)
    bb_width = last_row.get("bb_width", 100)
    bb_squeeze = bb_width < 0.05 if pd.notnull(bb_width) else False
    
    fvg_bull = last_row.get("fvg_bullish", False)
    fvg_bear = last_row.get("fvg_bearish", False)
    bos_bull = last_row.get("bos_bullish", False)
    bos_bear = last_row.get("bos_bearish", False)
    swept_lows = last_row.get("swept_lows", False)
    swept_highs = last_row.get("swept_highs", False)
    
    long_score = 0
    short_score = 0
    reasons = []
    penalties = []
    
    # ───────────────────────────────────────
    # LAYER 1 — TREND (20 pts)
    # ───────────────────────────────────────
    if pd.notnull(ema_21):
        if current_price > ema_21: long_score += 5
        if current_price < ema_21: short_score += 5
        if pd.notnull(ema_50):
            if ema_21 > ema_50: long_score += 5
            if ema_21 < ema_50: short_score += 5
            
    if pd.notnull(adx) and adx > 25:
        long_score += 5
        short_score += 5
        
    if pd.notnull(supertrend):
        if supertrend == 1 or supertrend == "bullish": long_score += 5
        if supertrend == -1 or supertrend == "bearish": short_score += 5

    # ───────────────────────────────────────
    # LAYER 2 — MOMENTUM (20 pts)
    # ───────────────────────────────────────
    if pd.notnull(rsi):
        if 45 <= rsi <= 65: long_score += 7
        if 35 <= rsi <= 55: short_score += 7
        
    if pd.notnull(macd) and pd.notnull(macd_signal):
        if macd > macd_signal: long_score += 7
        if macd < macd_signal: short_score += 7
        
    if pd.notnull(stoch_rsi):
        if stoch_rsi > 50: long_score += 6
        if stoch_rsi < 50: short_score += 6

    # ───────────────────────────────────────
    # LAYER 3 — VOLUME (20 pts)
    # ───────────────────────────────────────
    if pd.notnull(vol_sma) and vol_sma > 0 and vol > (1.5 * vol_sma):
        long_score += 7
        short_score += 7
        
    if pd.notnull(cvd):
        if cvd > 0: long_score += 7
        if cvd < 0: short_score += 7
        
    if pd.notnull(vwap):
        if current_price > vwap: long_score += 6
        if current_price < vwap: short_score += 6

    # ───────────────────────────────────────
    # LAYER 4 — PRICE ACTION (20 pts)
    # ───────────────────────────────────────
    if near_support: long_score += 10
    if near_resistance: short_score += 10
    if bb_squeeze:
        long_score += 5
        short_score += 5
        
    if last_row.get("fib_ote_bull", False): long_score += 5
    if last_row.get("fib_ote_bear", False): short_score += 5

    # ───────────────────────────────────────
    # LAYER 5 — ICT CONCEPTS (20 pts)
    # ───────────────────────────────────────
    if fvg_bull: long_score += 7
    if fvg_bear: short_score += 7
    if bos_bull: long_score += 7
    if bos_bear: short_score += 7
    if swept_lows: long_score += 6
    if swept_highs: short_score += 6
    
    # ═══════════════════════════════════════
    # PENALTY SYSTEM
    # ═══════════════════════════════════════
    long_penalty = 0
    short_penalty = 0
    
    if pd.notnull(rsi):
        if rsi > 75: 
            long_penalty += 10
            penalties.append("LONG penalty: RSI > 75 (overbought)")
        if rsi < 25: 
            short_penalty += 10
            penalties.append("SHORT penalty: RSI < 25 (oversold)")
            
    if pd.notnull(ema_200):
        if current_price < ema_200:
            long_penalty += 8
            penalties.append("LONG penalty: Price BELOW EMA 200")
        if current_price > ema_200:
            short_penalty += 8
            penalties.append("SHORT penalty: Price ABOVE EMA 200")
            
    if pd.notnull(cvd):
        if cvd < -1000: 
            long_penalty += 7
            penalties.append("LONG penalty: strongly negative CVD")
        if cvd > 1000:
            short_penalty += 7
            penalties.append("SHORT penalty: strongly positive CVD")
            
    now = datetime.now(timezone.utc)
    hour = now.hour
    if 0 <= hour < 3:
        long_penalty += 5
        short_penalty += 5
        penalties.append("Session penalty: Asian session (low volatility)")
    elif 7 <= hour < 9:
        long_score += 5
        short_score += 5
        reasons.append("Session bonus: London Open")
    elif 13 <= hour < 15:
        long_score += 5
        short_score += 5
        reasons.append("Session bonus: NY Open")

    long_score -= long_penalty
    short_score -= short_penalty
    
    # Check direction bias from the scanner
    final_dir = str(direction_bias).upper()
    if final_dir == "LONG" or final_dir == "BUY":
        final_dir = "LONG"
        final_score = long_score
    elif final_dir == "SHORT" or final_dir == "SELL":
        final_dir = "SHORT"
        final_score = short_score
    else:
        if long_score > short_score:
            final_dir = "LONG"
            final_score = long_score
        else:
            final_dir = "SHORT"
            final_score = short_score
            
    # Cap scores
    final_score = max(0, min(100, final_score))
    
    if final_score < 51:
        grade = "NO_SIGNAL"
    elif final_score >= 86:
        grade = "PREMIUM"
    elif final_score >= 71:
        grade = "GOOD"
    else:
        grade = "WEAK"
        
    return {
        "direction": final_dir,
        "long_score": max(0, min(100, long_score)),
        "short_score": max(0, min(100, short_score)),
        "final_score": final_score,
        "grade": grade,
        "htf_confirmed": False, # Assuming no HTF passed
        "session": "asian" if 0 <= hour < 3 else "london" if 7 <= hour < 12 else "ny",
        "reasons": reasons,
        "penalties": penalties,
        "timestamp": now.isoformat()
    }
