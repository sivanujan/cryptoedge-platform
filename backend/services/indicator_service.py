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
    if _USE_PTA:
        bb = pta.bbands(df[column], length=period, std=std)
        if bb is not None:
            df["bb_upper"] = bb[f"BBU_{period}_{std}"]
            df["bb_mid"] = bb[f"BBM_{period}_{std}"]
            df["bb_lower"] = bb[f"BBL_{period}_{std}"]
    elif _USE_TA:
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


def add_all_indicators(df: pd.DataFrame, strategy_params: dict = None) -> pd.DataFrame:
    """Add all standard indicators to a dataframe."""
    try:
        df = add_ema(df, 21)
        df = add_ema(df, 50)
        df = add_ema(df, 200)
        df = add_rsi(df, 14)
        df = add_macd(df)
        df = add_bbands(df)
        df = add_volume_ratio(df)
        df = add_volatility(df)
    except Exception as e:
        logger.error(f"Error adding indicators: {e}")
    return df
