def rsi_oversold_bounce(symbol, df):
    """RSI < 35 LONG / RSI > 65 SHORT on 15m timeframe"""
    if len(df) < 2 or 'rsi_14' not in df.columns: return None
    rsi = df['rsi_14'].iloc[-1]
    if rsi < 35:
        return {"signal": "LONG", "confidence": 80, "reason": "RSI Oversold"}
    elif rsi > 65:
        return {"signal": "SHORT", "confidence": 80, "reason": "RSI Overbought"}
    return None

def macd_crossover(symbol, df):
    """MACD line crosses signal line entry"""
    if len(df) < 2 or 'macd' not in df.columns or 'macd_signal' not in df.columns: return None
    macd = df['macd'].iloc[-1]
    macd_sig = df['macd_signal'].iloc[-1]
    macd_prev = df['macd'].iloc[-2]
    macd_sig_prev = df['macd_signal'].iloc[-2]
    
    if macd > macd_sig and macd_prev <= macd_sig_prev:
        return {"signal": "LONG", "confidence": 75, "reason": "MACD Bullish Cross"}
    elif macd < macd_sig and macd_prev >= macd_sig_prev:
        return {"signal": "SHORT", "confidence": 75, "reason": "MACD Bearish Cross"}
    return None

def ema_stack_breakout(symbol, df):
    """Price breaks through aligned EMA 9/21/50 stack"""
    if len(df) < 2 or 'ema_9' not in df.columns: return None
    close = df['close'].iloc[-1]
    e9 = df['ema_9'].iloc[-1]
    e21 = df['ema_21'].iloc[-1]
    e50 = df['ema_50'].iloc[-1]
    
    if close > e9 and e9 > e21 and e21 > e50:
        return {"signal": "LONG", "confidence": 70, "reason": "EMA Bull Stack"}
    elif close < e9 and e9 < e21 and e21 < e50:
        return {"signal": "SHORT", "confidence": 70, "reason": "EMA Bear Stack"}
    return None

def volume_spike_entry(symbol, df):
    """2x average volume with price level break"""
    if len(df) < 20 or 'volume' not in df.columns: return None
    vol = df['volume'].iloc[-1]
    avg_vol = df['volume'].iloc[-20:-1].mean()
    close = df['close'].iloc[-1]
    open_p = df['open'].iloc[-1]
    
    if vol > avg_vol * 2:
        if close > open_p:
            return {"signal": "LONG", "confidence": 65, "reason": "Bullish Vol Spike"}
        else:
            return {"signal": "SHORT", "confidence": 65, "reason": "Bearish Vol Spike"}
    return None

AVAILABLE_STRATEGIES = {
    "RSI Oversold Bounce": rsi_oversold_bounce,
    "MACD Crossover": macd_crossover,
    "EMA Stack Breakout": ema_stack_breakout,
    "Volume Spike Entry": volume_spike_entry
}
