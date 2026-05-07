import logging
from flask import Blueprint, jsonify, request
from sqlalchemy.orm import Session
from database.connection import SessionLocal
from database.scanner_models import BreakoutSignal, ScannerRun

logger = logging.getLogger(__name__)
scanner_bp = Blueprint('scanner', __name__, url_prefix='/api/v1/scanner')

from database.models import Signal, Strategy, Coin
from sqlalchemy import func
from datetime import datetime

def _signal_to_dict(s: Signal) -> dict:
    # Try to get pnl from first trade linked to this signal
    trade = s.trades[0] if s.trades else None
    pnl = float(trade.pnl_percent) if trade and trade.pnl_percent is not None else None
    
    return {
        "id": s.id,
        "symbol": s.coin.symbol if s.coin else "UNKNOWN",
        "strategy": s.strategy.name if s.strategy else "UNKNOWN",
        "signal_type": s.signal_type,
        "timeframe": s.timeframe,
        "entry_price": float(s.entry_price),
        "stop_loss": float(s.stop_loss) if s.stop_loss else None,
        "take_profit": float(s.take_profit) if s.take_profit else None,
        "confidence": float(s.confidence) if s.confidence else 0,
        "volatility": float(s.volatility) if s.volatility else 0,
        "status": s.status,
        "pnl_percent": pnl,
        "created_at": s.created_at.isoformat() + "Z" if s.created_at else None,
    }

@scanner_bp.route("/signals", methods=["GET"])
def list_signals():
    db = SessionLocal()
    try:
        coin_filter = request.args.get("coin")
        strategy_filter = request.args.get("strategy")
        signal_type = request.args.get("signal_type")
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))

        from sqlalchemy.orm import joinedload
        query = db.query(Signal).options(joinedload(Signal.coin), joinedload(Signal.strategy), joinedload(Signal.trades))
        
        if coin_filter:
            query = query.join(Coin).filter(Coin.symbol.ilike(f"%{coin_filter}%"))
        if strategy_filter:
            query = query.join(Strategy).filter(Strategy.name.ilike(f"%{strategy_filter}%"))
        if signal_type:
            query = query.filter(Signal.signal_type == signal_type.upper())

        total = query.count()
        signals = query.order_by(Signal.created_at.desc()).offset(offset).limit(limit).all()

        # Calculate Summary Stats for Signal History UI
        all_signals = db.query(Signal).options(joinedload(Signal.trades)).all()
        total_signals = len(all_signals)
        
        def is_win(s):
            if s.status == "closed": return True
            t = s.trades[0] if s.trades else None
            return t and t.pnl_percent and t.pnl_percent > 0

        def is_loss(s):
            if s.status == "stopped": return True
            t = s.trades[0] if s.trades else None
            return t and t.pnl_percent and t.pnl_percent < 0

        wins_count = sum(1 for s in all_signals if is_win(s))
        losses_count = sum(1 for s in all_signals if is_loss(s))
        wr = round(float(wins_count) / (wins_count + losses_count) * 100, 1) if (wins_count + losses_count) > 0 else 0
        
        total_pnl_val = 0.0
        for s in all_signals:
            t = s.trades[0] if s.trades else None
            if t and t.pnl_percent:
                total_pnl_val += float(t.pnl_percent)
        total_pnl_res = round(total_pnl_val, 2)

        # Strategy breakdown statistics
        strategy_data = {}
        for s in all_signals:
            nm = s.strategy.name if s.strategy else "Unknown"
            if nm not in strategy_data:
                strategy_data[nm] = {"name": nm, "total_signals": 0, "wins": 0, "losses": 0, "total_pnl": 0.0}
            
            stats_dict = strategy_data[nm]
            stats_dict["total_signals"] += 1
            if is_win(s): stats_dict["wins"] += 1
            elif is_loss(s): stats_dict["losses"] += 1
            
            t = s.trades[0] if s.trades else None
            if t and t.pnl_percent:
                stats_dict["total_pnl"] += float(t.pnl_percent)

        strategy_stats_list = []
        for nm, d_st in strategy_data.items():
            tw = d_st["wins"]
            tl = d_st["losses"]
            d_st["win_rate"] = round(float(tw) / (tw + tl) * 100, 1) if (tw + tl) > 0 else 0
            d_st["total_pnl"] = round(float(d_st["total_pnl"]), 2)
            strategy_stats_list.append(d_st)

        return jsonify({
            "status": "success",
            "total_signals": total_signals,
            "wins": wins_count,
            "losses": losses_count,
            "win_rate": wr,
            "total_pnl": total_pnl_res,
            "strategy_stats": sorted(strategy_stats_list, key=lambda x: x["total_pnl"], reverse=True),
            "signals": [_signal_to_dict(s) for s in signals],
            "total": total
        })
    finally:
        db.close()

@scanner_bp.route("/stats", methods=["GET"])
def get_scanner_stats():
    # Keep the existing breakout stats or merge? 
    # For now, let's keep it consistent with signals
    return list_signals()

@scanner_bp.route("/run", methods=["POST"])
def trigger_scanner():
    from services.scanner_service import run_scanner
    import threading
    threading.Thread(target=run_scanner).start()
    return jsonify({"status": "started"})
