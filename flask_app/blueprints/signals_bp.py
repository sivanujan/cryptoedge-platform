import logging
from flask import Blueprint, jsonify, request
from database.connection import SessionLocal
from database.models import Signal, Coin, Strategy
from datetime import datetime

logger = logging.getLogger(__name__)
signals_bp = Blueprint('signals', __name__, url_prefix='/api/v1/signals')

from sqlalchemy.orm import joinedload
from sqlalchemy import func

def _signal_to_dict(s: Signal, current_prices: dict = None) -> dict:
    # Get P&L from the first linked trade
    trade = s.trades[0] if s.trades else None
    pnl = float(trade.pnl_percent) if trade and trade.pnl_percent is not None else None
    exit_price = float(trade.exit_price) if trade and trade.exit_price is not None else None
    
    # Get current price from passed dict or fallback
    current_price = None
    if s.status == "active" and current_prices and s.coin.symbol in current_prices:
        current_price = current_prices[s.coin.symbol]
    elif s.status != "active":
        current_price = exit_price

    # Ensure all numeric fields are converted to float/int to avoid linter confusion
    entry_val = float(s.entry_price) if s.entry_price is not None else 0.0
    sl_val = float(s.stop_loss) if s.stop_loss is not None else None
    tp_val = float(s.take_profit) if s.take_profit is not None else None
    conf_val = float(s.confidence) if s.confidence is not None else 0.0
    vol_val = float(s.volatility) if s.volatility is not None else 0.0

    # Calculate live P&L for active signals
    if s.status == "active" and current_price and entry_val > 0:
        if s.signal_type == "BUY":
            pnl = (current_price - entry_val) / entry_val * 100
        else:
            pnl = (entry_val - current_price) / entry_val * 100

    return {
        "id": int(s.id),
        "symbol": str(s.coin.symbol) if s.coin else "UNKNOWN",
        "strategy": str(s.strategy.name) if s.strategy else "UNKNOWN",
        "signal_type": str(s.signal_type),
        "timeframe": str(s.timeframe),
        "entry_price": entry_val,
        "current_price": current_price,
        "exit_price": exit_price,
        "stop_loss": sl_val,
        "take_profit": tp_val,
        "confidence": conf_val,
        "volatility": vol_val,
        "status": str(s.status),
        "pnl_percent": pnl,
        "ai_analysis": s.ai_analysis,
        "ai_score": s.ai_score,
        "created_at": s.created_at.isoformat() + "Z" if s.created_at else None,
    }

@signals_bp.route("/<int:signal_id>", methods=["GET"])
def get_signal(signal_id):
    """Fetch a single signal with live price data."""
    db = SessionLocal()
    try:
        s = db.query(Signal).options(
            joinedload(Signal.coin), 
            joinedload(Signal.strategy), 
            joinedload(Signal.trades)
        ).filter_by(id=signal_id).first()
        
        if not s:
            return jsonify({"status": "error", "message": "Signal not found"}), 404
            
        current_prices = {}
        if s.status == "active":
             from services.binance_service import get_multiple_tickers
             tickers_data = get_multiple_tickers([s.coin.symbol])
             current_prices = {sym: data["last"] for sym, data in tickers_data.items() if data.get("last")}

        return jsonify({
            "status": "success",
            "signal": _signal_to_dict(s, current_prices)
        })
    finally:
        db.close()

