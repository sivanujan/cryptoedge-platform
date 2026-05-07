import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from database.models import BacktestResult, CoinStrategyMap, Coin, Strategy
from services.binance_service import get_ohlcv
from services.indicator_service import add_all_indicators
from strategies.golden_cross import STRATEGY_REGISTRY, get_strategy

logger = logging.getLogger(__name__)

TIMEFRAMES = ["1h", "4h", "1d"]
BACKTEST_MONTHS = 6


def _get_or_load_strategy(strategy_name: str, strategy_id: int, db: Session):
    """
    Get a strategy by name. If not in the in-memory registry (e.g. after a restart),
    try to load it from the python_code column in the database.
    """
    # 1. Check in-memory registry first (fast path)
    cls = STRATEGY_REGISTRY.get(strategy_name)
    if cls:
        return cls()

    # 2. Slow path: load python_code from DB
    from strategies.base_strategy import BaseStrategy
    import numpy as np
    import pandas as pd

    strategy_row = db.query(Strategy).filter_by(id=strategy_id).first()
    if strategy_row and strategy_row.python_code:
        python_code = strategy_row.python_code
        # Fix any legacy base import path
        python_code = python_code.replace("from strategies.base import BaseStrategy", "from strategies.base_strategy import BaseStrategy")
        namespace = {
            "BaseStrategy": BaseStrategy,
            "pd": pd,
            "np": np,
            "__builtins__": __builtins__,
        }
        try:
            exec(python_code, namespace)
            dyn_cls = namespace.get("_STRATEGY_CLASS")
            if dyn_cls:
                instance = dyn_cls()
                # Validate: check if it actually generates buy/sell signals on synthetic data
                if not _validate_strategy_signals(instance):
                    logger.warning(f"Strategy '{strategy_name}' generates only 0 signals — auto-patching with EMA fallback")
                    # Auto-patch the DB entry so next load gets working code
                    fallback_code = _FALLBACK_CODE_TEMPLATE.format(name=strategy_name)
                    strategy_row.python_code = fallback_code
                    try:
                        db.commit()
                    except Exception:
                        db.rollback()
                    # Load the fallback
                    fb_ns = {"BaseStrategy": BaseStrategy, "pd": pd, "np": np, "__builtins__": __builtins__}
                    exec(fallback_code, fb_ns)
                    dyn_cls = fb_ns.get("_STRATEGY_CLASS")
                    instance = dyn_cls()
                # Register for next time so we don't reload from DB again
                STRATEGY_REGISTRY[strategy_name] = dyn_cls
                logger.info(f"Dynamically re-loaded strategy '{strategy_name}' from DB")
                return instance
        except Exception as e:
            raise ValueError(f"Failed to load '{strategy_name}' from stored code: {e}")

    # 3. Final fallback: raise descriptive error
    raise ValueError(f"Strategy '{strategy_name}' not found. Available: {list(STRATEGY_REGISTRY.keys())}")


_FALLBACK_CODE_TEMPLATE = '''
import pandas as pd
import numpy as np
from strategies.base_strategy import BaseStrategy

class FallbackStrategy(BaseStrategy):
    name = "{name}"
    description = "Auto-fixed EMA/RSI crossover strategy."
    default_params = {{"maxDrawdownPct": 3.0}}

    def generate_signals(self, df):
        df = df.copy()
        df["signal"] = 0
        df["confidence"] = 50.0
        ema_fast = df["ema_21"]
        ema_slow = df["ema_50"]
        ema_trend = df["ema_200"]
        rsi = df["rsi_14"]
        close = df["close"]
        cross_above = (ema_fast > ema_slow) & (ema_fast.shift(1) <= ema_slow.shift(1))
        cross_below = (ema_fast < ema_slow) & (ema_fast.shift(1) >= ema_slow.shift(1))
        buy  = cross_above & (close > ema_trend) & (rsi > 40) & (rsi < 75)
        sell = cross_below & (close < ema_trend) & (rsi < 60) & (rsi > 25)
        df.loc[buy,  "signal"] = 1
        df.loc[sell, "signal"] = -1
        df.loc[buy,  "confidence"] = 70.0
        df.loc[sell, "confidence"] = 70.0
        return df

_STRATEGY_CLASS = FallbackStrategy
'''


