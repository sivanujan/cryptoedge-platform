import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database.connection import get_db
from database.models import Coin, CoinStrategyMap
from services.binance_service import get_current_price

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/coins", tags=["coins"])


@router.get("")
def list_coins(db: Session = Depends(get_db)):
    """Return all active coins with their assigned best strategy."""
    coins = db.query(Coin).filter_by(is_active=True).order_by(Coin.symbol).all()
    result = []
    for coin in coins:
        mapping = (
            db.query(CoinStrategyMap)
            .filter_by(coin_id=coin.id, is_active=True)
            .first()
        )
        result.append({
            "id": coin.id,
            "symbol": coin.symbol,
            "base_asset": coin.base_asset,
            "best_strategy": mapping.strategy.name if mapping and mapping.strategy else None,
            "best_timeframe": mapping.timeframe if mapping else None,
            "best_win_rate": mapping.win_rate if mapping else None,
        })
    return {"coins": result, "total": len(result)}


@router.get("/{symbol}/price")
def coin_price(symbol: str):
    """Get live price for a specific coin."""
    # Normalize symbol (e.g. BTCUSDT -> BTC/USDT)
    normalized = symbol if "/" in symbol else symbol.replace("USDT", "/USDT")
    price = get_current_price(normalized)
    if price is None:
        raise HTTPException(status_code=404, detail=f"Could not fetch price for {symbol}")
    return {"symbol": symbol, "price": price}


@router.post("/sync")
def sync_coins(db: Session = Depends(get_db)):
    """
    Sync all Binance USDT pairs into the coins table.
    Called once on setup or to refresh the coin list.
    """
    from services.binance_service import get_all_usdt_pairs
    pairs = get_all_usdt_pairs()
    added = 0
    for symbol in pairs:
        base = symbol.split("/")[0]
        existing = db.query(Coin).filter_by(symbol=symbol).first()
        if not existing:
            db.add(Coin(symbol=symbol, base_asset=base, is_active=True))
            added += 1
    db.commit()
    return {"synced": len(pairs), "added": added}
