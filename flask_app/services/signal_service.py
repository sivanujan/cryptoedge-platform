import os
import json
import logging
import requests
from database.connection import SessionLocal
from database.models import Strategy, CoinResult, SignalHistory
from services.confidence_service import calculate_confidence_score

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Use a capable model for complex JSON generation, default to free Llama 3.3
SIGNAL_MODEL = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct:free") 

PROMPT_TEMPLATE = """
You are a senior crypto derivatives analyst performing a strict pre-trade audit on an algorithmically generated signal for a CRYPTO FUTURES (perpetual) market. This market trades 24/7 — do NOT use forex/stock session logic. Do NOT consider or reference the generating strategy's historical win rate, trade count, or past P&L — this must play NO role in the verdict.

INPUT DATA (provided per signal):
- Symbol: {coin}
- Timeframe: {timeframe}
- Direction: {direction}
- Entry and risk parameters: R:R ratio {rr_ratio}:1, SL method: {sl_method}, Account size: ${account_size}, Risk pct: {risk_pct}%
- Technical context & Indicators:
{extra_context}

You must calculate the following directly from the OHLCV candles provided. Show your derived values in the output.

=== LAYER 1: TREND & STRUCTURE (classic) ===
- Determine trend on signal timeframe and HTF using swing highs/lows: uptrend = sequence of higher highs + higher lows; downtrend = lower highs + lower lows; else "ranging".
- direction_alignment.aligned = true only if signal direction matches BOTH signal-timeframe trend AND HTF trend.

=== LAYER 2: ICT / SMART MONEY CONCEPTS ===
Calculate these from raw candles:

A) BOS / CHoCH (Break of Structure / Change of Character):
- Identify the last 3-5 significant swing points on the signal timeframe.
- BOS = price breaks and closes beyond the most recent swing high (bullish) or swing low (bearish) IN THE DIRECTION of the existing trend → confirms trend continuation.
- CHoCH = price breaks structure AGAINST the prevailing trend (e.g., in a downtrend, price closes above the most recent lower high) → early reversal warning.
- Report the most recent structure event and whether it supports or contradicts the signal direction.

B) Fair Value Gap (FVG):
- Scan the last 30-50 candles for 3-candle sequences where candle 1's high/low does not overlap with candle 3's low/high (a gap/imbalance).
- Bullish FVG = candle1.high < candle3.low (gap below candle 3). Bearish FVG = candle1.low > candle3.high (gap above candle 3).
- Check whether current entry price sits inside or very near (within 0.3x ATR) an unfilled FVG in the trade's favor. If entry is chasing price far away from any FVG or already deep past one, flag it as poor location.

C) Liquidity Zones / Sweeps:
- Identify recent equal highs or equal lows (within ~0.1% of each other) on the signal timeframe — these are liquidity pools where stop-losses cluster.
- Check if, in the last 5-10 candles, price spiked through one of these levels with a wick and then closed back on the other side (a "liquidity sweep"). A sweep followed by reversal in the signal's direction is a STRONG bullish confirmation factor. A signal placed with NO recent sweep, entering mid-range, is weaker.
- For a LONG: look for a sweep of a recent low (stop hunt below support) followed by bullish close. For a SHORT: sweep of a recent high followed by bearish close.

D) Order Block:
- Identify the last opposite-colored candle immediately preceding a strong impulsive move (3+ consecutive candles in one direction with expanding range/volume).
- That candle's high-low range is the order block zone. Check if current entry is at, or has recently retested, this zone. Entry far from any order block = weaker location.

=== LAYER 3: MOMENTUM ===
- Check RSI extremity (>70 long / <30 short = late-entry risk) and RSI-vs-price divergence over the last 10-20 candles.
- Check MACD histogram slope (expanding or fading).

=== LAYER 4: VOLATILITY & VOLUME ===
- Compare current ATR to its 20/50-period average → "expanding" / "contracting" / "normal".
- Compare current/entry candle volume to 20-period average volume.

=== LAYER 5: FUNDING RATE & OPEN INTEREST ===
- High positive funding + LONG signal = crowded long risk. High negative funding + SHORT signal = crowded short risk.
- OI rising + price rising = healthy trend continuation (supportive). OI rising + price falling = building short pressure. Falling OI during a move = position unwinding, not fresh conviction — lower confidence.

=== LAYER 6: BTC CORRELATION (altcoins only) ===
- If BTC trend strongly opposes the signal direction, flag as correlation risk.

=== LAYER 7: RISK/REWARD ===
- R:R = |TP - Entry| / |Entry - SL|. Below 1.5:1 = weak regardless of other confluence.

=== LAYER 8: CONTRADICTION CHECK ===
- Flag any case where classic trend/indicators and ICT structure disagree (e.g., EMA trend says up, but recent CHoCH just broke it down) — call this out explicitly since it's the highest-value red flag.

OUTPUT FORMAT (strict JSON only, return nothing else):
{{
  "verdict": "STRONG" | "MODERATE" | "WEAK_SKIP",
  "confidence_score": 0-100,
  "direction_alignment": {{
    "signal_timeframe_trend": "up"|"down"|"ranging",
    "htf_trend": "up"|"down"|"ranging",
    "aligned": true|false
  }},
  "ict_analysis": {{
    "structure_event": "BOS_bullish"|"BOS_bearish"|"CHoCH_bullish"|"CHoCH_bearish"|"none",
    "structure_supports_signal": true|false,
    "fvg_present_in_favor": true|false,
    "fvg_note": "string",
    "liquidity_sweep_detected": true|false,
    "liquidity_sweep_note": "string",
    "order_block_retest": true|false
  }},
  "momentum": {{
    "rsi_value": number,
    "rsi_divergence": "none"|"bullish"|"bearish"
  }},
  "risk_reward_ratio": {rr_ratio},
  "volatility_regime": "expanding"|"contracting"|"normal",
  "volume_ratio": number,
  "funding_rate_risk": "none"|"crowded_long"|"crowded_short"|"unknown",
  "open_interest_signal": "confirming"|"diverging"|"unwinding"|"unknown",
  "btc_correlation_risk": "none"|"altcoin_against_btc_trend"|"n/a_is_btc_or_eth",
  "confluence_reasons": [ "short factual bullet", ... ],
  "risk_warnings": [ "short factual bullet", ... ],
  "penalty_breakdown": [ {{ "reason": "string", "points": -N }} ],
  "final_reasoning": "2-3 sentence plain-language summary referencing the strongest 1-2 factors, including ICT structure if it was decisive",
  "expires_in_candles": 3
}}

RULES:
{rules}
"""

