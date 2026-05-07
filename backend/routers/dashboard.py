import logging
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from database.connection import get_db
from database.models import Coin, Signal, BacktestResult, CoinStrategyMap
from services.binance_service import get_current_price

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/stats")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Return aggregated stats for dashboard top cards."""
    try:
        total_coins = db.query(Coin).filter_by(is_active=True).count()

        active_signals = db.query(Signal).filter_by(status="active").count()

        # Today's signal breakdown
        from datetime import datetime, date
        today_start = datetime.combine(date.today(), datetime.min.time())
        today_signals = db.query(Signal).filter(Signal.created_at >= today_start).all()
        today_total = len(today_signals)
        today_wins = sum(1 for s in today_signals if s.status == "won")
        today_losses = sum(1 for s in today_signals if s.status == "lost")
        today_closed = today_wins + today_losses
        today_win_rate = round(today_wins / today_closed * 100, 1) if today_closed else 0
        today_loss_rate = round(today_losses / today_closed * 100, 1) if today_closed else 0

        # Total return from closed trades (approximate from backtest data)
        best_results = (
            db.query(BacktestResult)
            .filter(BacktestResult.win_rate.isnot(None))
            .order_by(BacktestResult.win_rate.desc())
            .limit(5)
            .all()
        )

        top_coins = []
        for r in best_results:
            coin_name = r.coin.symbol if r.coin else "?"
            top_coins.append({
                "symbol": coin_name,
                "strategy": r.strategy.name if r.strategy else "?",
                "win_rate": r.win_rate,
                "total_return": r.total_return,
            })

        # Overall average return
        avg_return = db.query(func.avg(BacktestResult.total_return)).scalar() or 0

        return {
            "total_coins_scanning": total_coins,
            "active_signals": active_signals,
            "today_total_signals": today_total,
            "today_wins": today_wins,
            "today_losses": today_losses,
            "today_win_rate": today_win_rate,
            "today_loss_rate": today_loss_rate,
            "total_return": round(float(avg_return), 2),
            "top_performing_coins": top_coins,
            "bot_status": "running",
        }
    except Exception as e:
        logger.error(f"Dashboard stats error: {e}")
        return {
            "total_coins_scanning": 0,
            "active_signals": 0,
            "today_total_signals": 0,
            "today_wins": 0,
            "today_losses": 0,
            "today_win_rate": 0,
            "today_loss_rate": 0,
            "total_return": 0,
            "top_performing_coins": [],
            "bot_status": "stopped",
        }
