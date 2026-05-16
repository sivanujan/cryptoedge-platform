import logging
from flask import Blueprint, jsonify, request
from sqlalchemy.orm import Session
from sqlalchemy import func
from database.connection import SessionLocal
from database.models import Strategy, Signal, Trade, BacktestResult, CoinStrategyMap
from datetime import datetime

logger = logging.getLogger(__name__)
strategies_bp = Blueprint('strategies', __name__, url_prefix='/api/v1/strategies')

@strategies_bp.route("/all", methods=["GET"])
def list_all_strategies():
    """Return all strategies including inactive ones."""
    db = SessionLocal()
    try:
        strategies = db.query(Strategy).all()
        return jsonify([{"id": s.id, "name": s.name} for s in strategies])
    finally:
        db.close()

@strategies_bp.route("", methods=["GET"])
def list_strategies():
    """Return all strategies in the library."""
    db = SessionLocal()
    try:
        strategies = db.query(Strategy).filter_by(is_active=True).all()
        
        counts = db.query(CoinStrategyMap.strategy_id, func.count(CoinStrategyMap.id))\
            .filter_by(is_active=True)\
            .group_by(CoinStrategyMap.strategy_id)\
            .all()
        count_map = {strat_id: count for strat_id, count in counts}

        averages = db.query(BacktestResult.strategy_id, func.avg(BacktestResult.win_rate))\
            .group_by(BacktestResult.strategy_id)\
            .all()
        avg_map = {strat_id: float(avg) for strat_id, avg in averages if avg is not None}

        result = []
        for s in strategies:
            result.append({
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "parameters": s.parameters,
                "coin_count": count_map.get(s.id, 0),
                "avg_win_rate": round(avg_map.get(s.id, 0.0), 1),
                "has_python_code": bool(s.python_code),
                "has_pine_script": bool(s.pine_script),
                # New fields for Strategy Signal Engine
                "coins_tested": s.coins_tested,
                "timeframes": s.timeframes,
                "best_win_rate": s.best_win_rate,
                "best_tf": s.best_tf,
                "coins_above_65": s.coins_above_65,
                "tags": s.tags,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            })
        return jsonify({"strategies": result})
    finally:
        db.close()

