import numpy as np
import pandas as pd
from strategies.base_strategy import BaseStrategy
from services.indicator_service import add_ema


class GoldenCrossStrategy(BaseStrategy):
    """
    Golden Cross EMA strategy.

    Entry conditions:
    - Fast EMA (21) crosses above Slow EMA (50)
    - Price is above Trend EMA (200)  [optional via useTrendFilter]
    - Second chance: fast EMA crosses above trend EMA while above slow EMA

    Exit conditions:
    - Fast EMA (21) crosses below Slow EMA (50)
    - OR stop loss hit (configured via maxDrawdownPct)
    """

    name = "Golden Cross"
    description = (
        "Uses EMA21/50/200 crossover with trend filter. "
        "Enters when fast EMA crosses above slow EMA with trend confirmation."
    )
    default_params = {
        "fastLen": 21,
        "slowLen": 50,
        "trendLen": 200,
        "useTrendFilter": True,
        "maxDrawdownPct": 5.0,
    }

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        fast = p["fastLen"]
        slow = p["slowLen"]
        trend = p["trendLen"]

        # Add EMAs if not already present
        if f"ema_{fast}" not in df.columns:
            df = add_ema(df, fast)
        if f"ema_{slow}" not in df.columns:
            df = add_ema(df, slow)
        if f"ema_{trend}" not in df.columns:
            df = add_ema(df, trend)

        ema_fast = df[f"ema_{fast}"]
        ema_slow = df[f"ema_{slow}"]
        ema_trend = df[f"ema_{trend}"]
        close = df["close"]

        # Crossover detection: fast crosses above slow
        cross_above = (ema_fast > ema_slow) & (ema_fast.shift(1) <= ema_slow.shift(1))
        # Crossunder detection: fast crosses below slow
        cross_below = (ema_fast < ema_slow) & (ema_fast.shift(1) >= ema_slow.shift(1))

        # Trend filter
        above_trend = close > ema_trend if p["useTrendFilter"] else pd.Series(True, index=df.index)

        # Second chance cross: fast crosses above trend while above slow
        second_chance = (
            (ema_fast > ema_trend)
            & (ema_fast.shift(1) <= ema_trend.shift(1))
            & (ema_fast > ema_slow)
        )

        entry = (cross_above & above_trend) | (second_chance & above_trend)
        exit_ = cross_below

        # Build signal column
        df["signal"] = 0
        df.loc[entry, "signal"] = 1
        df.loc[exit_, "signal"] = -1

        # Confidence score based on EMA separation
        try:
            ema_diff_pct = ((ema_fast - ema_slow) / ema_slow * 100).abs()
            # Normalize to 50-95 range
            norm_conf = 50 + (ema_diff_pct / ema_diff_pct.max() * 45)
            df["confidence"] = norm_conf.clip(50, 95).fillna(50)
        except Exception:
            df["confidence"] = 70.0

        return df

    def get_entry_conditions(self, df: pd.DataFrame) -> pd.Series:
        signals = self.generate_signals(df)
        return signals["signal"] == 1

    def get_exit_conditions(self, df: pd.DataFrame) -> pd.Series:
        signals = self.generate_signals(df)
        return signals["signal"] == -1


# Registry: maps strategy name -> class
from strategies.ulcer_trend import UlcerTrendStrategy

STRATEGY_REGISTRY = {
    "Golden Cross": GoldenCrossStrategy,
    "Ulcer Trend Strategy": UlcerTrendStrategy,
}


class DynamicStrategy(BaseStrategy):
    """
    Adapter that executes Python code stored in the database.
    The code must define a variable `_STRATEGY_CLASS` pointing to a local class.
    """

    def __init__(self, strategy_obj, params: dict = None):
        super().__init__(params)
        self.strategy_obj = strategy_obj
        self._internal_strategy = None
        self._load_strategy()

    def _load_strategy(self):
        try:
            # Prepare execution context
            import pandas as pd
            import numpy as np
            from services.indicator_service import (
                add_ema, add_rsi, add_macd, add_bbands, 
                add_volatility, add_atr, add_vwap, add_all_indicators
            )
            
            ctx = {
                'pd': pd,
                'np': np,
                'BaseStrategy': BaseStrategy,
                'add_ema': add_ema,
                'add_rsi': add_rsi,
                'add_macd': add_macd,
                'add_bbands': add_bbands,
                'add_volatility': add_volatility,
                'add_atr': add_atr,
                'add_vwap': add_vwap,
                'add_all_indicators': add_all_indicators,
            }
            
            # Execute the code from the database
            exec(self.strategy_obj.python_code, ctx)
            
            # Extract the strategy class
            strat_cls = ctx.get('_STRATEGY_CLASS')
            if not strat_cls:
                # Fallback: look for any class inheriting from BaseStrategy
                for val in ctx.values():
                    if isinstance(val, type) and issubclass(val, BaseStrategy) and val != BaseStrategy:
                        strat_cls = val
                        break
            
            if not strat_cls:
                raise ValueError(f"No strategy class found in code for '{self.strategy_obj.name}'")
            
            # Instantiate the inner strategy
            self._internal_strategy = strat_cls(self.params)
            self.name = self.strategy_obj.name
            
        except Exception as e:
            # Fallback to GoldenCross if everything fails, but log error
            from services.indicator_service import logger
            logger.error(f"Failed to load dynamic strategy '{self.strategy_obj.name}': {e}")
            self._internal_strategy = GoldenCrossStrategy(self.params)

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        if self._internal_strategy:
            return self._internal_strategy.generate_signals(df)
        return df


def get_strategy(strategy_input, params: dict = None) -> BaseStrategy:
    """
    Instantiate a strategy. 
    Accepts strategy name (string) OR Strategy database model instance.
    """
    if isinstance(strategy_input, str):
        name = strategy_input
        cls = STRATEGY_REGISTRY.get(name)
        if cls:
            return cls(params)
        
        # If not in registry but it's a string, we can't do much without the DB object
        # unless we were to fetch it here. For safety, we raise error.
        raise ValueError(f"Strategy '{name}' not found in registry and no DB object provided.")
    
    # Otherwise assume it's a Strategy database object
    strategy_obj = strategy_input
    cls = STRATEGY_REGISTRY.get(strategy_obj.name)
    
    if cls:
        return cls(params)
    
    # Use DynamicStrategy for database-stored code
    return DynamicStrategy(strategy_obj, params)
