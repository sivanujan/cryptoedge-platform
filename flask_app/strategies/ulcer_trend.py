import numpy as np
import pandas as pd
from strategies.base_strategy import BaseStrategy


def _ulcer_index(close: pd.Series, length: int = 14) -> pd.Series:
    """
    Ulcer Index = sqrt(mean of squared drawdowns over the rolling window).
    Drawdown at each bar = % decline from the highest close in the window.
    """
    def _ui(window):
        peak = window.max()
        draws = ((window - peak) / peak * 100) ** 2
        return np.sqrt(draws.mean())

    return close.rolling(length).apply(_ui, raw=False)


class UlcerTrendStrategy(BaseStrategy):
    """
    Ulcer Trend Strategy

    The Ulcer Index (UI) measures downside volatility / drawdown stress.
    A rising UI = more pain. A falling UI = stress easing.

    Long Entry (ALL must be true):
        - UI crosses BELOW its MA  (stress is easing)
        - Price is ABOVE the Trend EMA  (uptrend confirmed)

    Short Entry (ALL must be true):
        - UI crosses ABOVE its MA  (stress is rising)
        - Price is BELOW the Trend EMA  (downtrend confirmed)
        - allow_shorts is enabled

    Exit Logic:
        - Long:  close when UI crosses ABOVE its MA  (reversal close)
        - Short: close when UI crosses BELOW its MA  (reversal close)
        - Fixed stop-loss and take-profit applied in the simulator
    """

    name = "Ulcer Trend Strategy"
    description = (
        "Uses the Ulcer Index (downside volatility) combined with a Trend EMA. "
        "Enters long when stress is easing and price is in an uptrend. "
        "Enters short when stress is rising and price is in a downtrend. "
        "Exits on stress reversal, stop-loss (-2%), or take-profit (+4%)."
    )
    default_params = {
        "ui_length": 14,          # Ulcer Index lookback
        "ui_ma_length": 5,        # Smoothing MA on the UI
        "trend_ema_length": 50,   # Trend EMA period
        "allow_shorts": True,     # Enable short side
        "stop_loss_pct": 2.0,     # Stop-loss % from entry
        "take_profit_pct": 4.0,   # Take-profit % from entry
        "maxDrawdownPct": 2.0,    # Used by base calculate_stop_loss
    }

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        p = self.params
        ui_len = int(p.get("ui_length", 14))
        ui_ma_len = int(p.get("ui_ma_length", 5))
        trend_len = int(p.get("trend_ema_length", 50))
        allow_shorts = bool(p.get("allow_shorts", True))

        close = df["close"]

        # 1. Ulcer Index
        ui = _ulcer_index(close, ui_len)

        # 2. UI smoothing MA (simple)
        ui_ma = ui.rolling(ui_ma_len).mean()

        # 3. Trend EMA
        trend_ema = close.ewm(span=trend_len, adjust=False).mean()

        # 4. Crossover conditions
        # UI crosses below MA: stress easing
        ui_cross_below = (ui < ui_ma) & (ui.shift(1) >= ui_ma.shift(1))
        # UI crosses above MA: stress rising
        ui_cross_above = (ui > ui_ma) & (ui.shift(1) <= ui_ma.shift(1))

        above_trend = close > trend_ema
        below_trend = close < trend_ema

        # 5. Entry signals
        long_entry  = ui_cross_below & above_trend
        short_entry = ui_cross_above & below_trend & allow_shorts

        # 6. Exit signals (reversal close)
        long_exit  = ui_cross_above          # stress is rising → exit long
        short_exit = ui_cross_below          # stress is easing → exit short

        # 7. Build signal column
        df = df.copy()
        df["signal"] = 0
        df.loc[long_entry,  "signal"] = 1
        df.loc[long_exit,   "signal"] = -1
        # Short entries override if allow_shorts (signal -1 for sell/short)
        if allow_shorts:
            df.loc[short_entry, "signal"] = -1
        # Exits from short = buy-to-cover (signal +1)
        # The simulator treats 1=buy, -1=sell so this aligns.

        # 8. Confidence: based on UI distance from its MA (normalised)
        try:
            ui_diff = (ui_ma - ui).abs()
            norm = ui_diff / (ui_diff.rolling(50).max() + 1e-9)
            df["confidence"] = (50 + norm * 45).clip(50, 95).fillna(60)
        except Exception:
            df["confidence"] = 65.0

        # Store indicators for potential visualisation
        df["ui"] = ui
        df["ui_ma"] = ui_ma
        df["trend_ema"] = trend_ema

        return df

    def calculate_stop_loss(self, entry_price: float) -> float:
        sl_pct = self.params.get("stop_loss_pct", 2.0)
        return round(entry_price * (1 - sl_pct / 100), 8)

    def calculate_take_profit(self, entry_price: float, ratio: float = 2.0) -> float:
        tp_pct = self.params.get("take_profit_pct", 4.0)
        return round(entry_price * (1 + tp_pct / 100), 8)