def get_higher_timeframe(tf: str) -> str:
    mapping = {
        "1m": "5m",
        "5m": "15m",
        "15m": "1h",
        "1h": "4h",
        "4h": "1d",
        "1d": "1w"
    }
    return mapping.get(tf, "1d")

def find_swing_points(df, window=3):
    """
    Find recent swing highs and swing lows (fractals).
    A high is a swing high if it's the maximum high in a window of 2*window + 1 candles.
    """
    import pandas as pd
    swing_highs = []
    swing_lows = []
    if df is None or len(df) < (window * 2 + 1):
        return swing_highs, swing_lows
        
    for i in range(window, len(df) - window):
        high_window = df['high'].iloc[i - window : i + window + 1]
        low_window = df['low'].iloc[i - window : i + window + 1]
        
        if df['high'].iloc[i] == high_window.max():
            swing_highs.append((df.index[i], df['high'].iloc[i]))
            
        if df['low'].iloc[i] == low_window.min():
            swing_lows.append((df.index[i], df['low'].iloc[i]))
            
    return swing_highs, swing_lows

def determine_swing_trend(df):
    if df is None or len(df) < 15:
        return "ranging"
    
    swing_highs, swing_lows = find_swing_points(df, window=3)
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return "ranging"
        
    last_highs = [sh[1] for sh in swing_highs[-2:]]
    last_lows = [sl[1] for sl in swing_lows[-2:]]
    
    if last_highs[-1] > last_highs[-2] and last_lows[-1] > last_lows[-2]:
        return "up"
    elif last_highs[-1] < last_highs[-2] and last_lows[-1] < last_lows[-2]:
        return "down"
    else:
        return "ranging"

def detect_bos_choch(df, direction):
    if df is None or len(df) < 20:
        return "none", False
        
    swing_highs, swing_lows = find_swing_points(df, window=3)
    if not swing_highs or not swing_lows:
        return "none", False
        
    last_close = df['close'].iloc[-1]
    
    import pandas as pd
    sma_50 = df['close'].rolling(window=20).mean()
    last_sma = sma_50.iloc[-1] if not sma_50.empty else None
    is_uptrend = last_close > last_sma if (last_sma is not None and pd.notnull(last_sma)) else True
    
    swing_highs.sort(key=lambda x: x[0])
    swing_lows.sort(key=lambda x: x[0])
    
    recent_df = df.iloc[-10:]
    
    bullish_break = False
    for idx, row in recent_df.iterrows():
        prev_highs = [sh[1] for sh in swing_highs if sh[0] < idx]
        if prev_highs and row['close'] > prev_highs[-1]:
            bullish_break = True
            break
            
    bearish_break = False
    for idx, row in recent_df.iterrows():
        prev_lows = [sl[1] for sl in swing_lows if sl[0] < idx]
        if prev_lows and row['close'] < prev_lows[-1]:
            bearish_break = True
            break
            
    event = "none"
    supports = False
    
    if bullish_break:
        if is_uptrend:
            event = "BOS_bullish"
        else:
            event = "CHoCH_bullish"
        supports = (direction == "LONG")
    elif bearish_break:
        if not is_uptrend:
            event = "BOS_bearish"
        else:
            event = "CHoCH_bearish"
        supports = (direction == "SHORT")
        
    return event, supports