@signals_bp.route("/history", methods=["GET"])
def signal_history():
    """Return signal history with full statistics for the SignalHistory page."""
    db = SessionLocal()
    try:
        coin_filter = request.args.get("coin")
        strategy_filter = request.args.get("strategy")
        signal_type = request.args.get("signal_type")
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))

        query = db.query(Signal).options(joinedload(Signal.coin), joinedload(Signal.strategy), joinedload(Signal.trades))
        
        if coin_filter:
            query = query.join(Coin).filter(Coin.symbol.ilike(f"%{coin_filter}%"))

        if signal_type:
            query = query.filter(Signal.signal_type == signal_type.upper())

        total = query.count()
        signals = query.order_by(Signal.created_at.desc()).offset(offset).limit(limit).all()

        # Fetch current prices for active signals using the more robust multi-ticker service
        active_symbols = [s.coin.symbol for s in signals if s.status == "active"]
        current_prices = {}
        if active_symbols:
            from services.binance_service import get_multiple_tickers
            tickers_data = get_multiple_tickers(active_symbols)
            # Convert {symbol: {last: X, ...}} to {symbol: X}
            current_prices = {sym: data["last"] for sym, data in tickers_data.items() if data.get("last")}

        # Summary statistics calculation
        all_signals = db.query(Signal).options(joinedload(Signal.trades)).all()
        
        def is_win(s):
            if s.status == "closed": return True
            t = s.trades[0] if s.trades else None
            return t and t.pnl_percent and t.pnl_percent > 0

        def is_loss(s):
            if s.status == "stopped": return True
            t = s.trades[0] if s.trades else None
            return t and t.pnl_percent and t.pnl_percent < 0

        from sqlalchemy import func
        from database.models import BacktestResult
        wins_count = int(sum(1 for s in all_signals if is_win(s)))
        losses_count = int(sum(1 for s in all_signals if is_loss(s)))
        
        # Fallback to BacktestResult if no real trades
        if wins_count == 0 and losses_count == 0:
            total_trades_val = db.query(func.sum(BacktestResult.total_trades)).scalar() or 0
            avg_wr = db.query(func.avg(BacktestResult.win_rate)).scalar() or 0.0
            wins_count = int(float(total_trades_val) * float(avg_wr) / 100)
            losses_count = int(total_trades_val) - wins_count
            total_pnl_val = float(db.query(func.avg(BacktestResult.total_return)).scalar() or 0.0)
        else:
            total_pnl_val = 0.0
            for s in all_signals:
                if s.trades and s.trades[0].pnl_percent is not None:
                    total_pnl_val += float(s.trades[0].pnl_percent)
            
        total_rated = wins_count + losses_count
        wr = round(float(wins_count) / total_rated * 100, 1) if total_rated > 0 else 0.0
        total_pnl_res = round(total_pnl_val, 2)

        # ── Strategy stats: include ALL active strategies, use backtest data for win rate ──
        from database.models import BacktestResult
        from sqlalchemy import func

        # Build signal counts per strategy (from live signals)
        signal_counts = {}    # strategy_name -> {total, wins, losses, total_pnl}
        for s in all_signals:
            nm = str(s.strategy.name) if s.strategy else "Unknown"
            if nm not in signal_counts:
                signal_counts[nm] = {"total_signals": 0, "wins": 0, "losses": 0, "total_pnl": 0.0}
            signal_counts[nm]["total_signals"] += 1
            if is_win(s):
                signal_counts[nm]["wins"] += 1
            elif is_loss(s):
                signal_counts[nm]["losses"] += 1
            if s.trades and s.trades[0].pnl_percent is not None:
                signal_counts[nm]["total_pnl"] += float(s.trades[0].pnl_percent)

        # Fetch ALL active strategies from DB so new ones always appear
        all_strategies = db.query(Strategy).filter_by(is_active=True).all()

        strategy_stats = []
        for strat in all_strategies:
            nm = strat.name
            base = signal_counts.get(nm, {"total_signals": 0, "wins": 0, "losses": 0, "total_pnl": 0.0})

            # Best single BacktestResult for this strategy (best win_rate with most trades)
            best_br = (
                db.query(BacktestResult)
                .filter(
                    BacktestResult.strategy_id == strat.id,
                    BacktestResult.win_rate.isnot(None),
                    BacktestResult.total_trades > 0,
                )
                .order_by(BacktestResult.win_rate.desc(), BacktestResult.total_trades.desc())
                .first()
            )

            # Average win rate across all BacktestResults for this strategy
            avg_wr = db.query(func.avg(BacktestResult.win_rate)).filter(
                BacktestResult.strategy_id == strat.id,
                BacktestResult.win_rate.isnot(None)
            ).scalar()

            # Win rate priority: real trades > backtest average > 0
            tw, tl = int(base["wins"]), int(base["losses"])
            denom = tw + tl
            if denom > 0:
                win_rate = round(float(tw) / denom * 100, 1)
            elif avg_wr is not None:
                win_rate = round(float(avg_wr), 1)
            else:
                win_rate = 0.0

            # P&L: use real signal P&L if present, else best backtest
            total_pnl = round(float(base["total_pnl"]), 2)
            if total_pnl == 0.0 and best_br and best_br.total_return:
                total_pnl = round(float(best_br.total_return), 2)

            # Best coin & timeframe from backtest
            best_coin = best_br.coin.symbol if best_br and best_br.coin else None
            best_tf = best_br.timeframe if best_br else None

            strategy_stats.append({
                "name": nm,
                "total_signals": int(base["total_signals"]),
                "wins": tw,
                "losses": tl,
                "win_rate": win_rate,
                "total_pnl": total_pnl,
                "best_coin": best_coin,
                "best_timeframe": best_tf,
                "has_backtest": best_br is not None,
            })

        # Sort by win_rate desc, then by total signals
        strategy_stats.sort(key=lambda x: (x["win_rate"], x["total_signals"]), reverse=True)

        return jsonify({
            "status": "success",
            "signals": [_signal_to_dict(s, current_prices) for s in signals],
            "total": total,
            "total_signals": len(all_signals),
            "wins": wins_count,
            "losses": losses_count,
            "win_rate": wr,
            "total_pnl": total_pnl_res,
            "strategy_stats": strategy_stats
        })
    except Exception as e:
        logger.exception(f"Error in signal_history: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()

@signals_bp.route("/live", methods=["GET"])
def live_signals():
    # Reuse signal_history with limit 10
    return signal_history()

@signals_bp.route("/history", methods=["DELETE"])
def clear_history():
    db = SessionLocal()
    try:
        db.query(Signal).delete()
        db.commit()
        return jsonify({"status": "success"})
    finally:
        db.close()

@signals_bp.route("/scan-now", methods=["POST"])
def scan_now():
    from services.scanner_service import run_scanner
    import threading
    threading.Thread(target=run_scanner).start()
    return jsonify({"status": "success"})
