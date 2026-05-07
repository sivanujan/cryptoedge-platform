"""
scanner_models.py — SQLAlchemy models for the Breakout Scanner.
Uses the same Base as the rest of the project so init_db() creates all tables.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DECIMAL, Enum as SAEnum, TIMESTAMP
from database.connection import Base


class BreakoutSignal(Base):
    __tablename__ = "breakout_signals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(20), nullable=False, index=True)
    direction = Column(SAEnum("LONG", "SHORT", name="breakout_direction_enum"), nullable=False)
    entry_price = Column(DECIMAL(20, 8), nullable=False)
    stop_loss = Column(DECIMAL(20, 8), nullable=False)
    take_profit_1 = Column(DECIMAL(20, 8), nullable=False)
    take_profit_2 = Column(DECIMAL(20, 8), nullable=False)
    atr = Column(DECIMAL(20, 8), nullable=True)
    rsi = Column(DECIMAL(10, 4), nullable=True)
    volume_ratio = Column(DECIMAL(10, 4), nullable=True)
    rs_vs_btc = Column(DECIMAL(10, 4), nullable=True)
    vwap = Column(DECIMAL(20, 8), nullable=True)
    signal_score = Column(Integer, nullable=False, default=0)
    status = Column(
        SAEnum("ACTIVE", "TP1_HIT", "TP2_HIT", "SL_HIT", "EXPIRED", name="breakout_status_enum"),
        nullable=False,
        default="ACTIVE",
        index=True,
    )
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)


class ScannerRun(Base):
    __tablename__ = "scanner_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    total_scanned = Column(Integer, nullable=False, default=0)
    signals_generated = Column(Integer, nullable=False, default=0)
    run_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=False)
