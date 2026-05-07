import logging
import pandas as pd

logger = logging.getLogger(__name__)

# Try pandas_ta first, fall back to ta library
try:
    import pandas_ta as pta
    _USE_PTA = True
except ImportError:
    _USE_PTA = False
    try:
        import ta
        _USE_TA = True
    except ImportError:
        _USE_TA = False
        logger.warning("Neither pandas_ta nor ta is installed. Indicators will be calculated manually.")
    try:
        import numpy as np
        _USE_NP = True
    except ImportError:
        _USE_NP = False


def add_ema(df: pd.DataFrame, period: int, column: str = "close") -> pd.DataFrame:
    """Add EMA column to dataframe."""
    col_name = f"ema_{period}"
    if _USE_PTA:
        df[col_name] = pta.ema(df[column], length=period)
    else:
        df[col_name] = df[column].ewm(span=period, adjust=False).mean()
    return df


def add_rsi(df: pd.DataFrame, period: int = 14, column: str = "close") -> pd.DataFrame:
    """Add RSI column to dataframe."""
    col_name = f"rsi_{period}"
    if _USE_PTA:
        df[col_name] = pta.rsi(df[column], length=period)
    elif _USE_TA:
        import ta as ta_lib
        df[col_name] = ta_lib.momentum.RSIIndicator(close=df[column], window=period).rsi()
    else:
        delta = df[column].diff()
        gain = delta.clip(lower=0).rolling(period).mean()
        loss = (-delta.clip(upper=0)).rolling(period).mean()
        rs = gain / loss
        df[col_name] = 100 - (100 / (1 + rs))
    return df


def add_macd(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
    column: str = "close",
) -> pd.DataFrame:
    """Add MACD, MACD signal, and MACD histogram columns."""
    if _USE_PTA:
        macd = pta.macd(df[column], fast=fast, slow=slow, signal=signal)
        if macd is not None:
            df["macd"] = macd[f"MACD_{fast}_{slow}_{signal}"]
            df["macd_signal"] = macd[f"MACDs_{fast}_{slow}_{signal}"]
            df["macd_hist"] = macd[f"MACDh_{fast}_{slow}_{signal}"]
    elif _USE_TA:
        import ta as ta_lib
        macd_ind = ta_lib.trend.MACD(close=df[column], window_slow=slow, window_fast=fast, window_sign=signal)
        df["macd"] = macd_ind.macd()
        df["macd_signal"] = macd_ind.macd_signal()
        df["macd_hist"] = macd_ind.macd_diff()
    else:
        ema_fast = df[column].ewm(span=fast, adjust=False).mean()
        ema_slow = df[column].ewm(span=slow, adjust=False).mean()
        df["macd"] = ema_fast - ema_slow
        df["macd_signal"] = df["macd"].ewm(span=signal, adjust=False).mean()
        df["macd_hist"] = df["macd"] - df["macd_signal"]
    return df


def add_bbands(
    df: pd.DataFrame,
    period: int = 20,
    std: float = 2.0,
    column: str = "close",
) -> pd.DataFrame:
    """Add Bollinger Bands: upper, middle, lower."""
    try:
        if _USE_PTA:
            bb = pta.bbands(df[column], length=period, std=std)
            if bb is not None:
                # pandas_ta column names can be tricky, try common patterns
                upper_col = f"BBU_{period}_{std}"
                mid_col = f"BBM_{period}_{std}"
                lower_col = f"BBL_{period}_{std}"
                
                if upper_col in bb.columns:
                    df["bb_upper"] = bb[upper_col]
                    df["bb_mid"] = bb[mid_col]
                    df["bb_lower"] = bb[lower_col]
                    return df
                else:
                    # Fallback to finding by prefix if exact match fails
                    for col in bb.columns:
                        if col.startswith("BBU_"): df["bb_upper"] = bb[col]
                        if col.startswith("BBM_"): df["bb_mid"] = bb[col]
                        if col.startswith("BBL_"): df["bb_lower"] = bb[col]
                    if "bb_upper" in df.columns: return df

        # Manual/TA Fallback
        if _USE_TA:
            import ta as ta_lib
            bb_ind = ta_lib.volatility.BollingerBands(close=df[column], window=period, window_dev=std)
            df["bb_upper"] = bb_ind.bollinger_hband()
            df["bb_mid"] = bb_ind.bollinger_mavg()
            df["bb_lower"] = bb_ind.bollinger_lband()
        else:
            mid = df[column].rolling(period).mean()
            std_dev = df[column].rolling(period).std()
            df["bb_mid"] = mid
            df["bb_upper"] = mid + std * std_dev
            df["bb_lower"] = mid - std * std_dev
    except Exception as e:
        logger.warning(f"BBands calculation error: {e}. Using simple manual fallback.")
        mid = df[column].rolling(period).mean()
        std_dev = df[column].rolling(period).std()
        df["bb_mid"] = mid
        df["bb_upper"] = mid + std * std_dev
        df["bb_lower"] = mid - std * std_dev
        
    return df


