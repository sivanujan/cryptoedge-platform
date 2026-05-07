"""
scanner_router.py — FastAPI router for the Breakout Scanner.
Endpoints:
  POST /scanner/run            → manually trigger scanner
  GET  /scanner/signals        → list signals with filters
  GET  /scanner/signals/{id}   → single signal
  PATCH /scanner/signals/{id}/status → update status
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.connection import get_db
from database.scanner_models import BreakoutSignal, ScannerRun

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/scanner", tags=["Breakout Scanner"])


# ─────────────────────────────────────────────
#  Pydantic Schemas
# ─────────────────────────────────────────────

class StatusUpdateRequest(BaseModel):
    status: str  # ACTIVE | TP1_HIT | TP2_HIT | SL_HIT | EXPIRED


VALID_STATUSES = {"ACTIVE", "TP1_HIT", "TP2_HIT", "SL_HIT", "EXPIRED"}


def _signal_to_dict(s: BreakoutSignal) -> dict:
    """Convert a BreakoutSignal ORM row to a JSON-serializable dict."""
    return {
        "id": s.id,
        "symbol": s.symbol,
        "direction": s.direction,
        "entry_price": float(s.entry_price),
        "stop_loss": float(s.stop_loss),
        "take_profit_1": float(s.take_profit_1),
        "take_profit_2": float(s.take_profit_2),
        "atr": float(s.atr) if s.atr is not None else None,
        "rsi": float(s.rsi) if s.rsi is not None else None,
        "volume_ratio": float(s.volume_ratio) if s.volume_ratio is not None else None,
        "rs_vs_btc": float(s.rs_vs_btc) if s.rs_vs_btc is not None else None,
        "vwap": float(s.vwap) if s.vwap is not None else None,
        "signal_score": s.signal_score,
        "status": s.status,
        "created_at": s.created_at.isoformat() + "Z" if s.created_at else None,
        # TradingView link
        "tv_url": f"https://www.tradingview.com/chart/?symbol=BINANCE:{s.symbol}.P",
    }


# ─────────────────────────────────────────────
#  Endpoints
# ─────────────────────────────────────────────

@router.post("/run")
async def trigger_scanner(background_tasks: BackgroundTasks):
    """Manually trigger the breakout scanner. Runs in background."""
    from scanner.breakout_scanner import run_breakout_scanner
    background_tasks.add_task(_run_scanner_sync)
    return {
        "status": "started",
        "message": "Breakout scanner triggered in background. Results will be saved to DB.",
    }


def _run_scanner_sync():
    """Wrapper to run async scanner from a sync BackgroundTask."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If called from a running loop context, create a new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, _do_scan())
                future.result()
        else:
            loop.run_until_complete(_do_scan())
    except RuntimeError:
        asyncio.run(_do_scan())


async def _do_scan():
    from scanner.breakout_scanner import run_breakout_scanner
    return await run_breakout_scanner()


@router.get("/signals")
def list_signals(
    status: Optional[str] = Query(None, description="Filter by status: ACTIVE, TP1_HIT, TP2_HIT, SL_HIT, EXPIRED"),
    direction: Optional[str] = Query(None, description="Filter by direction: LONG or SHORT"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Return paginated breakout signals with optional filters."""
    query = db.query(BreakoutSignal)

    if status:
        query = query.filter(BreakoutSignal.status == status.upper())
    if direction:
        query = query.filter(BreakoutSignal.direction == direction.upper())

    total = query.count()
    signals = (
        query
        .order_by(BreakoutSignal.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Recent scanner run info
    last_run = db.query(ScannerRun).order_by(ScannerRun.run_at.desc()).first()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "signals": [_signal_to_dict(s) for s in signals],
        "last_run": {
            "run_at": last_run.run_at.isoformat() + "Z" if last_run else None,
            "total_scanned": last_run.total_scanned if last_run else 0,
            "signals_generated": last_run.signals_generated if last_run else 0,
        } if last_run else None,
    }


@router.get("/signals/{signal_id}")
def get_signal(signal_id: int, db: Session = Depends(get_db)):
    """Return a single breakout signal by ID."""
    signal = db.query(BreakoutSignal).filter_by(id=signal_id).first()
    if not signal:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")
    return _signal_to_dict(signal)


@router.patch("/signals/{signal_id}/status")
def update_signal_status(
    signal_id: int,
    body: StatusUpdateRequest,
    db: Session = Depends(get_db),
):
    """Manually update the status of a breakout signal."""
    new_status = body.status.upper()
    if new_status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{new_status}'. Must be one of: {', '.join(VALID_STATUSES)}",
        )

    signal = db.query(BreakoutSignal).filter_by(id=signal_id).first()
    if not signal:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")

    signal.status = new_status
    db.commit()
    return {"ok": True, "signal_id": signal_id, "new_status": new_status}


@router.get("/stats")
def get_scanner_stats(db: Session = Depends(get_db)):
    """Quick stats for the scanner dashboard widget."""
    total = db.query(BreakoutSignal).count()
    active = db.query(BreakoutSignal).filter_by(status="ACTIVE").count()
    tp1_hit = db.query(BreakoutSignal).filter_by(status="TP1_HIT").count()
    tp2_hit = db.query(BreakoutSignal).filter_by(status="TP2_HIT").count()
    sl_hit = db.query(BreakoutSignal).filter_by(status="SL_HIT").count()

    win = tp1_hit + tp2_hit
    loss = sl_hit
    win_rate = round(win / (win + loss) * 100, 1) if (win + loss) > 0 else 0

    last_run = db.query(ScannerRun).order_by(ScannerRun.run_at.desc()).first()

    return {
        "total_signals": total,
        "active": active,
        "tp1_hit": tp1_hit,
        "tp2_hit": tp2_hit,
        "sl_hit": sl_hit,
        "win_rate": win_rate,
        "last_run_at": last_run.run_at.isoformat() + "Z" if last_run else None,
    }