def _validate_strategy_signals(instance) -> bool:
    """Quick check: does the strategy generate any non-zero signals on synthetic data?"""
    try:
        n = 120
        rng = np.random.default_rng(42)
        base = rng.uniform(100, 110, n)
        ema21 = pd.Series(base + rng.uniform(-2, 2, n))
        ema50 = pd.Series(base + rng.uniform(-4, 4, n))
        test_df = pd.DataFrame({
            'open': base, 'high': base+1, 'low': base-1, 'close': base,
            'volume': rng.uniform(1000, 5000, n),
            'ema_21': ema21, 'ema_50': ema50, 'ema_200': base + rng.uniform(-10, 10, n),
            'rsi_14': rng.uniform(20, 80, n), 'macd': rng.uniform(-1, 1, n),
            'macd_signal': rng.uniform(-1, 1, n), 'macd_hist': rng.uniform(-0.5, 0.5, n),
            'bb_upper': base+3, 'bb_mid': base, 'bb_lower': base-3, 'bb_width': np.full(n, 6.0),
            'atr_14': np.full(n, 1.5), 'volume_sma': np.full(n, 3000.0), 'volume_ratio': np.full(n, 1.0),
        })
        out = instance.generate_signals(test_df)
        counts = out['signal'].value_counts().to_dict()
        return (counts.get(1, 0) + counts.get(-1, 0)) > 0
    except Exception:
        return False