def add_volume_ratio(df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
    """Add volume ratio (current volume / average volume)."""
    df["volume_sma"] = df["volume"].rolling(period).mean()
    df["volume_ratio"] = df["volume"] / df["volume_sma"]
    return df


def add_volatility(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Add volatility % column based on ATR / Close * 100."""
    if _USE_PTA:
        atr = pta.atr(df["high"], df["low"], df["close"], length=period)
        if atr is not None:
            df["volatility_atr"] = (atr / df["close"]) * 100
    elif _USE_TA:
        import ta as ta_lib
        atr_ind = ta_lib.volatility.AverageTrueRange(high=df["high"], low=df["low"], close=df["close"], window=period)
        df["volatility_atr"] = (atr_ind.average_true_range() / df["close"]) * 100
    else:
        # Simple manual ATR
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        df["volatility_atr"] = (atr / df["close"]) * 100
    
    return df


def add_atr(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """Add ATR (Average True Range) indicator column."""
    if _USE_PTA:
        atr = pta.atr(df["high"], df["low"], df["close"], length=period)
        if atr is not None:
            df[f"atr_{period}"] = atr
    elif _USE_TA:
        import ta as ta_lib
        atr_ind = ta_lib.volatility.AverageTrueRange(high=df["high"], low=df["low"], close=df["close"], window=period)
        df[f"atr_{period}"] = atr_ind.average_true_range()
    else:
        # Manual ATR calculation
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df[f"atr_{period}"] = tr.rolling(period).mean()

    return df


def add_bb_width(df: pd.DataFrame, period: int = 20, std: float = 2.0) -> pd.DataFrame:
    """Add Bollinger Band Width and Squeeze indicator."""
    if "bb_upper" not in df.columns or "bb_lower" not in df.columns:
        df = add_bbands(df, period, std)
    
    df["bb_width"] = ((df["bb_upper"] - df["bb_lower"]) / df["bb_mid"]) * 100
    df["bb_squeeze"] = df["bb_width"] < 4.0
    return df


def add_vwap(df: pd.DataFrame) -> pd.DataFrame:
    """Add VWAP (Volume Weighted Average Price) for the current session (24h)."""
    # Simplified daily VWAP
    tp = (df["high"] + df["low"] + df["close"]) / 3
    df["vwap"] = (tp * df["volume"]).cumsum() / df["volume"].cumsum()
    return df


def find_sr_levels(df: pd.DataFrame, period: int = 20) -> dict:
    """Identify nearest 3 support and 3 resistance levels using pivots."""
    if len(df) < period * 2:
        return {"support": [], "resistance": []}
    
    current_price = df.iloc[-1]["close"]
    highs = df["high"].values
    lows = df["low"].values
    
    supports = []
    resistances = []
    
    for i in range(period, len(df) - period):
        # Pivot point logic (higher/lower than surrounding candles)
        if all(highs[i] > highs[i-period:i]) and all(highs[i] > highs[i+1:i+period+1]):
            resistances.append(float(highs[i]))
        if all(lows[i] < lows[i-period:i]) and all(lows[i] < lows[i+1:i+period+1]):
            supports.append(float(lows[i]))
            
    # Filter and sort
    s_levels = sorted([s for s in set(supports) if s < current_price], reverse=True)[:3]
    r_levels = sorted([r for r in set(resistances) if r > current_price])[:3]
    
    return {"support": s_levels, "resistance": r_levels}


def detect_patterns(df: pd.DataFrame) -> dict:
    """Detect candle patterns on the last 3 candles."""
    if len(df) < 5:
        return {}
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    prev2 = df.iloc[-3]
    
    patterns = []
    
    # helper
    def is_bullish(c): return c["close"] > c["open"]
    def body_size(c): return abs(c["close"] - c["open"])
    def full_size(c): return c["high"] - c["low"]
    
    # 1. Bullish Engulfing
    if not is_bullish(prev) and is_bullish(last) and last["close"] > prev["open"] and last["open"] < prev["close"]:
        patterns.append({"name": "Bullish Engulfing", "type": "LONG", "strength": "STRONG"})
        
    # 2. Bearish Engulfing
    if is_bullish(prev) and not is_bullish(last) and last["close"] < prev["open"] and last["open"] > prev["close"]:
        patterns.append({"name": "Bearish Engulfing", "type": "SHORT", "strength": "STRONG"})
        
    # 3. Hammer
    wick_lower = min(last["open"], last["close"]) - last["low"]
    if wick_lower > 2 * body_size(last) and (last["high"] - max(last["open"], last["close"])) < 0.1 * wick_lower:
        patterns.append({"name": "Hammer", "type": "LONG", "strength": "MODERATE"})
        
    # 4. Shooting Star
    wick_upper = last["high"] - max(last["open"], last["close"])
    if wick_upper > 2 * body_size(last) and (min(last["open"], last["close"]) - last["low"]) < 0.1 * wick_upper:
        patterns.append({"name": "Shooting Star", "type": "SHORT", "strength": "MODERATE"})

    return patterns[0] if patterns else None


def add_all_indicators(df: pd.DataFrame, strategy_params: dict = None) -> pd.DataFrame:
    """Add all standard indicators to a dataframe."""
    try:
        df = add_ema(df, 21)
        df = add_ema(df, 50)
        df = add_ema(df, 200)
        df = add_rsi(df, 14)
        df = add_macd(df)
        df = add_bbands(df)
        df = add_bb_width(df)
        df = add_volume_ratio(df)
        df = add_volatility(df)
        df = add_atr(df, 14)
        df = add_vwap(df)
    except Exception as e:
        logger.error(f"Error adding indicators: {e}")
    return df
