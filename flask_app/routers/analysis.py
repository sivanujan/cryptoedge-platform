import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database.connection import get_db
from services.analysis_service import analyze_coin_deep

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/analysis", tags=["analysis"])

@router.get("/{symbol}")
async def get_deep_analysis(symbol: str, db: Session = Depends(get_db)):
    """Trigger a deep scan/analysis for a specific coin."""
    # Ensure symbol is in uppercase and formatted correctly for Binance (e.g., BTCUSDT)
    # But for our service, we expect something like BTC/USDT or BTCUSDT
    formatted_symbol = symbol.upper()
    if "/" not in formatted_symbol and not formatted_symbol.endswith("USDT"):
        formatted_symbol = f"{formatted_symbol}USDT"
    
    # Try with / if not found (Binance symbols in DB are often BTC/USDT)
    # For now, let's just pass it through, the service handles cleaning
    
    result = await analyze_coin_deep(formatted_symbol, db)
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
        
    return result
