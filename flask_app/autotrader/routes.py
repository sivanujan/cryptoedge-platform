import logging
from flask import Blueprint, jsonify, request
from database.connection import SessionLocal
from database.models import AutoTradeSetting, AutoTrade
from . import engine
from .strategies import AVAILABLE_STRATEGIES
import json

logger = logging.getLogger(__name__)

autotrader_bp = Blueprint('autotrader', __name__, url_prefix='/api/v1/autotrader')

@autotrader_bp.route('/status', methods=['GET'])
def status():
    db = SessionLocal()
    try:
        settings = engine.get_settings(db)
        total_bal, avail_bal, unrl_pnl = 0.0, 0.0, 0.0
        try:
            from . import binance_executor
            total_bal, avail_bal, unrl_pnl = binance_executor.get_futures_balance()
        except Exception as e:
            logger.error(f"Error in status endpoint fetching balance: {e}")
            
        open_count = db.query(AutoTrade).filter_by(status="OPEN").count()
        
        return jsonify({
            "status": "success", 
            "is_enabled": settings.is_enabled,
            "futures_balance": total_bal,
            "available_balance": avail_bal,
            "unrealized_pnl": unrl_pnl,
            "open_positions_count": open_count,
            "daily_pnl": 0.0,
            "engine_message": "Engine active and scanning" if settings.is_enabled else "Engine stopped"
        })
    finally:
        db.close()

@autotrader_bp.route('/strategies', methods=['GET'])
def strategies():
    db = SessionLocal()
    try:
        from database.models import Strategy
        settings = engine.get_settings(db)
        enabled_list = []
        try:
            enabled_list = json.loads(settings.enabled_strategies)
        except:
            pass
            
        result = []
            
        # Add dynamic strategies from DB ONLY
        try:
            db_strats = db.query(Strategy).filter_by(is_active=True).all()
            for s in db_strats:
                result.append({
                    "name": s.name,
                    "enabled": s.name in enabled_list,
                    "description": s.description or f"Custom strategy {s.name}",
                    "signals_today": 0
                })
        except Exception as e:
            logger.error(f"Error fetching db strategies: {e}")
            
        return jsonify({"status": "success", "strategies": result})
    finally:
        db.close()

@autotrader_bp.route('/strategies/<path:name>/toggle', methods=['POST'])
def toggle_strategy(name):
    db = SessionLocal()
    try:
        settings = engine.get_settings(db)
        enabled_list = []
        try:
            enabled_list = json.loads(settings.enabled_strategies)
        except:
            pass
            
        if name in enabled_list:
            enabled_list.remove(name)
        else:
            enabled_list.append(name)
            
        settings.enabled_strategies = json.dumps(enabled_list)
        db.commit()
        return jsonify({"status": "success"})
    finally:
        db.close()

@autotrader_bp.route('/settings', methods=['GET'])
def get_settings():
    db = SessionLocal()
    try:
        settings = engine.get_settings(db)
        return jsonify({
            "leverage": settings.leverage,
            "per_trade_percent": settings.per_trade_percent,
            "max_open_trades": settings.max_open_trades,
            "daily_loss_limit": settings.daily_loss_limit
        })
    finally:
        db.close()

@autotrader_bp.route('/enable', methods=['POST'])
def enable():
    db = SessionLocal()
    try:
        settings = engine.get_settings(db)
        settings.is_enabled = True
        db.commit()
        engine.start_engine()
        return jsonify({"status": "success", "message": "Engine started"})
    finally:
        db.close()

@autotrader_bp.route('/disable', methods=['POST'])
def disable():
    db = SessionLocal()
    try:
        settings = engine.get_settings(db)
        settings.is_enabled = False
        db.commit()
        engine.stop_engine()
        return jsonify({"status": "success", "message": "Engine stopped"})
    finally:
        db.close()

@autotrader_bp.route('/settings', methods=['POST'])
def save_settings():
    db = SessionLocal()
    try:
        data = request.json
        settings = engine.get_settings(db)
        settings.leverage = data.get('leverage', settings.leverage)
        settings.per_trade_percent = data.get('per_trade_percent', settings.per_trade_percent)
        settings.max_open_trades = data.get('max_open_trades', settings.max_open_trades)
        settings.daily_loss_limit = data.get('daily_loss_limit', settings.daily_loss_limit)
        if 'enabled_strategies' in data:
            settings.enabled_strategies = json.dumps(data['enabled_strategies'])
        db.commit()
        return jsonify({"status": "success"})
    finally:
        db.close()

@autotrader_bp.route('/positions', methods=['GET'])
def positions():
    db = SessionLocal()
    try:
        trades = db.query(AutoTrade).filter_by(status="OPEN").all()
        return jsonify({"status": "success", "positions": [{"id": t.id, "symbol": t.symbol, "side": t.side, "entry": t.entry_price, "pnl": t.pnl, "sl": t.sl_price, "tp1": t.tp1, "tp2": t.tp2, "tp3": t.tp3} for t in trades]})
    finally:
        db.close()

@autotrader_bp.route('/trades', methods=['GET'])
def history():
    db = SessionLocal()
    try:
        trades = db.query(AutoTrade).filter(AutoTrade.status != "OPEN").order_by(AutoTrade.id.desc()).limit(20).all()
        return jsonify({"status": "success", "trades": [{"id": t.id, "symbol": t.symbol, "side": t.side, "entry": t.entry_price, "exit": t.exit_price, "pnl": t.pnl, "strategy": t.strategy_name, "status": t.status} for t in trades]})
    finally:
        db.close()
