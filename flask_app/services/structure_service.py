import pandas as pd
import numpy as np

def calculate_structure_sl_tp(df: pd.DataFrame, entry_price: float, signal_type: str, global_sl_pct: float, global_tp_pct: float):
    """
    Find most recent unmitigated swing low/high and calculate SL/TP based on market structure.
    """
    if df is None or len(df) < 20:
        is_long = signal_type.upper() == "BUY"
        fallback_sl = entry_price * (1 - global_sl_pct/100) if is_long else entry_price * (1 + global_sl_pct/100)
        fallback_tp = entry_price * (1 + global_tp_pct/100) if is_long else entry_price * (1 - global_tp_pct/100)
        return {
            "structure_sl": fallback_sl,
            "structure_tp": fallback_tp,
            "sl_pct": global_sl_pct,
            "tp_pct": global_tp_pct,
            "rr_ratio": global_tp_pct / global_sl_pct if global_sl_pct > 0 else 0,
            "sl_method": "fallback_pct"
        }

    last_20 = df.tail(20)
    lower_wicks = last_20.apply(lambda row: min(row['open'], row['close']) - row['low'], axis=1)
    upper_wicks = last_20.apply(lambda row: row['high'] - max(row['open'], row['close']), axis=1)
    avg_lower_wick = lower_wicks.mean()
    avg_upper_wick = upper_wicks.mean()

    df_len = len(df)
    swing_lows = []
    swing_highs = []
    
    for i in range(3, df_len - 3):
        low = df.iloc[i]['low']
        high = df.iloc[i]['high']
        
        # Check swing low
        is_swing_low = True
        for j in range(i-3, i+4):
            if i == j: continue
            if df.iloc[j]['low'] <= low:
                is_swing_low = False
                break
        
        if is_swing_low:
            mitigated = False
            for j in range(i+1, df_len):
                if df.iloc[j]['close'] < low:
                    mitigated = True
                    break
            if not mitigated:
                swing_lows.append((df.index[i], low))
                
        # Check swing high
        is_swing_high = True
        for j in range(i-3, i+4):
            if i == j: continue
            if df.iloc[j]['high'] >= high:
                is_swing_high = False
                break
                
        if is_swing_high:
            mitigated = False
            for j in range(i+1, df_len):
                if df.iloc[j]['close'] > high:
                    mitigated = True
                    break
            if not mitigated:
                swing_highs.append((df.index[i], high))

    is_long = signal_type.upper() == "BUY"
    proposed_sl = None
    proposed_tp = None
    
    if is_long:
        valid_sls = [sl for sl in swing_lows if sl[1] < entry_price]
        if valid_sls:
            recent_sl = valid_sls[-1][1]
            proposed_sl = recent_sl - avg_lower_wick - (entry_price * 0.0015) # 0.15% buffer
            
        valid_tps = [tp for tp in swing_highs if tp[1] > entry_price]
        if valid_tps:
            proposed_tp = valid_tps[-1][1]
    else:
        valid_sls = [sh for sh in swing_highs if sh[1] > entry_price]
        if valid_sls:
            recent_sl = valid_sls[-1][1]
            proposed_sl = recent_sl + avg_upper_wick + (entry_price * 0.0015)
            
        valid_tps = [tp for tp in swing_lows if tp[1] < entry_price]
        if valid_tps:
            proposed_tp = valid_tps[-1][1]

    # Sanity checks
    fallback_sl = entry_price * (1 - global_sl_pct/100) if is_long else entry_price * (1 + global_sl_pct/100)
    fallback_tp = entry_price * (1 + global_tp_pct/100) if is_long else entry_price * (1 - global_tp_pct/100)
    
    sl_method = "fallback_pct"
    structure_sl = fallback_sl
    
    if proposed_sl is not None:
        sl_distance_pct = abs(entry_price - proposed_sl) / entry_price * 100
        if 0.3 <= sl_distance_pct <= 10.0:
            structure_sl = proposed_sl
            sl_method = "swing"
            
    if proposed_tp is not None:
        structure_tp = proposed_tp
    else:
        if sl_method == "swing":
            risk = abs(entry_price - structure_sl)
            structure_tp = entry_price + (risk * 2) if is_long else entry_price - (risk * 2)
        else:
            structure_tp = fallback_tp
            
    sl_pct = abs(entry_price - structure_sl) / entry_price * 100
    tp_pct = abs(entry_price - structure_tp) / entry_price * 100
    rr_ratio = tp_pct / sl_pct if sl_pct > 0 else 0
    
    return {
        "structure_sl": round(structure_sl, 8),
        "structure_tp": round(structure_tp, 8),
        "sl_pct": round(sl_pct, 4),
        "tp_pct": round(tp_pct, 4),
        "rr_ratio": round(rr_ratio, 2),
        "sl_method": sl_method
    }
