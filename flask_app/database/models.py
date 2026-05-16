from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime,
    ForeignKey, JSON, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from database.connection import Base


class Coin(Base):
    __tablename__ = "coins"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), unique=True, nullable=False, index=True)
    base_asset = Column(String(20), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    backtest_results = relationship("BacktestResult", back_populates="coin")
    coin_strategy_maps = relationship("CoinStrategyMap", back_populates="coin")
    signals = relationship("Signal", back_populates="coin")
    trades = relationship("Trade", back_populates="coin")


class Strategy(Base):
    __tablename__ = "strategies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    parameters = Column(JSON, nullable=True)
    pine_script = Column(Text, nullable=True)
    python_code = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # New fields for Strategy Signal Engine
    coins_tested = Column(Integer, nullable=True)
    timeframes = Column(JSON, nullable=True)
    best_win_rate = Column(Float, nullable=True)
    best_tf = Column(String(10), nullable=True)
    coins_above_65 = Column(Integer, nullable=True)
    tags = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

    backtest_results = relationship("BacktestResult", back_populates="strategy")
    coin_strategy_maps = relationship("CoinStrategyMap", back_populates="strategy")
    signals = relationship("Signal", back_populates="strategy")
    coin_results = relationship("CoinResult", back_populates="strategy")


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id = Column(Integer, primary_key=True, index=True)
    coin_id = Column(Integer, ForeignKey("coins.id"), nullable=False, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, index=True)
    win_rate = Column(Float, nullable=True, index=True)
    total_trades = Column(Integer, nullable=True)
    total_return = Column(Float, nullable=True)
    max_drawdown = Column(Float, nullable=True)
    sharpe_ratio = Column(Float, nullable=True)
    profit_factor = Column(Float, nullable=True)
    volatility = Column(Float, nullable=True)
    tested_from = Column(DateTime, nullable=True)
    tested_to = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    coin = relationship("Coin", back_populates="backtest_results")
    strategy = relationship("Strategy", back_populates="backtest_results")


class CoinStrategyMap(Base):
    __tablename__ = "coin_strategy_map"

    id = Column(Integer, primary_key=True, index=True)
    coin_id = Column(Integer, ForeignKey("coins.id"), nullable=False, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, default="1h", index=True)
    win_rate = Column(Float, nullable=True, index=True)
    is_active = Column(Boolean, default=True)
    assigned_at = Column(DateTime, default=datetime.utcnow)

    coin = relationship("Coin", back_populates="coin_strategy_maps")
    strategy = relationship("Strategy", back_populates="coin_strategy_maps")


class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True, index=True)
    coin_id = Column(Integer, ForeignKey("coins.id"), nullable=False)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False)
    signal_type = Column(SAEnum("BUY", "SELL", name="signal_type_enum"), nullable=False)
    entry_price = Column(Float, nullable=False)
    stop_loss = Column(Float, nullable=True)
    take_profit = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    volatility = Column(Float, nullable=True)
    timeframe = Column(String(10), nullable=False, default="1h")
    status = Column(String(20), default="active")  # active, closed, cancelled
    ai_analysis = Column(Text, nullable=True) # AI analysis details
    ai_score = Column(Float, nullable=True) # AI sentiment score (0-100)
    
    # Structure-based Stop Loss & Take Profit
    structure_sl = Column(Float, nullable=True)
    structure_tp = Column(Float, nullable=True)
    sl_pct = Column(Float, nullable=True)
    tp_pct = Column(Float, nullable=True)
    rr_ratio = Column(Float, nullable=True)
    sl_method = Column(String(20), nullable=True) # "swing" or "fallback_pct"

    created_at = Column(DateTime, default=datetime.utcnow)

    coin = relationship("Coin", back_populates="signals")
    strategy = relationship("Strategy", back_populates="signals")
    trades = relationship("Trade", back_populates="signal")


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    signal_id = Column(Integer, ForeignKey("signals.id"), nullable=True)
    coin_id = Column(Integer, ForeignKey("coins.id"), nullable=False)
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    pnl = Column(Float, nullable=True)
    pnl_percent = Column(Float, nullable=True)
    status = Column(String(20), default="open")  # open, closed, stopped
    opened_at = Column(DateTime, default=datetime.utcnow)
    closed_at = Column(DateTime, nullable=True)

    coin = relationship("Coin", back_populates="trades")
    signal = relationship("Signal", back_populates="trades")