def find_nearest_fvg(df, entry_price, direction, atr):
    if df is None or len(df) < 10:
        return False, "none nearby"
        
    fvg_present = False
    fvg_note = "none nearby"
    
    limit = min(50, len(df))
    sub = df.iloc[-limit:]
    
    bullish_fvgs = []
    bearish_fvgs = []
    
    for i in range(2, len(sub)):
        c1 = sub.iloc[i-2]
        c3 = sub.iloc[i]
        
        # Bullish FVG
        if c1['high'] < c3['low']:
            zone = (c1['high'], c3['low'])
            filled = False
            for j in range(i+1, len(sub)):
                if sub.iloc[j]['low'] < zone[0]:
                    filled = True
                    break
            if not filled:
                bullish_fvgs.append(zone)
                
        # Bearish FVG
        if c1['low'] > c3['high']:
            zone = (c3['high'], c1['low'])
            filled = False
            for j in range(i+1, len(sub)):
                if sub.iloc[j]['high'] > zone[1]:
                    filled = True
                    break
            if not filled:
                bearish_fvgs.append(zone)
                
    atr_threshold = 0.3 * atr if atr else 0.0
    
    if direction == "LONG" and bullish_fvgs:
        nearest = None
        min_dist = float('inf')
        for zone in bullish_fvgs:
            if zone[0] <= entry_price <= zone[1]:
                nearest = zone
                min_dist = 0
                break
            else:
                dist = min(abs(entry_price - zone[0]), abs(entry_price - zone[1]))
                if dist < min_dist:
                    min_dist = dist
                    nearest = zone
        if nearest:
            if min_dist == 0:
                fvg_present = True
                fvg_note = f"Entry sits inside unfilled Bullish FVG [{nearest[0]:.4f} - {nearest[1]:.4f}]"
            elif atr_threshold > 0 and min_dist <= atr_threshold:
                fvg_present = True
                fvg_note = f"Entry is within 0.3x ATR of unfilled Bullish FVG [{nearest[0]:.4f} - {nearest[1]:.4f}]"
            else:
                fvg_note = f"Nearest unfilled Bullish FVG is at [{nearest[0]:.4f} - {nearest[1]:.4f}]"
                
    elif direction == "SHORT" and bearish_fvgs:
        nearest = None
        min_dist = float('inf')
        for zone in bearish_fvgs:
            if zone[0] <= entry_price <= zone[1]:
                nearest = zone
                min_dist = 0
                break
            else:
                dist = min(abs(entry_price - zone[0]), abs(entry_price - zone[1]))
                if dist < min_dist:
                    min_dist = dist
                    nearest = zone
        if nearest:
            if min_dist == 0:
                fvg_present = True
                fvg_note = f"Entry sits inside unfilled Bearish FVG [{nearest[0]:.4f} - {nearest[1]:.4f}]"
            elif atr_threshold > 0 and min_dist <= atr_threshold:
                fvg_present = True
                fvg_note = f"Entry is within 0.3x ATR of unfilled Bearish FVG [{nearest[0]:.4f} - {nearest[1]:.4f}]"
            else:
                fvg_note = f"Nearest unfilled Bearish FVG is at [{nearest[0]:.4f} - {nearest[1]:.4f}]"
                
    return fvg_present, fvg_note

def detect_liquidity_sweep(df, direction):
    if df is None or len(df) < 15:
        return False, "no recent sweep"
        
    swing_highs, swing_lows = find_swing_points(df.iloc[:-10], window=3)
    if not swing_highs or not swing_lows:
        return False, "no recent sweep"
        
    recent_df = df.iloc[-10:]
    
    if direction == "LONG":
        for idx, row in recent_df.iterrows():
            valid_lows = [sl[1] for sl in swing_lows if sl[0] < idx]
            if not valid_lows:
                continue
            recent_low = valid_lows[-1]
            if row['low'] < recent_low and row['close'] > recent_low:
                return True, f"Liquidity sweep detected at low {row['low']:.4f} of recent support {recent_low:.4f}"
    else:
        for idx, row in recent_df.iterrows():
            valid_highs = [sh[1] for sh in swing_highs if sh[0] < idx]
            if not valid_highs:
                continue
            recent_high = valid_highs[-1]
            if row['high'] > recent_high and row['close'] < recent_high:
                return True, f"Liquidity sweep detected at high {row['high']:.4f} of recent resistance {recent_high:.4f}"
                
    return False, "no recent sweep"

def check_order_block(df, entry_price, direction):
    if df is None or len(df) < 15:
        return False
        
    for i in range(len(df) - 4, 2, -1):
        c0 = df.iloc[i-1]
        c1 = df.iloc[i]
        c2 = df.iloc[i+1]
        c3 = df.iloc[i+2]
        
        is_bullish_impulse = (
            c1['close'] > c1['open'] and 
            c2['close'] > c2['open'] and 
            c3['close'] > c3['open'] and
            c3['volume'] > df['volume'].iloc[i-5:i].mean()
        )
        if is_bullish_impulse and direction == "LONG" and c0['close'] < c0['open']:
            if c0['low'] * 0.995 <= entry_price <= c0['high'] * 1.005:
                return True
                
        is_bearish_impulse = (
            c1['close'] < c1['open'] and 
            c2['close'] < c2['open'] and 
            c3['close'] < c3['open'] and
            c3['volume'] > df['volume'].iloc[i-5:i].mean()
        )
        if is_bearish_impulse and direction == "SHORT" and c0['close'] > c0['open']:
            if c0['low'] * 0.995 <= entry_price <= c0['high'] * 1.005:
                return True
                
    return False

