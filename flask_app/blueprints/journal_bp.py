import logging
from flask import Blueprint, jsonify, request
from database.connection import SessionLocal
from database.models import JournalTrade
import services.journal_service as journal_service

logger = logging.getLogger(__name__)

journal_bp = Blueprint("journal", __name__, url_prefix="/api/v1/journal")

@journal_bp.route("/trades", methods=["GET"])
def get_trades():
    db = SessionLocal()
    try:
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 50))
        offset = (page - 1) * limit
        
        query = db.query(JournalTrade).order_by(JournalTrade.entry_time.desc())
        
        # Optional filters
        symbol = request.args.get("symbol")
        if symbol:
            query = query.filter(JournalTrade.symbol == symbol)
            
        side = request.args.get("side")
        if side:
            query = query.filter(JournalTrade.side == side)
            
        total = query.count()
        trades = query.offset(offset).limit(limit).all()
        
        result = []
        for t in trades:
            result.append({
                "id": t.id,
                "symbol": t.symbol,
                "side": t.side,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "qty": t.qty,
                "invested": t.invested,
                "returned": t.returned,
                "pnl": t.pnl,
                "pnl_percent": t.pnl_percent,
                "entry_time": t.entry_time.isoformat(),
                "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                "hold_time_mins": t.hold_time_mins,
                "status": t.status
            })
            
        return jsonify({
            "total": total,
            "page": page,
            "limit": limit,
            "trades": result
        })
    finally:
        db.close()

@journal_bp.route("/summary", methods=["GET"])
def get_summary():
    result = journal_service.get_performance_summary()
    return jsonify(result)

@journal_bp.route("/coins", methods=["GET"])
def get_coins():
    result = journal_service.get_coin_performance()
    return jsonify(result)

@journal_bp.route("/mistakes", methods=["GET"])
def get_mistakes():
    result = journal_service.generate_ai_mistake_analysis()
    return jsonify(result)

@journal_bp.route("/refresh", methods=["POST"])
def refresh_trades():
    result = journal_service.fetch_and_sync_trades()
    return jsonify(result)

@journal_bp.route("/calendar", methods=["GET"])
def get_calendar():
    db = SessionLocal()
    try:
        from sqlalchemy import func
        # Group by date of exit_time
        trades = db.query(
            func.date(JournalTrade.exit_time).label('date'),
            func.sum(JournalTrade.pnl).label('pnl'),
            func.count(JournalTrade.id).label('count')
        ).filter(JournalTrade.status == "CLOSED", JournalTrade.exit_time.isnot(None)).group_by(func.date(JournalTrade.exit_time)).all()
        
        result = []
        for t in trades:
            result.append({
                "date": str(t.date),
                "pnl": t.pnl,
                "count": t.count
            })
        return jsonify(result)
    finally:
        db.close()
