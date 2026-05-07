import logging
from flask import Blueprint, jsonify
from sqlalchemy import func
from database.connection import SessionLocal
from database.models import Coin, Signal, BacktestResult, Strategy

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/v1/dashboard')

@dashboard_bp.route("/stats", methods=["GET"])
def dashboard_stats():
    """Return full summary stats for the dashboard."""
    logger.info("Fetching dashboard stats...")
    db = SessionLocal()
    try:
        from datetime import date as dt_date
        today = dt_date.today()
        
        total_coins = db.query(Coin).filter_by(is_active=True).count()
        active_signals = db.query(Signal).filter_by(status="active").count()
        
        # Today's signals count
        today_total_signals = db.query(Signal).filter(func.date(Signal.created_at) == today).count()
        
        # Today's wins/losses from Trades
        from database.models import Trade
        today_trades = db.query(Trade).filter(func.date(Trade.closed_at) == today).all()
        today_wins = len([t for t in today_trades if (t.pnl or 0) > 0])
        today_losses = len([t for t in today_trades if (t.pnl or 0) <= 0])
        
        total_today = today_wins + today_losses
        today_win_rate = (today_wins / total_today * 100) if total_today > 0 else 0.0
        today_loss_rate = (today_losses / total_today * 100) if total_today > 0 else 0.0

        # Fallback to backtest averages if no trades today (to keep the dashboard looking "live")
        # But we should probably prioritize actual today stats if they exist.
        # For now, let's keep the global avg_wr as today_win_rate if no trades happened today, 
        # or just show 0 if that's more accurate. 
        # The user seems to want to see "Today" stats.
        
        avg_wr = db.query(func.avg(BacktestResult.win_rate)).scalar() or 0.0
        total_ret = db.query(func.avg(BacktestResult.total_return)).scalar() or 0.0
        
        # Top performers - ensure it's ALWAYS a list
        top_results = db.query(BacktestResult).order_by(BacktestResult.win_rate.desc()).limit(10).all()
        top_coins = []
        for r in top_results:
            try:
                top_coins.append({
                    "symbol": r.coin.symbol if r.coin else "Unknown",
                    "strategy": r.strategy.name if r.strategy else "Unknown",
                    "win_rate": float(r.win_rate or 0),
                    "total_return": float(r.total_return or 0)
                })
            except Exception as e:
                logger.error(f"Error processing row: {e}")

        return jsonify({
            "total_coins_scanning": int(total_coins),
            "active_signals": int(active_signals),
            "today_total_signals": int(today_total_signals),
            "today_wins": int(today_wins),
            "today_losses": int(today_losses),
            "today_win_rate": round(float(today_win_rate if total_today > 0 else avg_wr), 1),
            "today_loss_rate": round(float(today_loss_rate), 1),
            "total_return": round(float(total_ret), 2),
            "top_performing_coins": top_coins,
            "bot_status": "running"
        })
    finally:
        db.close()
