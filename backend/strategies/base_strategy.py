from abc import ABC, abstractmethod
import pandas as pd


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.
    Each strategy must implement generate_signals().
    """

    name: str = "base"
    description: str = ""
    default_params: dict = {}

    def __init__(self, params: dict = None):
        self.params = {**self.default_params, **(params or {})}

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Given OHLCV + indicators DataFrame, return the same DataFrame
        with added 'signal' column: 1 = BUY, -1 = SELL, 0 = HOLD.
        Also add 'confidence' column (0-100 float).
        """
        pass

    def get_entry_conditions(self, df: pd.DataFrame) -> pd.Series:
        """Return boolean series of entry (BUY) conditions."""
        raise NotImplementedError

    def get_exit_conditions(self, df: pd.DataFrame) -> pd.Series:
        """Return boolean series of exit (SELL) conditions."""
        raise NotImplementedError

    def calculate_stop_loss(self, entry_price: float, signal_type: str = "BUY") -> float:
        sl_pct = self.params.get("maxDrawdownPct", 2.0)
        if signal_type == "BUY":
            return round(entry_price * (1 - sl_pct / 100), 8)
        else: # SELL
            return round(entry_price * (1 + sl_pct / 100), 8)

    def calculate_take_profit(self, entry_price: float, signal_type: str = "BUY", ratio: float = 2.0) -> float:
        sl_pct = self.params.get("maxDrawdownPct", 2.0)
        if signal_type == "BUY":
            return round(entry_price * (1 + (sl_pct * ratio) / 100), 8)
        else: # SELL
            return round(entry_price * (1 - (sl_pct * ratio) / 100), 8)
