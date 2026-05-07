import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import Signal
from services.signal_service import get_live_signals, get_signal_history, get_signal_stats, clear_all_signals
from services.scanner_service import run_scanner
from fastapi import BackgroundTasks

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/signals", tags=["signals"])


@router.get("/live")
def live_signals(db: Session = Depends(get_db)):
    """Return all currently active signals."""
    return {"signals": get_live_signals(db)}


@router.get("/history")
def signal_history(
    coin: str = Query(None),
    strategy: str = Query(None),
    signal_type: str = Query(None),
    result: str = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Return paginated signal history with optional filters."""
    data = get_signal_history(db, coin, strategy, signal_type, result, limit, offset)
    stats = get_signal_stats(db)
    return {**stats, **data}


@router.delete("/history")
def clear_history(db: Session = Depends(get_db)):
    """Delete all signal history."""
    success = clear_all_signals(db)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to clear signal history")
    return {"ok": True, "message": "Signal history cleared successfully"}


@router.patch("/{signal_id}/status")
def update_signal_status(
    signal_id: int,
    status: str,
    db: Session = Depends(get_db),
):
    sig = db.query(Signal).filter_by(id=signal_id).first()
    if not sig:
        raise HTTPException(status_code=404, detail="Signal not found")
    sig.status = status
    db.commit()
    return {"ok": True}

@router.post("/scan-now")
def trigger_manual_scan(background_tasks: BackgroundTasks):
    """Manually trigger the market scanner instantly."""
    background_tasks.add_task(run_scanner)
    return {"status": "started", "message": "Manual market scan triggered in background."}
