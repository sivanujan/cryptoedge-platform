import logging
import uuid
import threading
from datetime import datetime
from flask import Blueprint, jsonify, request
from sqlalchemy.orm import Session, joinedload
from database.connection import SessionLocal
from database.models import BacktestResult, Coin, Strategy, BacktestJob
from services.backtest_service import run_backtest, assign_best_strategies

logger = logging.getLogger(__name__)
backtest_bp = Blueprint('backtest', __name__, url_prefix='/api/v1/backtest')

@backtest_bp.route("/results", methods=["GET"])
def backtest_results():
    """Return filtered backtest results."""
    db = SessionLocal()
    try:
        strategy = request.args.get("strategy")
        timeframe = request.args.get("timeframe")
        limit = int(request.args.get("limit", 200))
        
        query = db.query(BacktestResult).options(joinedload(BacktestResult.coin), joinedload(BacktestResult.strategy)).join(Coin).join(Strategy)
        
        if strategy:
            if strategy.isdigit():
                query = query.filter(BacktestResult.strategy_id == int(strategy))
            else:
                query = query.filter(Strategy.name.ilike(f"%{strategy}%"))
        if timeframe:
            query = query.filter(BacktestResult.timeframe == timeframe)
            
        results = query.order_by(BacktestResult.win_rate.desc()).limit(limit).all()
        total_count = query.count()  # Total before limit
        
        return jsonify({
            "total": total_count,
            "results": [
                {
                    "id": r.id,
                    "symbol": r.coin.symbol if r.coin else "",
                    "strategy": r.strategy.name if r.strategy else "",
                    "timeframe": r.timeframe,
                    "win_rate": float(r.win_rate) if r.win_rate is not None else 0.0,
                    "total_trades": r.total_trades,
                    "total_return": float(r.total_return) if r.total_return is not None else 0.0,
                    "max_drawdown": float(r.max_drawdown) if r.max_drawdown is not None else 0.0,
                    "sharpe_ratio": float(r.sharpe_ratio) if r.sharpe_ratio is not None else 0.0,
                    "volatility": float(r.volatility) if r.volatility is not None else 0.0
                } for r in results
            ]
        })
    finally:
        db.close()

