import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from database.models import Signal, Coin, Strategy

logger = logging.getLogger(__name__)


def get_live_signals(db: Session) -> List[dict]:
    """Return all currently active signals with coin and strategy info."""
    signals = (
        db.query(Signal)
        .filter(Signal.status == "active")
        .order_by(Signal.created_at.desc())
        .limit(100)
        .all()
    )
    return [_signal_to_dict(s) for s in signals]


def get_signal_history(
    db: Session,
    coin_symbol: Optional[str] = None,
    strategy_name: Optional[str] = None,
    signal_type: Optional[str] = None,
    result: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> dict:
    """Return paginated signal history with optional filters."""
    query = db.query(Signal).join(Coin).join(Strategy)

    if coin_symbol:
        query = query.filter(Coin.symbol.ilike(f"%{coin_symbol}%"))
    if strategy_name:
        query = query.filter(Strategy.name.ilike(f"%{strategy_name}%"))
    if signal_type:
        query = query.filter(Signal.signal_type == signal_type.upper())
    if result == "win":
        query = query.filter(Signal.status == "closed")
    elif result == "loss":
        query = query.filter(Signal.status == "stopped")

    total = query.count()
    signals = query.order_by(Signal.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "signals": [_signal_to_dict(s) for s in signals],
    }


def get_signal_stats(db: Session) -> dict:
    """Aggregate signal statistics for history page."""
    total = db.query(Signal).count()
    wins = db.query(Signal).filter(Signal.status == "closed").count()
    losses = db.query(Signal).filter(Signal.status == "stopped").count()

    win_rate = round(wins / total * 100, 1) if total > 0 else 0
    return {
        "total_signals": total,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
    }


def _signal_to_dict(s: Signal) -> dict:
    return {
        "id": s.id,
        "symbol": s.coin.symbol if s.coin else "",
        "strategy": s.strategy.name if s.strategy else "",
        "signal_type": s.signal_type,
        "entry_price": s.entry_price,
        "stop_loss": s.stop_loss,
        "take_profit": s.take_profit,
        "confidence": s.confidence,
        "timeframe": s.timeframe,
        "status": s.status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }
