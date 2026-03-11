import logging
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database.connection import get_db
from database.models import Setting

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/settings", tags=["settings"])

DEFAULT_SETTINGS = {
    "binance_api_key": "",
    "binance_secret_key": "",
    "scanner_interval_minutes": "15",
    "risk_per_trade_pct": "2",
    "default_sl_pct": "3",
    "default_tp_pct": "6",
    "notify_browser": "true",
    "notify_email": "false",
    "notify_telegram": "false",
}


class SettingsUpdate(BaseModel):
    binance_api_key: Optional[str] = None
    binance_secret_key: Optional[str] = None
    scanner_interval_minutes: Optional[str] = None
    risk_per_trade_pct: Optional[str] = None
    default_sl_pct: Optional[str] = None
    default_tp_pct: Optional[str] = None
    notify_browser: Optional[str] = None
    notify_email: Optional[str] = None
    notify_telegram: Optional[str] = None


@router.get("")
def get_settings(db: Session = Depends(get_db)):
    settings_rows = db.query(Setting).all()
    settings = {**DEFAULT_SETTINGS}
    for row in settings_rows:
        settings[row.key] = row.value
    # Mask API keys
    if settings.get("binance_api_key"):
        settings["binance_api_key"] = "***" + settings["binance_api_key"][-4:]
    if settings.get("binance_secret_key"):
        settings["binance_secret_key"] = "***" + settings["binance_secret_key"][-4:]
    return settings


@router.post("")
def save_settings(body: SettingsUpdate, db: Session = Depends(get_db)):
    updates = body.model_dump(exclude_none=True)
    for key, value in updates.items():
        row = db.query(Setting).filter_by(key=key).first()
        if row:
            row.value = str(value)
        else:
            db.add(Setting(key=key, value=str(value)))
    db.commit()
    return {"saved": True, "updated_keys": list(updates.keys())}
