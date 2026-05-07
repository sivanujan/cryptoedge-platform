import logging
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session, joinedload
from database.models import Signal, Coin, Strategy, Trade

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
    query = (
        db.query(Signal)
        .options(joinedload(Signal.coin), joinedload(Signal.strategy), joinedload(Signal.trades))
        .join(Coin)
        .join(Strategy)
    )

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

    # Fetch live prices for active signals to calculate current PnL
    active_symbols = list(set([s.coin.symbol for s in signals if s.status == "active"]))
    live_prices = {}
    if active_symbols:
        from services.binance_service import get_multiple_prices
        live_prices = get_multiple_prices(active_symbols)

    return {
        "total": total,
        "signals": [_signal_to_dict(s, live_prices) for s in signals],
    }


def get_signal_stats(db: Session) -> dict:
    """Aggregate signal statistics for history page, including live PnL."""
    from sqlalchemy import func
    
    signals = db.query(Signal).options(
        joinedload(Signal.coin), 
        joinedload(Signal.trades),
        joinedload(Signal.strategy) # Eager load strategy
    ).all()
    total = len(signals)
    if total == 0:
        return {
            "total_signals": 0, 
            "wins": 0, 
            "losses": 0, 
            "win_rate": 0, 
            "total_pnl": 0
        }

    # Fetch live prices for active signals to calculate current PnL
    active_symbols = list(set([s.coin.symbol for s in signals if s.status == "active"]))
    live_prices = {}
    if active_symbols:
        from services.binance_service import get_multiple_prices
        try:
            live_prices = get_multiple_prices(active_symbols)
        except Exception as e:
            logger.error(f"Error fetching live prices for stats: {e}")

    wins = 0
    losses = 0
    total_pnl = 0.0

    strategy_map = {}

    # Seed with all active strategies to ensure they show up even with 0 signals
    from database.models import Strategy
    active_strategies = db.query(Strategy).filter_by(is_active=True).all()
    for s in active_strategies:
        strategy_map[s.name] = {
            "name": s.name,
            "total_signals": 0,
            "wins": 0,
            "losses": 0,
            "total_pnl": 0.0
        }

    for s in signals:
        strat_name = s.strategy.name if s.strategy else "Unknown"
        if strat_name not in strategy_map:
            strategy_map[strat_name] = {
                "name": strat_name,
                "total_signals": 0,
                "wins": 0,
                "losses": 0,
                "total_pnl": 0.0
            }
        
        sm = strategy_map[strat_name]
        sm["total_signals"] += 1

        pnl = None
        # Use trade PnL if available (for closed/stopped)
        if s.trades:
            # Get the first trade's PnL percent
            pnl = s.trades[0].pnl_percent
        
        # If no trade PnL (or active), calculate it using current price
        if (pnl is None or s.status == "active") and s.coin.symbol in live_prices:
            curr = live_prices[s.coin.symbol]
            entry = s.entry_price
            if entry and entry > 0:
                if s.signal_type == "BUY":
                    pnl = (curr - entry) / entry * 100
                else: # SELL
                    pnl = (entry - curr) / entry * 100
        
        if pnl is not None:
            total_pnl += pnl
            sm["total_pnl"] += pnl
            if pnl > 0:
                wins += 1
                sm["wins"] += 1
            elif pnl < 0:
                losses += 1
                sm["losses"] += 1
        elif s.status == "closed":
            wins += 1
            sm["wins"] += 1
        elif s.status == "stopped":
            losses += 1
            sm["losses"] += 1

    # Calculate win rates for each strategy
    strategy_stats = []
    for name, sm in strategy_map.items():
        w = sm["wins"]
        l = sm["losses"]
        sm["win_rate"] = round(w / (w + l) * 100, 1) if (w + l) > 0 else 0
        sm["total_pnl"] = round(sm["total_pnl"], 2)
        strategy_stats.append(sm)

    # Sort by total signals descending, then by name
    strategy_stats.sort(key=lambda x: (x["total_signals"], x["name"]), reverse=True)

    win_rate = round(wins / (wins + losses) * 100, 1) if (wins + losses) > 0 else 0
    
    return {
        "total_signals": total,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "total_pnl": round(total_pnl, 2),
        "strategy_stats": strategy_stats
    }


def _signal_to_dict(s: Signal, live_prices: dict = None) -> dict:
    # Get PnL from the associated trade if it exists
    pnl = None
    current_price = None

    if s.trades:
        # Assuming the first/last trade linked to this signal is the primary one
        pnl = s.trades[0].pnl_percent
    
    # If active, calculate live PnL if we have a current price
    if s.status == "active" and live_prices and s.coin.symbol in live_prices:
        current_price = live_prices[s.coin.symbol]
        entry = s.entry_price
        if entry and entry > 0:
            if s.signal_type == "BUY":
                pnl = (current_price - entry) / entry * 100
            else: # SELL
                pnl = (entry - current_price) / entry * 100

    return {
        "id": s.id,
        "symbol": s.coin.symbol if s.coin else "",
        "strategy": s.strategy.name if s.strategy else "",
        "signal_type": s.signal_type,
        "entry_price": s.entry_price,
        "current_price": current_price,
        "stop_loss": s.stop_loss,
        "take_profit": s.take_profit,
        "confidence": s.confidence,
        "volatility": s.volatility,
        "timeframe": s.timeframe,
        "status": s.status,
        "pnl_percent": round(pnl, 2) if pnl is not None else None,
        "created_at": (s.created_at.isoformat() + "Z") if s.created_at else None,
    }


def clear_all_signals(db: Session) -> bool:
    """Delete all signal history records."""
    try:
        db.query(Signal).delete()
        db.commit()
        return True
    except Exception as e:
        logger.error(f"Error clearing signals: {e}")
        db.rollback()
        return False