@backtest_bp.route("/results/table", methods=["GET"])
def backtest_results_table():
    """Return all backtest results grouped by (coin, strategy), containing all timeframes."""
    db = SessionLocal()
    try:
        strategy_id = request.args.get("strategy_id")
        query = db.query(BacktestResult).options(joinedload(BacktestResult.coin), joinedload(BacktestResult.strategy))
        
        if strategy_id:
            query = query.filter(BacktestResult.strategy_id == int(strategy_id))

        results = query.all()

        # Fallback to CoinResult (imported data) if internal backtest has no results
        if not results and strategy_id:
            from database.models import CoinResult, Strategy
            coin_results = db.query(CoinResult).filter_by(strategy_id=int(strategy_id)).all()
            strat = db.query(Strategy).filter_by(id=int(strategy_id)).first()
            strat_name = strat.name if strat else f"Strategy {strategy_id}"
            
            if coin_results:
                grouped = {}
                for r in coin_results:
                    key = (r.coin, strat_name, int(strategy_id))
                    
                    if key not in grouped:
                        grouped[key] = {
                            "coin": r.coin,
                            "coin_id": 0,
                            "strategy": strat_name,
                            "strategy_id": int(strategy_id),
                            "results": {},
                            "best_timeframe": r.best_tf,
                            "best_win_rate": float(r.best_win_rate) if r.best_win_rate else None
                        }
                        
                    tf_res = r.tf_results or {}
                    for tf, data in tf_res.items():
                        grouped[key]["results"][tf] = {
                            "win_rate": float(data.get("win_rate")) if data.get("win_rate") is not None else None,
                            "trades": data.get("trades"),
                            "return_pct": float(r.return_pct) if r.return_pct is not None else None,
                            "drawdown": float(r.drawdown) if r.drawdown is not None else None,
                            "volatility": 0.0,
                        }
                
                table_data = list(grouped.values())
                
                # Sort fallback data too
                def get_weighted_score(item):
                    wr = item.get("best_win_rate")
                    tf = item.get("best_timeframe")
                    trades = item["results"].get(tf, {}).get("trades")
                    if trades is None: trades = 0
                    if wr is None: return -1.0
                    return wr * min(trades, 10) / 10.0

                table_data.sort(key=get_weighted_score, reverse=True)
                return jsonify(table_data)

        # Group by (coin symbol, strategy)
        grouped = {}
        for r in results:
            if not r.coin or not r.strategy:
                continue

            key = (r.coin.symbol, r.strategy.name, r.strategy.id)
            if key not in grouped:
                grouped[key] = {
                    "coin": r.coin.symbol,
                    "coin_id": r.coin.id,
                    "strategy": r.strategy.name,
                    "strategy_id": r.strategy.id,
                    "results": {},
                    "best_timeframe": None,
                    "best_win_rate": None
                }

            # Add timeframe data
            grouped[key]["results"][r.timeframe] = {
                "win_rate": float(r.win_rate) if r.win_rate is not None else None,
                "trades": r.total_trades,
                "return_pct": float(r.total_return) if r.total_return is not None else None,
                "drawdown": float(r.max_drawdown) if r.max_drawdown is not None else None,
                "volatility": float(r.volatility) if r.volatility is not None else 0,
            }

            # Track best timeframe
            if r.win_rate is not None:
                if grouped[key]["best_win_rate"] is None or r.win_rate > grouped[key]["best_win_rate"]:
                    grouped[key]["best_win_rate"] = float(r.win_rate)
                    grouped[key]["best_timeframe"] = r.timeframe

        # Convert to list and sort
        table_data = list(grouped.values())
        
        def get_weighted_score(item):
            wr = item.get("best_win_rate")
            tf = item.get("best_timeframe")
            trades = item["results"].get(tf, {}).get("trades")
            if trades is None: trades = 0
            if wr is None: return -1.0
            return wr * min(trades, 10) / 10.0

        table_data.sort(key=get_weighted_score, reverse=True)
        return jsonify(table_data)
    except Exception as e:
        logger.error(f"Error in backtest_table: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@backtest_bp.route("/summary/<int:strategy_id>", methods=["GET"])
def backtest_summary(strategy_id):
    """Return top-level summary statistics for a given strategy."""
    db = SessionLocal()
    try:
        # Get all results with a win rate for this strategy
        results = db.query(BacktestResult).options(joinedload(BacktestResult.coin)).filter(
            BacktestResult.strategy_id == strategy_id,
            BacktestResult.win_rate.isnot(None)
        ).all()
        
        if not results:
            return jsonify({
                "total_coins_tested": 0,
                "coins_above_65": 0,
                "coins_above_55": 0,
                "best_coin": None,
                "best_win_rate": 0,
                "best_trades": 0,
                "best_timeframe_overall": None,
                "avg_win_rate_by_timeframe": {},
                "last_run": None
            })

        # Group by timeframe to calculate averages
        tf_stats = {}
        best_overall_wr = -1.0
        best_overall_coin = None
        best_overall_tf = None
        best_overall_trades = 0
        
        coins_tested = set()
        coins_above_65 = set()
        coins_above_55 = set()
        best_weighted_score = -1.0
        
        for r in results:
            coins_tested.add(r.coin_id)
            trades = r.total_trades or 0
            weight = min(trades, 10) / 10.0
            weighted_score = r.win_rate * weight
            
            if r.timeframe not in tf_stats:
                tf_stats[r.timeframe] = {"sum": 0, "count": 0}
                
            tf_stats[r.timeframe]["sum"] += r.win_rate
            tf_stats[r.timeframe]["count"] += 1
            
            if r.win_rate >= 65.0 and trades >= 3:
                coins_above_65.add(r.coin_id)
            if r.win_rate >= 55.0 and trades >= 3:
                coins_above_55.add(r.coin_id)
                
            if weighted_score > best_weighted_score:
                best_weighted_score = weighted_score
                best_overall_wr = float(r.win_rate)
                best_overall_tf = r.timeframe
                best_overall_coin = r.coin.symbol if r.coin else None
                best_overall_trades = trades

        # Calculate TF averages
        avg_by_tf = {}
        best_tf_overall = None
        best_tf_avg = -1.0
        for tf, data in tf_stats.items():
            avg = round(data["sum"] / data["count"], 1)
            avg_by_tf[tf] = avg
            if avg > best_tf_avg:
                best_tf_avg = avg
                best_tf_overall = tf

        return jsonify({
            "total_coins_tested": len(coins_tested),
            "coins_above_65": len(coins_above_65),
            "coins_above_55": len(coins_above_55),
            "best_coin": best_overall_coin,
            "best_win_rate": best_overall_wr if best_overall_wr >= 0 else 0,
            "best_trades": best_overall_trades,
            "best_timeframe_overall": best_tf_overall,
            "avg_win_rate_by_timeframe": avg_by_tf,
            "last_run": results[0].created_at.isoformat() if hasattr(results[0], 'created_at') and results[0].created_at else None
        })
    except Exception as e:
        logger.error(f"Error in backtest_summary: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        db.close()

@backtest_bp.route("/run-strategy/<int:strategy_id>", methods=["POST"])
def run_strategy_backtest(strategy_id):
    """Run backtest for a strategy on all coins × all timeframes in background."""
    TIMEFRAMES = ["5m", "15m", "1h", "2h", "4h", "1d"]
    db = SessionLocal()
    try:
        strategy = db.query(Strategy).filter_by(id=strategy_id).first()
        if not strategy:
            return jsonify({"error": "Strategy not found"}), 404
        
        data = request.get_json(silent=True) or {}
        selected_coin_ids = data.get("coin_ids", [])
        
        if selected_coin_ids:
            coins = db.query(Coin).filter(Coin.id.in_(selected_coin_ids), Coin.is_active==True).all()
        else:
            coins = db.query(Coin).filter_by(is_active=True).all()
            
        if not coins:
            return jsonify({"error": "No active coins found for backtest"}), 400
            
        job_id = f"job_{strategy_id}_{int(datetime.utcnow().timestamp())}"
        
        # DETACH all necessary info before starting thread (avoids session conflicts)
        strategy_name = strategy.name
        coin_data = [{"id": c.id, "symbol": c.symbol} for c in coins]
        total_tests = len(coin_data) * len(TIMEFRAMES)
        
        try:
            job = BacktestJob(
                id=job_id, status="running", strategy_id=strategy_id,
                total_tests=total_tests, completed=0,
                total_coins=len(coin_data), total_timeframes=len(TIMEFRAMES)
            )
            db.add(job)
            db.commit()
        except Exception as e:
            logger.error(f"FAILED TO CREATE BACKTEST JOB: {e}")
            db.rollback()
            return jsonify({"error": f"Database error creating job: {str(e)}"}), 500
        
        def _task(s_name, s_id, j_id, coins_list, timeframes):
            thread_db = SessionLocal()
            completed = 0
            try:
                from services.backtest_service import run_backtest
                from concurrent.futures import ThreadPoolExecutor, as_completed
                
                # Generate all tasks
                tasks = []
                for c_info in coins_list:
                    for tf in timeframes:
                        tasks.append((c_info, tf))
                        
                def run_single(c_info, tf):
                    # Each thread MUST have its own DB session!
                    local_db = SessionLocal()
                    try:
                        run_backtest(
                            symbol=c_info["symbol"],
                            strategy_name=s_name,
                            timeframe=tf,
                            db=local_db,
                            coin_id=c_info["id"],
                            strategy_id=s_id
                        )
                        return True
                    except Exception as e:
                        logger.warning(f"Backtest failed for {c_info['symbol']} {tf}: {e}")
                        return False
                    finally:
                        local_db.close()

                # Run in parallel with 5 workers
                with ThreadPoolExecutor(max_workers=5) as executor:
                    future_to_task = {executor.submit(run_single, c_info, tf): (c_info, tf) for c_info, tf in tasks}
                    
                    for future in as_completed(future_to_task):
                        c_info, tf = future_to_task[future]
                        completed += 1
                        
                        # Update progress every 5 tests to reduce DB load
                        if completed % 5 == 0 or completed == len(tasks):
                            j = thread_db.query(BacktestJob).filter_by(id=j_id).first()
                            if j:
                                j.completed = completed
                                j.current_coin = c_info["symbol"]
                                j.current_tf = tf
                                j.message = f"Testing {c_info['symbol']} on {tf}..."
                                thread_db.commit()
                
                # Mark complete
                j = thread_db.query(BacktestJob).filter_by(id=j_id).first()
                if j:
                    j.status = "complete"
                    j.completed = completed
                    j.message = "Backtest complete!"
                    thread_db.commit()
                logger.info(f"Backtest job {j_id} complete: {completed} tests")
                
                # Proactively calculate rankings in case they imported data for this strategy
                from services.ranking_service import calculate_and_store_rankings
                calculate_and_store_rankings(thread_db, s_id)
                
            except Exception as e:
                logger.error(f"BACKGROUND BACKTEST FAILED: {e}")
                try:
                    j = thread_db.query(BacktestJob).filter_by(id=j_id).first()
                    if j:
                        j.status = "error"
                        j.message = str(e)
                        thread_db.commit()
                except Exception:
                    pass
            finally:
                thread_db.close()
                
        threading.Thread(target=_task, args=(strategy_name, strategy_id, job_id, coin_data, TIMEFRAMES)).start()
        return jsonify({"job_id": job_id, "status": "started", "total_tests": total_tests})
    finally:
        db.close()

@backtest_bp.route("/progress/<string:job_id>", methods=["GET"])
def get_backtest_progress(job_id):
    """Return the progress of a background backtest job."""
    db = SessionLocal()
    try:
        job = db.query(BacktestJob).filter_by(id=job_id).first()
        if not job:
            return jsonify({"status": "not_found"}), 404
        return jsonify({
            "status": job.status,
            "completed": job.completed,
            "total": job.total_tests,
            "progress": (job.completed / job.total_tests * 100) if job.total_tests > 0 else 0
        })
    finally:
        db.close()

@backtest_bp.route("/assign-bulk", methods=["POST"])
def assign_bulk_strategies():
    """Assign best performing strategies to coins in bulk."""
    from database.models import Setting
    db = SessionLocal()
    try:
        data = request.json
        min_win_rate = float(data.get("min_win_rate", 60.0))
        timeframe = data.get("timeframe", "1h")
        
        count = assign_best_strategies(db, min_win_rate=min_win_rate, timeframe=timeframe)
        return jsonify({"status": "success", "count": count})
    finally:
        db.close()

@backtest_bp.route("/run", methods=["POST"])
def run_manual_backtest():
    """Trigger a manual backtest."""
    return jsonify({"status": "started", "job_id": "manual_" + str(int(datetime.utcnow().timestamp()))})

@backtest_bp.route("/run-all", methods=["POST"])
def run_all_backtests():
    """Trigger backtests for all."""
    return jsonify({"status": "started", "job_id": "all_" + str(int(datetime.utcnow().timestamp()))})


@backtest_bp.route("/download-cache", methods=["POST"])
def download_cache():
    """Download OHLCV data for all active coins and timeframes to populate cache."""
    db = SessionLocal()
    try:
        from database.models import Coin, BacktestJob
        coins = db.query(Coin).filter_by(is_active=True).all()
        timeframes = ["5m", "15m", "1h", "2h", "4h", "1d"]
        
        if not coins:
            return jsonify({"error": "No active coins found"}), 400
            
        job_id = f"dl_job_{int(datetime.utcnow().timestamp())}"
        total_tests = len(coins) * len(timeframes)
        
        job = BacktestJob(
            id=job_id, status="running", strategy_id=None,
            total_tests=total_tests, completed=0,
            total_coins=len(coins), total_timeframes=len(timeframes),
            message="Initializing downloads..."
        )
        db.add(job)
        db.commit()
        
        coin_data = [{"id": c.id, "symbol": c.symbol} for c in coins]
        
        def _task(j_id, coins_list, tfs):
            thread_db = SessionLocal()
            completed = 0
            failed = 0
            try:
                from services.binance_service import get_ohlcv
                from concurrent.futures import ThreadPoolExecutor, as_completed
                from services.backtest_service import _get_limit_for_timeframe
                
                tasks = []
                for c_info in coins_list:
                    for tf in tfs:
                        tasks.append((c_info, tf))
                        
                def download_single(c_info, tf):
                    try:
                        import time
                        time.sleep(1) # Add 1 second delay to avoid rate limits
                        limit = _get_limit_for_timeframe(tf, 6) # 6 months
                        df = get_ohlcv(c_info["symbol"], timeframe=tf, limit=limit)
                        return df is not None
                    except Exception as e:
                        logger.warning(f"Download failed for {c_info['symbol']} {tf}: {e}")
                        return False

                # Reduced to 2 workers and added delays to prevent IP ban
                with ThreadPoolExecutor(max_workers=2) as executor:
                    future_to_task = {executor.submit(download_single, c_info, tf): (c_info, tf) for c_info, tf in tasks}
                    
                    for future in as_completed(future_to_task):
                        c_info, tf = future_to_task[future]
                        success = future.result()
                        completed += 1
                        if not success:
                            failed += 1
                            
                        # Update progress every 5 tests
                        if completed % 5 == 0 or completed == len(tasks):
                            j = thread_db.query(BacktestJob).filter_by(id=j_id).first()
                            if j:
                                j.completed = completed
                                j.message = f"Downloaded {c_info['symbol']} on {tf} ({completed}/{len(tasks)}). Failed: {failed}"
                                thread_db.commit()
                                
                j = thread_db.query(BacktestJob).filter_by(id=j_id).first()
                if j:
                    j.status = "complete"
                    j.completed = completed
                    j.message = f"Download complete! Success: {completed - failed}, Failed: {failed}"
                    thread_db.commit()
                    
            except Exception as e:
                logger.error(f"BACKGROUND DOWNLOAD FAILED: {e}")
                try:
                    j = thread_db.query(BacktestJob).filter_by(id=j_id).first()
                    if j:
                        j.status = "error"
                        j.message = str(e)
                        thread_db.commit()
                except Exception:
                    pass
            finally:
                thread_db.close()
                
        import threading
        threading.Thread(target=_task, args=(job_id, coin_data, timeframes)).start()
        return jsonify({"job_id": job_id, "status": "started", "total_tests": total_tests})
        
    except Exception as e:
        logger.exception(f"Error in download_cache: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
    finally:
        db.close()