def run_backtest(
    symbol: str,
    strategy_name: str,
    timeframe: str,
    db: Session,
    coin_id: int,
    strategy_id: int,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Run a backtest for a single coin+strategy+timeframe combination.
    Returns dict with performance metrics and saves to DB.
    """
    result = {
        "symbol": symbol,
        "strategy": strategy_name,
        "timeframe": timeframe,
        "win_rate": None,
        "total_trades": 0,
        "total_return": None,
        "max_drawdown": None,
        "sharpe_ratio": None,
        "profit_factor": None,
        "error": None,
    }

    try:
        # Fetch historical data
        limit = _get_limit_for_timeframe(timeframe, BACKTEST_MONTHS)
        df = get_ohlcv(symbol, timeframe, limit=limit)

        if df is None or len(df) < 100:
            raise ValueError(f"Insufficient data for {symbol} [{timeframe}]")

        # Add indicators
        df = add_all_indicators(df)
        df = df.dropna()

        if len(df) < 50:
            raise ValueError("Not enough data after indicator calculation")

        # Generate signals — auto-load strategy from DB if not in registry
        strategy = _get_or_load_strategy(strategy_name, strategy_id, db)
        # Reset index so AI-generated strategies can safely use integer-based iloc/loc[0] indexing
        df = df.reset_index(drop=True)
        df = strategy.generate_signals(df)

        # Simple backtest simulation (vectorised)
        metrics = _simulate_trades(df, strategy)
        
        # Current Volatility (ATR-based)
        last_volatility = float(df["volatility_atr"].iloc[-1]) if "volatility_atr" in df.columns else None
        metrics["volatility"] = round(last_volatility, 2) if last_volatility is not None else None

        result.update(metrics)
        tested_from = df.index[0].to_pydatetime() if hasattr(df.index[0], "to_pydatetime") else datetime.utcnow()
        tested_to = df.index[-1].to_pydatetime() if hasattr(df.index[-1], "to_pydatetime") else datetime.utcnow()

        # Save to DB
        _save_backtest_result(
            db=db,
            coin_id=coin_id,
            strategy_id=strategy_id,
            timeframe=timeframe,
            metrics=metrics,
            tested_from=tested_from,
            tested_to=tested_to,
        )

    except Exception as e:
        result["error"] = str(e)
        logger.warning(f"Backtest failed: {symbol} {strategy_name} {timeframe}: {e}")
        _save_backtest_result(
            db=db,
            coin_id=coin_id,
            strategy_id=strategy_id,
            timeframe=timeframe,
            metrics={},
            tested_from=datetime.utcnow(),
            tested_to=datetime.utcnow(),
            error=str(e),
        )

    return result


def _simulate_trades(df: pd.DataFrame, strategy) -> Dict[str, Any]:
    """Simulate entry/exit trades from signal column and calculate metrics."""
    closes = df["close"].values
    signals = df["signal"].values
    n = len(closes)

    trades = []
    in_trade = False
    entry_price = 0.0
    sl = 0.0

    for i in range(1, n):
        if not in_trade and signals[i - 1] == 1:
            in_trade = True
            entry_price = closes[i]
            sl = strategy.calculate_stop_loss(entry_price)
        elif in_trade:
            current = closes[i]
            hit_sl = current <= sl
            has_exit = signals[i - 1] == -1
            if hit_sl or has_exit or i == n - 1:
                pnl_pct = (current - entry_price) / entry_price * 100
                trades.append(pnl_pct)
                in_trade = False

    if not trades:
        return {
            "win_rate": 0.0,
            "total_trades": 0,
            "total_return": 0.0,
            "max_drawdown": 0.0,
            "sharpe_ratio": 0.0,
            "profit_factor": 0.0,
        }

    trades_arr = np.array(trades)
    wins = trades_arr[trades_arr > 0]
    losses = trades_arr[trades_arr <= 0]
    win_rate = len(wins) / len(trades_arr) * 100
    total_return = float(trades_arr.sum())
    max_drawdown = float(trades_arr.min()) if len(losses) > 0 else 0.0

    # Sharpe (annualised approximation using trade returns)
    if trades_arr.std() > 0:
        sharpe = (trades_arr.mean() / trades_arr.std()) * np.sqrt(252)
    else:
        sharpe = 0.0

    gross_profit = wins.sum() if len(wins) > 0 else 0.0
    gross_loss = abs(losses.sum()) if len(losses) > 0 else 1.0
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

    return {
        "win_rate": round(win_rate, 2),
        "total_trades": len(trades),
        "total_return": round(total_return, 2),
        "max_drawdown": round(max_drawdown, 2),
        "sharpe_ratio": round(float(sharpe), 3),
        "profit_factor": round(float(profit_factor), 3),
    }


def _get_limit_for_timeframe(timeframe: str, months: int) -> int:
    # We need enough data for indicators (EMA 200) + the backtest period.
    # Binance usually allows up to 1000 candles per fetch.
    mapping = {"1m": 1500, "5m": 1500, "15m": 1500, "1h": 1000, "4h": 500, "1d": 500}
    limit = mapping.get(timeframe, 1000)
    
    # Ensure 1d has enough for 6 months (approx 180 days) + EMA 200 buffer
    if timeframe == "1d":
        return 500 
    if timeframe == "4h":
        return 700
        
    return limit


def _save_backtest_result(
    db: Session,
    coin_id: int,
    strategy_id: int,
    timeframe: str,
    metrics: dict,
    tested_from: datetime,
    tested_to: datetime,
    error: str = None,
):
    # Delete old result for same coin/strategy/timeframe
    existing = (
        db.query(BacktestResult)
        .filter_by(coin_id=coin_id, strategy_id=strategy_id, timeframe=timeframe)
        .first()
    )
    if existing:
        db.delete(existing)

    result = BacktestResult(
        coin_id=coin_id,
        strategy_id=strategy_id,
        timeframe=timeframe,
        win_rate=metrics.get("win_rate"),
        total_trades=metrics.get("total_trades"),
        total_return=metrics.get("total_return"),
        max_drawdown=metrics.get("max_drawdown"),
        sharpe_ratio=metrics.get("sharpe_ratio"),
        profit_factor=metrics.get("profit_factor"),
        volatility=metrics.get("volatility"),
        tested_from=tested_from,
        tested_to=tested_to,
        error=error,
    )
    db.add(result)
    db.commit()


def assign_best_strategies(db: Session):
    """
    For each coin, find the best performing strategy+timeframe
    using a Weighted Win Rate (WWR) to favor statistical significance.
    WWR = WinRate * min(trades, 10) / 10
    """
    coins = db.query(Coin).filter_by(is_active=True).all()
    for coin in coins:
        results = (
            db.query(BacktestResult)
            .filter(BacktestResult.coin_id == coin.id, BacktestResult.win_rate.isnot(None))
            .all()
        )
        
        if not results:
            continue
            
        # Select best using Weighted Win Rate
        best = None
        best_score = -1.0
        
        for r in results:
            trades = r.total_trades or 0
            weight = min(trades, 10) / 10.0
            score = r.win_rate * weight
            
            if score > best_score:
                best_score = score
                best = r
                
        if best:
            existing = (
                db.query(CoinStrategyMap).filter_by(coin_id=coin.id).first()
            )
            if existing:
                existing.strategy_id = best.strategy_id
                existing.timeframe = best.timeframe
                existing.win_rate = best.win_rate
                existing.assigned_at = datetime.utcnow()
            else:
                mapping = CoinStrategyMap(
                    coin_id=coin.id,
                    strategy_id=best.strategy_id,
                    timeframe=best.timeframe,
                    win_rate=best.win_rate,
                )
                db.add(mapping)
    db.commit()
    logger.info("Best strategies assigned to all coins using weighted scoring.")
