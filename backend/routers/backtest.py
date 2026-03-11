import logging
import uuid
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel

from database.connection import get_db
from database.models import BacktestResult, Coin, Strategy, CoinStrategyMap, BacktestJob
from services.backtest_service import run_backtest, assign_best_strategies, TIMEFRAMES

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])

# Keep small in-memory cache for very recent jobs (fast path)
_jobs: dict = {}


class BacktestRunRequest(BaseModel):
    symbol: str
    strategy_name: str
    timeframe: str = "1h"
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None

class BulkAssignItem(BaseModel):
    coin_id: int
    strategy_id: int
    timeframe: str

class BulkAssignRequest(BaseModel):
    assignments: list[BulkAssignItem]


@router.get("/results")
def backtest_results(
    strategy: Optional[str] = Query(None),
    timeframe: Optional[str] = Query(None),
    min_win_rate: Optional[float] = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Return all backtest results with optional filters."""
    query = (
        db.query(BacktestResult)
        .options(joinedload(BacktestResult.coin), joinedload(BacktestResult.strategy))
        .join(Coin)
        .join(Strategy)
        .filter(BacktestResult.win_rate.isnot(None))
    )
    if strategy:
        query = query.filter(Strategy.name.ilike(f"%{strategy}%"))
    if timeframe:
        query = query.filter(BacktestResult.timeframe == timeframe)
    if min_win_rate is not None:
        query = query.filter(BacktestResult.win_rate >= min_win_rate)

    total = query.count()
    results = query.order_by(BacktestResult.win_rate.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "results": [
            {
                "id": r.id,
                "symbol": r.coin.symbol if r.coin else "",
                "strategy": r.strategy.name if r.strategy else "",
                "timeframe": r.timeframe,
                "win_rate": r.win_rate,
                "total_trades": r.total_trades,
                "total_return": r.total_return,
                "max_drawdown": r.max_drawdown,
                "sharpe_ratio": r.sharpe_ratio,
                "profit_factor": r.profit_factor,
                "tested_from": r.tested_from.isoformat() if r.tested_from else None,
                "tested_to": r.tested_to.isoformat() if r.tested_to else None,
            }
            for r in results
        ],
    }


@router.post("/run")
def run_single_backtest(body: BacktestRunRequest, db: Session = Depends(get_db)):
    """Run backtest for a single coin + strategy + timeframe."""
    coin = db.query(Coin).filter_by(symbol=body.symbol).first()
    if not coin:
        raise HTTPException(status_code=404, detail=f"Coin {body.symbol} not in database. Run /coins/sync first.")

    strategy = db.query(Strategy).filter_by(name=body.strategy_name).first()
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy {body.strategy_name} not found.")

    result = run_backtest(
        symbol=body.symbol,
        strategy_name=body.strategy_name,
        timeframe=body.timeframe,
        db=db,
        coin_id=coin.id,
        strategy_id=strategy.id,
    )
    return result


@router.post("/run-all")
def run_all_backtests(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Trigger full backtest for all coins × all strategies × all timeframes as background job."""
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {"progress": 0, "status": "running", "started_at": datetime.utcnow().isoformat()}

    def _run_all():
        try:
            coins = db.query(Coin).filter_by(is_active=True).all()
            strategies = db.query(Strategy).filter_by(is_active=True).all()
            total = len(coins) * len(strategies) * len(TIMEFRAMES)
            done = 0
            for coin in coins:
                for strategy in strategies:
                    for tf in TIMEFRAMES:
                        try:
                            run_backtest(
                                symbol=coin.symbol,
                                strategy_name=strategy.name,
                                timeframe=tf,
                                db=db,
                                coin_id=coin.id,
                                strategy_id=strategy.id,
                            )
                        except Exception:
                            pass
                        done += 1
                        _jobs[job_id]["progress"] = round(done / total * 100, 1)
            assign_best_strategies(db)
            _jobs[job_id]["status"] = "completed"
            _jobs[job_id]["progress"] = 100
        except Exception as e:
            _jobs[job_id]["status"] = "failed"
            _jobs[job_id]["error"] = str(e)

    background_tasks.add_task(_run_all)
    return {"job_id": job_id, "status": "started"}


class RunStrategyRequest(BaseModel):
    timeframes: Optional[list[str]] = ["5m", "15m", "1h", "2h", "4h", "1d"]
    candle_limit: Optional[int] = 1000
    coin_limit: Optional[str] = "all"


@router.post("/run-strategy/{strategy_id}")
def run_strategy_backtest(
    strategy_id: int, 
    body: Optional[RunStrategyRequest] = None, 
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    """Run backtest for a specific strategy on all active coins across multiple timeframes."""
    strategy = db.query(Strategy).filter_by(id=strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
        
    req = body or RunStrategyRequest()
    if req.coin_limit == "all":
        coins = db.query(Coin).filter_by(is_active=True).all()
    else:
        try:
            limit = int(req.coin_limit)
            coins = db.query(Coin).filter_by(is_active=True).limit(limit).all()
        except ValueError:
            coins = db.query(Coin).filter_by(is_active=True).limit(20).all()

    job_id = f"job_strat_{strategy.id}_{datetime.utcnow().timestamp()}"
    
    # Persist initial job state to DB (survives restarts + works across workers)
    job_row = BacktestJob(
        id=job_id,
        status="running",
        strategy_id=strategy.id,
        total_coins=len(coins),
        total_timeframes=len(req.timeframes),
        total_tests=len(coins) * len(req.timeframes),
        completed=0,
        message="Starting backtest..."
    )
    db.add(job_row)
    db.commit()
    # Also cache in-memory for fast in-process access
    _jobs[job_id] = job_id  # marker so we know it exists

    # Snapshot data needed by the background task
    coin_list = [(c.id, c.symbol) for c in coins]
    strategy_id_val = strategy.id
    strategy_name_val = strategy.name
    timeframes_val = list(req.timeframes)

    def _run_batch():
        import time
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from database.connection import SessionLocal
        from services.backtest_service import assign_best_strategies

        logger.info(f"[Backtest] Started job {job_id} for strategy '{strategy_name_val}' | {len(coin_list)} coins x {len(timeframes_val)} timeframes")

        def _update_job(db_s, **kwargs):
            """Atomic update to the job row."""
            try:
                row = db_s.query(BacktestJob).filter_by(id=job_id).first()
                if row:
                    for k, v in kwargs.items():
                        setattr(row, k, v)
                    db_s.commit()
            except Exception as upd_err:
                logger.warning(f"Job update failed: {upd_err}")
                db_s.rollback()

        best_wr = 0.0
        coins_above_65 = set()
        completed_count = 0

        try:
            for index, (coin_id_val, coin_symbol) in enumerate(coin_list):
                _upd_db = SessionLocal()
                try:
                    _update_job(_upd_db, current_coin=coin_symbol,
                                message=f"Testing {coin_symbol} ({index+1}/{len(coin_list)})...")
                finally:
                    _upd_db.close()

                logger.info(f"[Backtest] Coin {index+1}/{len(coin_list)}: {coin_symbol}")

                def _run_one(tf, _sym=coin_symbol, _cid=coin_id_val, _sid=strategy_id_val, _sname=strategy_name_val):
                    db_s = SessionLocal()
                    try:
                        res = run_backtest(
                            symbol=_sym, strategy_name=_sname, timeframe=tf,
                            db=db_s, coin_id=_cid, strategy_id=_sid,
                        )
                        return tf, res
                    except Exception as e:
                        logger.warning(f"[Backtest] FAILED {_sym} {tf}: {e}")
                        return tf, None
                    finally:
                        db_s.close()

                with ThreadPoolExecutor(max_workers=max(len(timeframes_val), 1)) as ex:
                    futures = {ex.submit(_run_one, tf): tf for tf in timeframes_val}
                    for future in as_completed(futures):
                        tf, res = future.result()
                        completed_count += 1
                        updates = {"completed": completed_count}
                        if res:
                            wr = res.get("win_rate")
                            if wr is not None:
                                logger.info(f"[Backtest] {coin_symbol} {tf} | win_rate={wr}%")
                                if wr > best_wr:
                                    best_wr = wr
                                    updates["best_win_rate"] = best_wr
                                    updates["best_coin"] = f"{coin_symbol} ({wr}% on {tf})"
                                if wr >= 65.0:
                                    coins_above_65.add(coin_symbol)
                                    updates["coins_above_65"] = len(coins_above_65)
                        _upd_db2 = SessionLocal()
                        try:
                            _update_job(_upd_db2, **updates)
                        finally:
                            _upd_db2.close()

                time.sleep(0.15)

            logger.info(f"[Backtest] Finished testing. Assigning best strategies...")
            db_final = SessionLocal()
            try:
                assign_best_strategies(db_final)
                _update_job(db_final, status="complete", message="Backtest run complete.",
                            current_coin="", current_tf="")
            finally:
                db_final.close()
            logger.info(f"[Backtest] Job {job_id} complete!")

        except Exception as e:
            logger.error(f"[Backtest] Job {job_id} crashed: {e}", exc_info=True)
            db_err = SessionLocal()
            try:
                _update_job(db_err, status="error", message=str(e))
            finally:
                db_err.close()

    background_tasks.add_task(_run_batch)
    return {"job_id": job_id, "status": "started"}


@router.get("/progress/{job_id}")
def backtest_progress(job_id: str, db: Session = Depends(get_db)):
    """Return progress of a running backtest job (reads from DB — works across restarts and workers)."""
    row = db.query(BacktestJob).filter_by(id=job_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "status": row.status,
        "total_coins": row.total_coins,
        "total_timeframes": row.total_timeframes,
        "total_tests": row.total_tests,
        "completed": row.completed,
        "best_coin": row.best_coin,
        "best_win_rate": row.best_win_rate,
        "coins_above_65": row.coins_above_65,
        "current_coin": row.current_coin,
        "current_tf": row.current_tf,
        "message": row.message,
    }


@router.get("/results/table")
def backtest_results_table(
    strategy_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Return all backtest results grouped by coin, containing all timeframes.
    Shows ALL results including 0-trade ones so users can see coverage.
    """
    query = (
        db.query(BacktestResult)
        .options(joinedload(BacktestResult.coin), joinedload(BacktestResult.strategy))
    )
    if strategy_id:
        query = query.filter(BacktestResult.strategy_id == strategy_id)

    results = query.all()

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

        # Add timeframe data (include even if win_rate is None / error rows)
        grouped[key]["results"][r.timeframe] = {
            "win_rate": r.win_rate,
            "trades": r.total_trades,
            "return_pct": r.total_return,
            "drawdown": r.max_drawdown,
            "error": r.error,
        }

        # Track best timeframe (only from rows that have a win_rate)
        if r.win_rate is not None:
            if grouped[key]["best_win_rate"] is None or r.win_rate > grouped[key]["best_win_rate"]:
                grouped[key]["best_win_rate"] = r.win_rate
                grouped[key]["best_timeframe"] = r.timeframe

    # Convert to list — sort by best win rate descending (None = 0 coins tested = goes to bottom)
    table_data = list(grouped.values())
    table_data.sort(key=lambda x: x["best_win_rate"] if x["best_win_rate"] is not None else -1.0, reverse=True)

    return table_data



@router.get("/summary/{strategy_id}")
def backtest_summary(strategy_id: int, db: Session = Depends(get_db)):
    """Return top-level summary statistics for a given strategy."""
    from sqlalchemy import func
    
    results = db.query(BacktestResult).filter(
        BacktestResult.strategy_id == strategy_id,
        BacktestResult.win_rate.isnot(None)
    ).all()
    
    if not results:
        return {
            "total_coins_tested": 0,
            "coins_above_65": 0,
            "coins_above_55": 0,
            "best_coin": None,
            "best_win_rate": 0,
            "best_timeframe_overall": None,
            "avg_win_rate_by_timeframe": {},
            "last_run": None
        }

    # Group by timeframe to calculate averages
    tf_stats = {}
    best_overall_wr = -1.0
    best_overall_coin = None
    best_overall_tf = None
    
    # We want unique coins tested
    coins_tested = set()
    coins_above_65 = set()
    coins_above_55 = set()
    
    for r in results:
        coins_tested.add(r.coin_id)
        
        if r.timeframe not in tf_stats:
            tf_stats[r.timeframe] = {"sum": 0, "count": 0}
            
        tf_stats[r.timeframe]["sum"] += r.win_rate
        tf_stats[r.timeframe]["count"] += 1
        
        if r.win_rate >= 65.0:
            coins_above_65.add(r.coin_id)
        if r.win_rate >= 55.0:
            coins_above_55.add(r.coin_id)
            
        if r.win_rate > best_overall_wr:
            best_overall_wr = r.win_rate
            best_overall_tf = r.timeframe
            best_overall_coin = r.coin.symbol if r.coin else None

    # Calculate TF averages
    avg_by_tf = {}
    for tf, data in tf_stats.items():
        avg_by_tf[tf] = round(data["sum"] / data["count"], 1)
        
    # Find best TF overall (TF with highest average)
    best_tf_overall = None
    best_tf_avg = -1.0
    for tf, avg in avg_by_tf.items():
        if avg > best_tf_avg:
            best_tf_avg = avg
            best_tf_overall = tf

    return {
        "total_coins_tested": len(coins_tested),
        "coins_above_65": len(coins_above_65),
        "coins_above_55": len(coins_above_55),
        "best_coin": best_overall_coin,
        "best_win_rate": best_overall_wr,
        "best_timeframe_overall": best_tf_overall,
        "avg_win_rate_by_timeframe": avg_by_tf,
        "last_run": results[0].created_at.isoformat() if results[0].created_at else None
    }


@router.post("/assign-bulk")
def assign_bulk_strategies(request: BulkAssignRequest, db: Session = Depends(get_db)):
    """
    Bulk assign specific coins to a strategy & timeframe from the screener.
    Updates or inserts rows into coin_strategy_map.
    """
    updated_count = 0
    for item in request.assignments:
        existing = db.query(CoinStrategyMap).filter_by(
            coin_id=item.coin_id, 
            strategy_id=item.strategy_id, 
            timeframe=item.timeframe
        ).first()
        if not existing:
            new_map = CoinStrategyMap(
                coin_id=item.coin_id,
                strategy_id=item.strategy_id,
                timeframe=item.timeframe
            )
            db.add(new_map)
            updated_count += 1
        
    db.commit()
    return {"status": "success", "message": f"Successfully assigned {updated_count} coins."}