def detect_rsi_divergence(df):
    if df is None or len(df) < 15 or 'rsi_14' not in df.columns:
        return "none"
    
    sub = df.tail(15)
    lows_idx = []
    for i in range(1, len(sub)-1):
        if sub['low'].iloc[i] < sub['low'].iloc[i-1] and sub['low'].iloc[i] < sub['low'].iloc[i+1]:
            lows_idx.append(i)
            
    highs_idx = []
    for i in range(1, len(sub)-1):
        if sub['high'].iloc[i] > sub['high'].iloc[i-1] and sub['high'].iloc[i] > sub['high'].iloc[i+1]:
            highs_idx.append(i)
            
    if len(lows_idx) >= 2:
        i1, i2 = lows_idx[-2], lows_idx[-1]
        p1, p2 = sub['low'].iloc[i1], sub['low'].iloc[i2]
        r1, r2 = sub['rsi_14'].iloc[i1], sub['rsi_14'].iloc[i2]
        if p2 < p1 and r2 > r1:
            return "bullish"
            
    if len(highs_idx) >= 2:
        i1, i2 = highs_idx[-2], highs_idx[-1]
        p1, p2 = sub['high'].iloc[i1], sub['high'].iloc[i2]
        r1, r2 = sub['rsi_14'].iloc[i1], sub['rsi_14'].iloc[i2]
        if p2 > p1 and r2 < r1:
            return "bearish"
            
    return "none"

def format_candles_compact(df, limit=100):
    if df is None or df.empty:
        return "No candles available"
    sub = df.tail(limit)
    lines = []
    lines.append("Index (0=recent),Open,High,Low,Close,Volume")
    for i, (idx, row) in enumerate(sub.iterrows()):
        countdown = len(sub) - 1 - i
        o = f"{row['open']:.5f}"
        h = f"{row['high']:.5f}"
        l = f"{row['low']:.5f}"
        c = f"{row['close']:.5f}"
        v = f"{row['volume']:.2f}"
        lines.append(f"{countdown},{o},{h},{l},{c},{v}")
    return "\n".join(lines)

def get_derivatives_context(exchange, symbol, direction, timeframe, entry_price=None, df=None, df_htf=None, df_btc=None):
    """
    Fetch derivatives metrics and calculate ICT/SMC concepts.
    """
    import pandas as pd
    import numpy as np
    funding_rate = None
    open_interest = None
    btc_price = None
    btc_change = None
    volatility_regime = "normal"
    open_interest_signal = "unknown"
    btc_correlation_risk = "unknown"

    try:
        rate_data = exchange.fetch_funding_rate(symbol)
        if rate_data and 'fundingRate' in rate_data:
            funding_rate = rate_data['fundingRate']
    except Exception as e:
        logger.warning(f"Could not fetch funding rate for {symbol}: {e}")

    try:
        oi_data = exchange.fetch_open_interest(symbol)
        if oi_data and 'openInterestAmount' in oi_data:
            open_interest = oi_data['openInterestAmount']
    except Exception as e:
        logger.warning(f"Could not fetch open interest for {symbol}: {e}")

    try:
        btc_ticker = exchange.fetch_ticker('BTC/USDT:USDT')
        if btc_ticker:
            btc_price = btc_ticker.get('last')
            btc_change = btc_ticker.get('percentage')
    except Exception as e:
        logger.warning(f"Could not fetch BTC ticker: {e}")

    # Calculate Volatility Regime
    atr_val = None
    if df is not None and len(df) >= 64:
        try:
            high = df['high']
            low = df['low']
            close = df['close']
            
            tr1 = high - low
            tr2 = (high - close.shift(1)).abs()
            tr3 = (low - close.shift(1)).abs()
            
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=14).mean()
            atr_val = atr.iloc[-1]
            atr_sma = atr.rolling(window=50).mean()
            
            last_atr = atr.iloc[-1]
            last_atr_sma = atr_sma.iloc[-1]
            
            if pd.notnull(last_atr) and pd.notnull(last_atr_sma) and last_atr_sma > 0:
                if last_atr > last_atr_sma * 1.05:
                    volatility_regime = "expanding"
                elif last_atr < last_atr_sma * 0.95:
                    volatility_regime = "contracting"
                else:
                    volatility_regime = "normal"
        except Exception as e:
            logger.warning(f"Failed to calculate volatility regime: {e}")

    # Fetch Open Interest History to calculate OI trend
    try:
        oi_history = exchange.fetch_open_interest_history(symbol, timeframe, limit=5)
        if oi_history and len(oi_history) >= 2:
            first_oi = oi_history[0]['openInterestAmount']
            last_oi = oi_history[-1]['openInterestAmount']
            oi_change_pct = (last_oi - first_oi) / first_oi if first_oi > 0 else 0
            
            if df is not None and len(df) >= 5:
                price_change = df['close'].iloc[-1] - df['close'].iloc[-5]
                is_price_rising = price_change > 0
                is_oi_rising = oi_change_pct > 0.001
                is_oi_falling = oi_change_pct < -0.001
                
                signal_dir = "LONG" if direction == "LONG" else "SHORT"
                
                if is_oi_rising:
                    if (signal_dir == "LONG" and is_price_rising) or (signal_dir == "SHORT" and not is_price_rising):
                        open_interest_signal = "confirming"
                    else:
                        open_interest_signal = "diverging"
                elif is_oi_falling:
                    open_interest_signal = "unwinding"
                else:
                    open_interest_signal = "confirming"
    except Exception as e:
        logger.warning(f"Could not calculate open interest trend: {e}")

    # Calculate BTC Correlation Risk
    if btc_change is not None:
        if symbol.startswith("BTC") or symbol.startswith("ETH"):
            btc_correlation_risk = "n/a_is_btc_or_eth"
        else:
            btc_trend_up = btc_change > 0
            signal_dir = "LONG" if direction == "LONG" else "SHORT"
            if (signal_dir == "LONG" and not btc_trend_up) or (signal_dir == "SHORT" and btc_trend_up):
                btc_correlation_risk = "altcoin_against_btc_trend"
            else:
                btc_correlation_risk = "none"

    # Calculate swing trends
    signal_trend = determine_swing_trend(df)
    htf_trend = determine_swing_trend(df_htf)
    
    # Calculate BOS / CHoCH structure event
    structure_event, structure_supports_signal = detect_bos_choch(df, direction)
    
    # Calculate FVG presence in favor
    fvg_present_in_favor, fvg_note = find_nearest_fvg(df, entry_price or 0.0, direction, atr_val or 0.0)
    
    # Calculate Liquidity Zones / sweeps
    liquidity_sweep_detected, liquidity_sweep_note = detect_liquidity_sweep(df, direction)
    
    # Calculate Order Block retest
    order_block_retest = check_order_block(df, entry_price or 0.0, direction)
    
    # Calculate RSI values & divergences
    rsi_value = None
    if df is not None and not df.empty and 'rsi_14' in df.columns:
        rsi_val_last = df['rsi_14'].iloc[-1]
        if pd.notnull(rsi_val_last):
            rsi_value = float(rsi_val_last)
            
    rsi_divergence = detect_rsi_divergence(df)

    # Format indicators context block
    info = "[DERIVATIVES CONTEXT]\n"
    if funding_rate is not None:
        info += f"- Current Funding Rate: {funding_rate * 100:.6f}%\n"
    else:
        info += "- Current Funding Rate: Not Available\n"

    if open_interest is not None:
        info += f"- Open Interest Amount: {open_interest:,.2f} units\n"
    else:
        info += "- Open Interest: Not Available\n"

    if btc_price is not None:
        btc_change_str = f"{btc_change:+.2f}%" if btc_change is not None else "N/A"
        info += f"- BTC/USDT Price: ${btc_price:,.2f} (24h Change: {btc_change_str})\n"
    else:
        info += "- BTC Correlation Data: Not Available\n"

    info += f"- Volatility Regime: {volatility_regime}\n"
    info += f"- Open Interest Signal: {open_interest_signal}\n"
    info += f"- BTC Correlation Risk: {btc_correlation_risk}\n"
    
    info += "\n[SWING TREND ANALYSIS]\n"
    info += f"- Signal Timeframe Swing Trend: {signal_trend}\n"
    info += f"- HTF Swing Trend: {htf_trend}\n"
    
    info += "\n[ICT / SMART MONEY CONCEPTS]\n"
    info += f"- Structure Event: {structure_event}\n"
    info += f"- Structure Supports Signal: {structure_supports_signal}\n"
    info += f"- FVG Present In Favor: {fvg_present_in_favor}\n"
    info += f"- FVG Note: {fvg_note}\n"
    info += f"- Liquidity Sweep Detected: {liquidity_sweep_detected}\n"
    info += f"- Liquidity Sweep Note: {liquidity_sweep_note}\n"
    info += f"- Order Block Retest: {order_block_retest}\n"
    
    info += "\n[MOMENTUM CONTEXT]\n"
    info += f"- RSI Value: {rsi_value if rsi_value is not None else 'N/A'}\n"
    info += f"- RSI Divergence: {rsi_divergence}\n"
    
    info += "\n[RAW OHLCV CANDLES (SIGNAL TIMEFRAME - LAST 100)]\n"
    info += format_candles_compact(df, limit=100) + "\n"
    
    info += "\n[RAW OHLCV CANDLES (HTF TIMEFRAME - LAST 50)]\n"
    info += format_candles_compact(df_htf, limit=50) + "\n"
    
    if df_btc is not None and not df_btc.empty:
        info += "\n[RAW OHLCV CANDLES (BTC/USDT - LAST 50)]\n"
        info += format_candles_compact(df_btc, limit=50) + "\n"

    return info