@strategies_bp.route("", methods=["POST"])
def create_strategy():
    """Add a new strategy to the library."""
    db = SessionLocal()
    try:
        data = request.json or {}
        name = data.get("name")
        description = (data.get("description") or "").strip()
        pine_script = (data.get("pine_script") or "").strip() or None
        
        if not name or not name.strip():
            return jsonify({"status": "error", "message": "Name is required"}), 400
        name = name.strip()

        existing = db.query(Strategy).filter_by(name=name).first()
        if existing:
            return jsonify({"status": "error", "message": "Strategy with this name already exists"}), 400

        # Ensure parameters is a dict even if null passed
        params = data.get("parameters")
        if params is None: params = {}

        strategy = Strategy(
            name=name,
            description=description if description else None,
            pine_script=pine_script,
            parameters=params,
            is_active=True,
            # New fields for Strategy Signal Engine
            coins_tested=data.get("coins_tested"),
            timeframes=data.get("timeframes"),
            best_win_rate=data.get("best_win_rate"),
            best_tf=data.get("best_tf"),
            coins_above_65=data.get("coins_above_65"),
            tags=data.get("tags"),
        )
        db.add(strategy)
        db.commit()
        db.refresh(strategy)
        logger.info(f"Created new strategy: {strategy.name} (ID: {strategy.id})")
        return jsonify({"id": strategy.id, "name": strategy.name, "status": "success"})
    except Exception as e:
        logger.exception(f"Error in create_strategy: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()

@strategies_bp.route("/<int:strategy_id>/convert-pine", methods=["POST"])
def convert_pine_script(strategy_id):
    """Convert Pine Script to Python using AI."""
    from services.ai_service import convert_pine_to_python, validate_strategy_code
    from strategies.golden_cross import STRATEGY_REGISTRY
    
    db = SessionLocal()
    try:
        strategy = db.query(Strategy).filter_by(id=strategy_id).first()
        if not strategy:
            return jsonify({"error": "Strategy not found"}), 404
        
        if not strategy.pine_script:
            return jsonify({"error": "No Pine Script to convert"}), 400

        try:
            python_code = convert_pine_to_python(strategy.pine_script, strategy.name)
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 502

        is_valid, err = validate_strategy_code(python_code)
        if not is_valid:
            return jsonify({"error": f"AI generated invalid code: {err}"}), 422

        strategy.python_code = python_code
        db.commit()
        return jsonify({"status": "success", "message": "Converted successfully"})
    finally:
        db.close()

@strategies_bp.route("/<int:strategy_id>/reactivate", methods=["POST"])
def reactivate_strategy(strategy_id):
    """Reactivate a strategy."""
    db = SessionLocal()
    try:
        strategy = db.query(Strategy).filter_by(id=strategy_id).first()
        if not strategy:
            return jsonify({"error": "Strategy not found"}), 404
        strategy.is_active = True
        db.commit()
        return jsonify({"status": "success"})
    finally:
        db.close()

@strategies_bp.route("/<int:strategy_id>/python-code", methods=["GET"])
def get_python_code(strategy_id):
    """Get the Python code of a strategy."""
    db = SessionLocal()
    try:
        strategy = db.query(Strategy).filter_by(id=strategy_id).first()
        if not strategy:
            return jsonify({"error": "Strategy not found"}), 404
        return jsonify({"python_code": strategy.python_code})
    finally:
        db.close()

@strategies_bp.route("/<int:strategy_id>/coins", methods=["GET"])
def get_strategy_coins(strategy_id):
    """Get coins mapped to this strategy."""
    db = SessionLocal()
    try:
        mappings = db.query(CoinStrategyMap).filter_by(strategy_id=strategy_id, is_active=True).all()
        return jsonify([{"symbol": m.coin.symbol, "id": m.coin_id} for m in mappings])
    finally:
        db.close()

@strategies_bp.route("/<int:strategy_id>", methods=["DELETE"])
def delete_strategy(strategy_id):
    """Permanent delete of a strategy and data."""
    db = SessionLocal()
    try:
        strategy = db.query(Strategy).filter_by(id=strategy_id).first()
        if not strategy:
            return jsonify({"error": "Strategy not found"}), 404
        
        signals = db.query(Signal).filter_by(strategy_id=strategy_id).all()
        signal_ids = [s.id for s in signals]
        
        if signal_ids:
            db.query(Trade).filter(Trade.signal_id.in_(signal_ids)).delete(synchronize_session=False)
        
        db.query(Signal).filter_by(strategy_id=strategy_id).delete(synchronize_session=False)
        db.query(BacktestResult).filter_by(strategy_id=strategy_id).delete(synchronize_session=False)
        db.query(CoinStrategyMap).filter_by(strategy_id=strategy_id).delete(synchronize_session=False)
        
        db.delete(strategy)
        db.commit()
        return jsonify({"status": "success"})
    finally:
        db.close()

@strategies_bp.route("/<int:strategy_id>/import-results", methods=["POST"])
def import_coin_results(strategy_id):
    """Bulk import coin results from CSV or JSON."""
    db = SessionLocal()
    try:
        data = request.json or {}
        results_data = data.get("results")
        format_type = data.get("format", "json") # "csv" or "json"
        
        if not results_data:
            return jsonify({"status": "error", "message": "No data provided"}), 400
            
        from database.models import CoinResult, Strategy
        
        strategy = db.query(Strategy).filter_by(id=strategy_id).first()
        if not strategy:
            return jsonify({"status": "error", "message": "Strategy not found"}), 404
            
        imported_count = 0
        
        if format_type == "json":
            for item in results_data:
                coin = item.get("coin")
                if not coin: continue
                
                existing = db.query(CoinResult).filter_by(strategy_id=strategy_id, coin=coin).first()
                if existing:
                    db.delete(existing)
                    
                coin_result = CoinResult(
                    strategy_id=strategy_id,
                    coin=coin,
                    tf_results=item.get("tf_results"),
                    best_tf=item.get("best_tf"),
                    best_win_rate=item.get("best_win_rate"),
                    trades_at_best=item.get("trades_at_best"),
                    return_pct=item.get("return_pct"),
                    drawdown=item.get("drawdown")
                )
                db.add(coin_result)
                imported_count += 1
                
        elif format_type == "csv":
            import csv
            from io import StringIO
            
            f = StringIO(results_data)
            reader = csv.DictReader(f)
            
            for row in reader:
                coin = row.get("coin")
                if not coin: continue
                
                tf_results = {}
                for tf in ["5m", "15m", "1h", "2h", "4h", "1d"]:
                    win = row.get(f"{tf}_win")
                    trades = row.get(f"{tf}_trades")
                    if win is not None and trades is not None:
                        tf_results[tf] = {
                            "win_rate": float(win) if win else 0.0,
                            "trades": int(trades) if trades else 0
                        }
                        
                existing = db.query(CoinResult).filter_by(strategy_id=strategy_id, coin=coin).first()
                if existing:
                    db.delete(existing)
                    
                # Infer best_win_rate and trades_at_best from tf_results if not in CSV
                best_tf = row.get("best_tf")
                best_win = float(row.get("best_win_rate")) if row.get("best_win_rate") else None
                trades_at_best = int(row.get("trades_at_best")) if row.get("trades_at_best") else None
                
                if best_tf and not best_win and best_tf in tf_results:
                    best_win = tf_results[best_tf]["win_rate"]
                    trades_at_best = tf_results[best_tf]["trades"]
                    
                coin_result = CoinResult(
                    strategy_id=strategy_id,
                    coin=coin,
                    tf_results=tf_results,
                    best_tf=best_tf,
                    best_win_rate=best_win,
                    trades_at_best=trades_at_best,
                    return_pct=float(row.get("return_pct")) if row.get("return_pct") else None,
                    drawdown=float(row.get("drawdown")) if row.get("drawdown") else None
                )
                db.add(coin_result)
                imported_count += 1
                
        db.commit()
        
        # Calculate rankings after import
        from services.ranking_service import calculate_and_store_rankings
        calculate_and_store_rankings(db, strategy_id)
        
        return jsonify({"status": "success", "message": f"Imported {imported_count} results and updated rankings"})
    except Exception as e:
        db.rollback()
        logger.exception(f"Error in import_coin_results: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()


@strategies_bp.route("/<int:strategy_id>/rankings", methods=["GET"])
def get_strategy_rankings(strategy_id):
    """Fetch stored rankings for a strategy."""
    db = SessionLocal()
    try:
        from database.models import StrategyRanking
        rankings = db.query(StrategyRanking).filter_by(strategy_id=strategy_id).order_by(StrategyRanking.final_score.desc()).all()
        
        result = []
        for r in rankings:
            result.append({
                "id": r.id,
                "coin": r.coin,
                "timeframe": r.timeframe,
                "win_rate": r.win_rate,
                "trades": r.trades,
                "confidence": r.confidence,
                "final_score": r.final_score
            })
            
        return jsonify({"status": "success", "rankings": result})
    except Exception as e:
        logger.exception(f"Error in get_strategy_rankings: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()
