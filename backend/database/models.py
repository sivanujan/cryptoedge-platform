from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime,
    ForeignKey, JSON, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


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
    created_at = Column(DateTime, default=datetime.utcnow)

    backtest_results = relationship("BacktestResult", back_populates="strategy")
    coin_strategy_maps = relationship("CoinStrategyMap", back_populates="strategy")
    signals = relationship("Signal", back_populates="strategy")


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
    timeframe = Column(String(10), nullable=False, default="1h")
    status = Column(String(20), default="active")  # active, closed, cancelled
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
    current_tf = Column(String(10), default="")
    message = Column(String(200), default="Starting backtest...")
    error_detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