def generate_signal_stream(db, strategy_id, coin, timeframe, direction, rr_ratio, sl_method, account_size, risk_pct, extra_context, entry_price=None, sl_price=None, tp_price=None, severity='BALANCED'):
    """
    Generate a signal using AI and stream the response.
    """
    # 1. Fetch data
    strategy = db.query(Strategy).filter_by(id=strategy_id).first()
    coin_result = db.query(CoinResult).filter_by(strategy_id=strategy_id, coin=coin).first()
    
    if not strategy:
        yield "Error: Strategy not found"
        return

    # Add severity instructions to extra_context
    severity_instruction = ""
    sev_upper = severity.upper() if severity else "BALANCED"
    if sev_upper == 'STRICT':
        severity_instruction = (
            "AUDIT SEVERITY: STRICT. Evaluate with maximum skepticism. "
            "Enforce all rules and penalties strictly. Deduct maximum points for any trend misalignment, "
            "RSI divergence, low volume ratio, or BTC correlation anomalies. Cautiously label signals as WEAK_SKIP if any layer fails."
        )
    elif sev_upper == 'BALANCED':
        severity_instruction = (
            "AUDIT SEVERITY: BALANCED. Be skeptical but fair. "
            "If the HTF trend is 'ranging' instead of actively opposing, do not penalize the direction alignment (aligned can be true if local trend matches signal). "
            "Standard indicator penalties apply."
        )
    elif sev_upper == 'LENIENT':
        severity_instruction = (
            "AUDIT SEVERITY: LENIENT. Prioritize favorable Risk-Reward ratios and ICT-based zone locations (order blocks, FVGs). "
            "Ignore minor volume ratio issues (do not penalize if volume_ratio > 0.6) and do not penalize for minor RSI divergences. "
            "Only penalize direction alignment if the HTF trend is actively opposing the signal direction (e.g. LONG signal into a down HTF trend)."
        )
    extra_context = f"=== AUDIT MODE: {sev_upper} ===\n{severity_instruction}\n\n{extra_context or ''}"

    # Fetch OHLCV data to get current price, indicators, and trend
    from services.binance_service import get_ohlcv, get_current_price
    from services.indicator_service import add_all_indicators
    import pandas as pd

    df = get_ohlcv(coin, timeframe, limit=200)
    
    htf_timeframe = get_higher_timeframe(timeframe)
    df_htf = get_ohlcv(coin, htf_timeframe, limit=100)
    
    df_btc = None
    if coin != "BTC/USDT:USDT" and coin != "BTCUSDT":
        df_btc = get_ohlcv("BTC/USDT:USDT", timeframe, limit=100)
    trend_str = "neutral"
    trend_details = ""
    last_close = None

    if df is not None and not df.empty:
        df = add_all_indicators(df)
        df = df.dropna()
        if not df.empty:
            last_row = df.iloc[-1]
            last_close = float(last_row["close"])
            ema_21 = last_row.get("ema_21", None)
            ema_50 = last_row.get("ema_50", None)
            ema_200 = last_row.get("ema_200", None)

            if pd.notnull(ema_21) and pd.notnull(ema_50):
                if last_close > ema_50 and ema_21 > ema_50:
                    trend_str = "uptrend"
                elif last_close < ema_50 and ema_21 < ema_50:
                    trend_str = "downtrend"
            
            ema_21_str = f"{ema_21:.6f}" if pd.notnull(ema_21) else "N/A"
            ema_50_str = f"{ema_50:.6f}" if pd.notnull(ema_50) else "N/A"
            ema_200_str = f"{ema_200:.6f}" if pd.notnull(ema_200) else "N/A"
            
            trend_details = (
                f"Price: {last_close:.6f}, EMA_21: {ema_21_str}, "
                f"EMA_50: {ema_50_str}, EMA_200: {ema_200_str}"
            )

    # Resolve entry_price, sl_price, tp_price if None or 0
    if not entry_price or entry_price == 0:
        if last_close is not None:
            entry_price = last_close
        else:
            entry_price = get_current_price(coin) or 0.0

    if not sl_price or not tp_price or sl_price == 0 or tp_price == 0:
        from database.models import Setting
        default_sl = 2.0
        default_tp = 4.0
        setting_rows = db.query(Setting).all()
        settings = {row.key: row.value for row in setting_rows}
        global_sl = float(settings.get("default_sl_pct", default_sl))
        global_tp = float(settings.get("default_tp_pct", default_tp))

        from services.structure_service import calculate_structure_sl_tp
        struct_dir = direction if direction in ["LONG", "SHORT"] else ("LONG" if trend_str == "uptrend" else "SHORT")
        
        # If we have a dataframe, calculate structure-based SL/TP
        if df is not None and not df.empty:
            struct_data = calculate_structure_sl_tp(df, entry_price, "BUY" if struct_dir == "LONG" else "SELL", global_sl, global_tp)
            if not sl_price or sl_price == 0:
                sl_price = struct_data["structure_sl"]
            if not tp_price or tp_price == 0:
                tp_price = struct_data["structure_tp"]
        else:
            # Fallback pct-based SL/TP
            if struct_dir == "LONG":
                if not sl_price or sl_price == 0:
                    sl_price = entry_price * (1 - global_sl / 100)
                if not tp_price or tp_price == 0:
                    tp_price = entry_price * (1 + global_tp / 100)
            else:
                if not sl_price or sl_price == 0:
                    sl_price = entry_price * (1 + global_sl / 100)
                if not tp_price or tp_price == 0:
                    tp_price = entry_price * (1 - global_tp / 100)

    # Bias direction based on detected trend if direction is 'both'
    if direction == "both":
        if trend_str == "uptrend":
            direction = "LONG"
        elif trend_str == "downtrend":
            direction = "SHORT"
        else:
            direction = "LONG" # Fallback bias

    # Add trend check context to extra_context
    trend_info = f"[TREND CHECK: {trend_str.upper()} | {trend_details}]\n"
    if df is not None and not df.empty:
        last_row = df.iloc[-1]
        rsi_val = last_row.get("rsi_14", None)
        macd_val = last_row.get("macd", None)
        macd_sig_val = last_row.get("macd_signal", None)
        vol_ratio_val = last_row.get("volume_ratio", None)
        rsi_str = f"{rsi_val:.2f}" if pd.notnull(rsi_val) else "N/A"
        macd_str = f"{macd_val:.6f}" if pd.notnull(macd_val) else "N/A"
        macd_sig_str = f"{macd_sig_val:.6f}" if pd.notnull(macd_sig_val) else "N/A"
        vol_ratio_str = f"{vol_ratio_val:.2f}" if pd.notnull(vol_ratio_val) else "N/A"
        trend_info += (
            f"[INDICATORS | RSI_14: {rsi_str}, "
            f"MACD: {macd_str}, MACD_Signal: {macd_sig_str}, "
            f"Volume_Ratio: {vol_ratio_str}]\n"
        )
    # Fetch real-time derivatives data to supply funding, open interest, and btc trend correlation
    from services.binance_service import get_swap_exchange
    exchange = get_swap_exchange()
    deriv_info = get_derivatives_context(
        exchange=exchange,
        symbol=coin,
        direction=direction,
        timeframe=timeframe,
        entry_price=entry_price,
        df=df,
        df_htf=df_htf,
        df_btc=df_btc
    )
    extra_context = trend_info + deriv_info + (extra_context or "")
        
    # Get results for specific timeframe
    tf_data = {}
    if coin_result and coin_result.tf_results:
        tf_data = coin_result.tf_results.get(timeframe, {})
        
    win_rate = tf_data.get("win_rate", 0.0)
    trades = tf_data.get("trades", 0)
    
    # 2. Calculate confidence score
    score_data = calculate_confidence_score(
        win_rate=win_rate,
        trades=trades,
        coins_tested=strategy.coins_tested or 0,
        coins_above_65=strategy.coins_above_65 or 0,
        return_pct=coin_result.return_pct if coin_result else 0.0,
        drawdown=coin_result.drawdown if coin_result else 0.0
    )
    
    # 3. Build prompt rules based on severity
    rules = ""
    sev_upper = severity.upper() if severity else "BALANCED"
    if sev_upper == 'STRICT':
        rules = (
            "- Never output \"STRONG\" if direction_alignment.aligned is false, unless ict_analysis.structure_event shows a confirmed CHoCH + retest supporting the NEW direction.\n"
            "- Never output \"STRONG\" if risk_reward_ratio < 1.5.\n"
            "- Never output \"STRONG\" unless at least ONE of (fvg_present_in_favor, liquidity_sweep_detected, order_block_retest) is true — entries with zero ICT-based location confluence should be capped at \"MODERATE\" at best.\n"
            "- If volume_ratio is below 0.8, cap verdict at \"MODERATE\" regardless of other factors.\n"
            "- Do NOT reference forex/stock trading sessions as a factor.\n"
            "- Do NOT reference strategy win rate, trade count, or historical performance anywhere in output.\n"
            "- If funding rate or open interest data is not provided, set those fields to \"unknown\" and do not penalize for missing data.\n"
            "- Be highly skeptical by default. If in doubt, lean toward WEAK_SKIP."
        )
    elif sev_upper == 'BALANCED':
        rules = (
            "- Never output \"STRONG\" if direction_alignment.aligned is false, unless HTF trend is ranging or there is an ICT structure break (BOS/CHoCH) supporting the signal.\n"
            "- Never output \"STRONG\" if risk_reward_ratio < 1.5.\n"
            "- entries with zero ICT-based location confluence should be capped at \"MODERATE\" at best.\n"
            "- If volume_ratio is below 0.8, cap verdict at \"MODERATE\".\n"
            "- Do NOT reference forex/stock trading sessions as a factor.\n"
            "- Do NOT reference strategy win rate, trade count, or historical performance anywhere in output.\n"
            "- If funding rate or open interest data is not provided, set those fields to \"unknown\".\n"
            "- Be skeptical but fair."
        )
    else:  # LENIENT
        rules = (
            "- You may output \"STRONG\" or \"MODERATE\" even if direction_alignment.aligned is false, as long as the local timeframe trend matches the signal direction and HTF trend is ranging (not opposing).\n"
            "- You may output \"STRONG\" if risk_reward_ratio >= 1.5.\n"
            "- Do not penalize or cap the score for minor volume ratio drops (only cap at \"MODERATE\" if volume_ratio is extremely low, below 0.4).\n"
            "- Do not penalize for minor RSI divergences or normal volatility regimes.\n"
            "- Prioritize high Risk-Reward and local order block or FVG entries. Be generous with the confidence score (allow scores above 75 if local structure is solid).\n"
            "- If funding rate or open interest data is not provided, set those fields to \"unknown\"."
        )

    prompt = PROMPT_TEMPLATE.format(
        strategy_name=strategy.name,
        coin=coin,
        timeframe=timeframe,
        win_rate=win_rate,
        trades=trades,
        return_pct=coin_result.return_pct if coin_result else 0.0,
        drawdown=coin_result.drawdown if coin_result else 0.0,
        score=score_data["score"],
        grade=score_data["grade"],
        coins_tested=strategy.coins_tested or 0,
        coins_above_65=strategy.coins_above_65 or 0,
        direction=direction,
        rr_ratio=rr_ratio,
        sl_method=sl_method,
        account_size=account_size,
        risk_pct=risk_pct,
        extra_context=extra_context,
        rules=rules
    )
    
    # 4. Call OpenRouter with streaming
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "http://localhost:5174",
        "X-Title": "CryptoEdge Signal Generator",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": SIGNAL_MODEL,
        "messages": [
            {"role": "system", "content": "You are a precise JSON generator. Output ONLY valid JSON."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.2,
        "stream": True
    }
    
    try:
        resp = requests.post(OPENROUTER_URL, json=payload, headers=headers, stream=True, timeout=180)
        
        full_content = ""
        for line in resp.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith("data: "):
                    data_str = line_str[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        content = data["choices"][0]["delta"].get("content", "")
                        full_content += content
                        yield content
                    except:
                        pass
                        
        # 5. Save to history after stream completes
        try:
            if not full_content:
                logger.error(f"OpenRouter returned empty content. Response status: {resp.status_code}")
                try:
                    logger.error(f"Raw response text: {resp.text}")
                except:
                    pass
            
            # Try to parse the full content to extract verdict and score
            try:
                import re
                json_match = re.search(r'\{[\s\S]*\}', full_content)
                if json_match:
                    signal_json = json.loads(json_match.group(0))
                else:
                    signal_json = json.loads(full_content)
                
                verdict_val = signal_json.get("verdict", signal_json.get("grade", "WEAK_SKIP"))
                if verdict_val in ["STRONG", "MODERATE", "PREMIUM", "GOOD", "TAKE"]:
                    verdict = "TAKE"
                else:
                    verdict = "SKIP"
                confidence = signal_json.get("confidence_score", signal_json.get("final_score", 0.0))
                validity_score = float(confidence) / 10.0
            except Exception as json_err:
                logger.warning(f"Failed to parse AI JSON: {json_err}. Using rule-based fallback for execution.")
                
                # Calculate quantity based on risk
                risk_amount = account_size * risk_pct / 100.0
                risk_per_unit = abs(entry_price - sl_price)
                qty = risk_amount / risk_per_unit if risk_per_unit > 0 else 0.0
                
                signal_json = {
                    "direction": "LONG" if tp_price > entry_price else "SHORT",
                    "grade": "GOOD",
                    "final_score": 75,
                }
                verdict = "TAKE"
                validity_score = 7.5
            
            history = SignalHistory(
                strategy_id=strategy_id,
                coin=coin,
                timeframe=timeframe,
                verdict=verdict,
                validity_score=validity_score,
                full_signal=signal_json,
                outcome="Pending"
            )
            db.add(history)
            db.commit()
            logger.info(f"Saved signal history for {coin}")
            
            # 6. Execute AI signal if AutoTrader is enabled and verdict is TAKE
            if verdict == "TAKE":
                execute_ai_signal(db, signal_json, coin, direction, entry_price, sl_price, tp_price, account_size, risk_pct)
            
        except Exception as e:
            logger.error(f"Failed to save signal history or execute trade: {e}")
            logger.error(f"Full content was: {full_content}")
            
    except Exception as e:
        logger.exception(f"Error in generate_signal_stream: {e}")
        yield f"Error: {e}"


def execute_ai_signal(db, signal_json, coin, direction=None, entry_price=0, sl_price=0, tp_price=0, account_size=10000.0, risk_pct=1.0):
    """
    Execute the AI signal if AutoTrader is enabled.
    """
    from autotrader.engine import get_settings
    from autotrader import binance_executor
    from database.models import AutoTrade
    
    settings = get_settings(db)
    if not settings.is_enabled:
        logger.info("AutoTrader is disabled. Skipping execution.")
        return
        
    try:
        grade = signal_json.get("verdict", signal_json.get("grade", "NO_SIGNAL"))
        if grade not in ["PREMIUM", "GOOD", "STRONG", "MODERATE", "TAKE"]:
            logger.info(f"Grade/verdict is {grade}. Skipping execution.")
            return
            
        # Infer direction
        if not direction:
            direction = signal_json.get("direction", "")
        if not direction or direction == "NO_SIGNAL":
            logger.warning("No direction in signal. Cannot execute.")
            return
            
        is_long = direction == "LONG"
        
        if not entry_price or not tp_price or not sl_price:
            logger.warning("Missing price levels in arguments. Cannot execute AI signal.")
            return
            
        side = "LONG" if is_long else "SHORT"
        binance_side = "BUY" if is_long else "SELL"
        stop_side = "SELL" if is_long else "BUY"
        
        # Calculate quantity based on risk
        risk_amount = account_size * risk_pct / 100.0
        risk_per_unit = abs(entry_price - sl_price)
        qty = risk_amount / risk_per_unit if risk_per_unit > 0 else 0.0
        
        leverage = settings.leverage
        
        if not qty or qty <= 0:
            logger.warning("Calculated quantity is invalid. Cannot execute.")
            return
            
        symbol_base = coin.replace('/', '').replace(':USDT', '')
        
        # Set leverage
        binance_executor.set_leverage(symbol_base, leverage)
        
        # Place Market Order
        logger.info(f"Placing AI signal order: {binance_side} {qty} {symbol_base} at {entry_price}")
        order_result = binance_executor.place_market_order(symbol_base, binance_side, qty)
        
        if order_result:
            logger.info(f"Order placed successfully: {order_result.get('orderId')}")
            
            sl_price = stop_loss.get("price")
            # Place SL and TP
            if sl_price:
                binance_executor.place_stop_market_order(symbol_base, stop_side, qty, sl_price)
            if tp1_price:
                binance_executor.place_take_profit_market_order(symbol_base, stop_side, qty, tp1_price)
                
            # Save to AutoTrade table to track it
            new_trade = AutoTrade(
                symbol=coin, side=side, entry_price=entry_price, quantity=qty,
                leverage=leverage, margin_used=position_size.get("position_size_usd", 0),
                strategy_name="AI Signal Engine", sl_price=sl_price or 0, 
                tp1=tp1_price or 0, tp2=take_profit.get("tp2_price") or 0, tp3=0,
                status="OPEN"
            )
            db.add(new_trade)
            db.commit()
            logger.info(f"Saved auto trade for {coin}")
            
    except Exception as e:
        logger.exception(f"Error executing AI signal: {e}")
