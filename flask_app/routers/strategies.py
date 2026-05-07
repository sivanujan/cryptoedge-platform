import logging
import types
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from database.connection import get_db
from database.models import Strategy

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/strategies", tags=["strategies"])


class StrategyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    pine_script: Optional[str] = None
    parameters: Optional[dict] = None


@router.get("")
def list_strategies(db: Session = Depends(get_db)):
    """Return all strategies in the library."""
    from sqlalchemy import func
    from database.models import BacktestResult, CoinStrategyMap

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
            "created_at": s.created_at.isoformat() if s.created_at else None,
        })
    return {"strategies": result}


@router.post("")
def create_strategy(body: StrategyCreate, db: Session = Depends(get_db)):
    """Add a new strategy to the library."""
    existing = db.query(Strategy).filter_by(name=body.name).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Strategy with this name already exists",
                "existing_id": existing.id,
                "existing_name": existing.name,
                "is_active": existing.is_active
            }
        )

    desc = body.description.strip() if body.description else None

    strategy = Strategy(
        name=body.name,
        description=desc if desc else None,
        pine_script=body.pine_script,
        parameters=body.parameters or {},
        is_active=True,
    )
    db.add(strategy)
    db.commit()
    db.refresh(strategy)
    return {"id": strategy.id, "name": strategy.name}


@router.post("/{strategy_id}/convert-pine")
def convert_pine_script(strategy_id: int, db: Session = Depends(get_db)):
    """
    Convert the strategy's Pine Script to Python using AI (Gemma 3 27B via OpenRouter).
    Saves the Python code to the DB and registers the strategy class dynamically.
    """
    from services.ai_service import convert_pine_to_python, validate_strategy_code
    from strategies.golden_cross import STRATEGY_REGISTRY

    strategy = db.query(Strategy).filter_by(id=strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    if not strategy.pine_script:
        raise HTTPException(status_code=400, detail="This strategy has no Pine Script to convert")

    # Call AI to convert
    try:
        python_code = convert_pine_to_python(strategy.pine_script, strategy.name)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Validate the generated code
    is_valid, err = validate_strategy_code(python_code)
    if not is_valid:
        logger.error(f"Generated code failed validation: {err}\n\nCode:\n{python_code}")
        raise HTTPException(status_code=422, detail=f"AI generated invalid code: {err}")

    # Dynamically load the generated Python class
    try:
        from strategies.base_strategy import BaseStrategy
        import pandas as pd
        import numpy as np

        namespace = {
            "BaseStrategy": BaseStrategy,
            "pd": pd,
            "np": np,
            "__builtins__": globals()["__builtins__"] # Provide access to built-in functions
        }
        
        # We need to replace 'strategies.base' in the code if it still says that out of habit
        python_code = python_code.replace("from strategies.base import BaseStrategy", "from strategies.base_strategy import BaseStrategy")
        
        exec(python_code, namespace)
        strategy_class = namespace.get("_STRATEGY_CLASS")
        if not strategy_class:
            raise ValueError("_STRATEGY_CLASS not found in generated code")
        
        # Register it so backtest engine can find it by name
        STRATEGY_REGISTRY[strategy.name] = strategy_class
        logger.info(f"Dynamically registered strategy: '{strategy.name}'")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load generated code: {e}")

    # Save to DB
    strategy.python_code = python_code
    db.commit()

    return {
        "status": "success",
        "strategy_id": strategy_id,
        "strategy_name": strategy.name,
        "message": "Pine Script converted and strategy registered. You can now run a backtest!",
    }


@router.get("/{strategy_id}/python-code")
def get_python_code(strategy_id: int, db: Session = Depends(get_db)):
    """Return the generated Python code for a strategy (for inspection)."""
    strategy = db.query(Strategy).filter_by(id=strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return {
        "strategy_id": strategy_id,
        "name": strategy.name,
        "python_code": strategy.python_code or "",
        "has_code": bool(strategy.python_code),
    }


@router.get("/{strategy_id}/coins")
def strategy_coins(strategy_id: int, db: Session = Depends(get_db)):
    """Return which coins use this strategy."""
    from database.models import CoinStrategyMap
    mappings = db.query(CoinStrategyMap).filter_by(strategy_id=strategy_id, is_active=True).all()
    return {
        "coins": [
            {
                "symbol": m.coin.symbol,
                "timeframe": m.timeframe,
                "win_rate": m.win_rate,
            }
            for m in mappings
            if m.coin
        ]
    }


@router.post("/{strategy_id}/reactivate")
def reactivate_strategy(strategy_id: int, db: Session = Depends(get_db)):
    """Reactivate an inactive strategy."""
    strategy = db.query(Strategy).filter_by(id=strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    strategy.is_active = True
    db.commit()
    return {"status": "success", "id": strategy.id, "name": strategy.name}


@router.get("/all")
def list_all_strategies(db: Session = Depends(get_db)):
    """Return all strategies including inactive ones (for admin/debug)."""
    strategies = db.query(Strategy).all()
    return {
        "strategies": [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description,
                "is_active": s.is_active,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in strategies
        ]
    }


@router.delete("/{strategy_id}")
def delete_strategy(strategy_id: int, db: Session = Depends(get_db)):
    """Permanent delete of a strategy and all its associated data (signals, trades, results)."""
    from database.models import Signal, Trade, BacktestResult, CoinStrategyMap
    
    strategy = db.query(Strategy).filter_by(id=strategy_id).first()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    
    # 1. Get all signals for this strategy to find associated trades
    signals = db.query(Signal).filter_by(strategy_id=strategy_id).all()
    signal_ids = [s.id for s in signals]
    
    # 2. Delete trades associated with those signals
    if signal_ids:
        db.query(Trade).filter(Trade.signal_id.in_(signal_ids)).delete(synchronize_session=False)
    
    # 3. Delete signals
    db.query(Signal).filter_by(strategy_id=strategy_id).delete(synchronize_session=False)
    
    # 4. Delete backtest results
    db.query(BacktestResult).filter_by(strategy_id=strategy_id).delete(synchronize_session=False)
    
    # 5. Delete coin maps
    db.query(CoinStrategyMap).filter_by(strategy_id=strategy_id).delete(synchronize_session=False)
    
    # 6. Delete the strategy itself (Hard delete)
    db.delete(strategy)
    
    db.commit()
    logger.info(f"Deleted strategy {strategy_id} and all cascaded data.")
    return {"status": "success", "message": "Strategy and all associated data deleted permanentely"}