class Setting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BacktestJob(Base):
    """Persists backtest job state to DB so it survives restarts and works with multiple workers."""
    __tablename__ = "backtest_jobs"

    id = Column(String(100), primary_key=True)   # job_id string
    status = Column(String(20), default="running")  # running | complete | error
    strategy_id = Column(Integer, nullable=True)
    total_coins = Column(Integer, default=0)
    total_timeframes = Column(Integer, default=0)
    total_tests = Column(Integer, default=0)
    completed = Column(Integer, default=0)
    best_coin = Column(String(100), nullable=True)
    best_win_rate = Column(Float, default=0.0)
    coins_above_65 = Column(Integer, default=0)
    current_coin = Column(String(50), default="")
    eta_seconds = Column(Integer, default=0)
    progress_percent = Column(Float, default=0.0)
    error_message = Column(Text, nullable=True)
    current_tf = Column(String(10), default="")
    message = Column(String(200), default="Starting backtest...")
    error_detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AutoTrade(Base):
    __tablename__ = "auto_trades"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(50), nullable=False)
    side = Column(String(10), nullable=False) # LONG or SHORT
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    quantity = Column(Float, nullable=False)
    leverage = Column(Integer, nullable=False)
    margin_used = Column(Float, nullable=False)
    pnl = Column(Float, nullable=True)
    strategy_name = Column(String(100), nullable=False)
    sl_price = Column(Float, nullable=False)
    tp1 = Column(Float, nullable=False)
    tp2 = Column(Float, nullable=False)
    tp3 = Column(Float, nullable=False)
    sl_moved_to_be = Column(Boolean, default=False)
    sl_moved_to_tp1 = Column(Boolean, default=False)
    status = Column(String(50), default="OPEN")
    open_time = Column(DateTime, default=datetime.utcnow)
    close_time = Column(DateTime, nullable=True)
    close_reason = Column(String(100), nullable=True)

class AutoTradeSetting(Base):
    __tablename__ = "auto_trade_settings"

    id = Column(Integer, primary_key=True, index=True)
    leverage = Column(Integer, default=10)
    per_trade_percent = Column(Float, default=30.0)
    max_open_trades = Column(Integer, default=3)
    daily_loss_limit = Column(Float, default=20.0)
    enabled_strategies = Column(String(500), default="[]") 
    is_enabled = Column(Boolean, default=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class DailyPnlSummary(Base):
    __tablename__ = "daily_pnl_summary"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(String(20), nullable=False, unique=True)
    starting_balance = Column(Float, nullable=False)
    ending_balance = Column(Float, nullable=True)
    total_trades = Column(Integer, default=0)
    wins = Column(Integer, default=0)
    losses = Column(Integer, default=0)
    gross_pnl = Column(Float, default=0.0)
    trading_halted = Column(Boolean, default=False)

class JournalTrade(Base):
    __tablename__ = "journal_trades"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    side = Column(String(10), nullable=False) # LONG / SHORT
    entry_price = Column(Float, nullable=False)
    exit_price = Column(Float, nullable=True)
    qty = Column(Float, nullable=False)
    invested = Column(Float, nullable=False) # entry_price * qty
    returned = Column(Float, nullable=True)  # exit_price * qty
    pnl = Column(Float, nullable=True)
    pnl_percent = Column(Float, nullable=True)
    entry_time = Column(DateTime, nullable=False, index=True)
    exit_time = Column(DateTime, nullable=True)
    hold_time_mins = Column(Float, nullable=True)
    status = Column(String(20), default="OPEN") # OPEN, CLOSED
    created_at = Column(DateTime, default=datetime.utcnow)


class CoinResult(Base):
    __tablename__ = "coin_results"

    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False, index=True)
    coin = Column(String(20), nullable=False, index=True)
    tf_results = Column(JSON, nullable=True)
    best_tf = Column(String(10), nullable=True)
    best_win_rate = Column(Float, nullable=True)
    trades_at_best = Column(Integer, nullable=True)
    return_pct = Column(Float, nullable=True)
    drawdown = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    strategy = relationship("Strategy", back_populates="coin_results")


class SignalHistory(Base):
    __tablename__ = "signal_history"

    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False, index=True)
    coin = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False)
    verdict = Column(String(10), nullable=False) # TAKE, SKIP, WAIT
    validity_score = Column(Integer, nullable=True)
    full_signal = Column(JSON, nullable=False) # Stores the full response JSON
    outcome = Column(String(20), default="Pending") # Win, Loss, Pending
    created_at = Column(DateTime, default=datetime.utcnow)

    strategy = relationship("Strategy")


class StrategyRanking(Base):
    __tablename__ = "strategy_rankings"

    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=False, index=True)
    coin = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False)
    win_rate = Column(Float, nullable=False)
    trades = Column(Integer, nullable=False)
    confidence = Column(Float, nullable=False)
    final_score = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    strategy = relationship("Strategy")
