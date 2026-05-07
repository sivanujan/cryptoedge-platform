import logging
from fastapi import APIRouter, Query
from services.futures_analysis_service import get_futures_top_long_short

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/futures", tags=["futures"])


@router.get("/top-long-short")
async def get_top_long_short(
    limit: int = Query(20, ge=5, le=50, description="Number of top gainers/losers to return"),
    min_volume: float = Query(10000000, ge=0, description="Minimum 24h volume in USDT"),
    timeframe: str = Query("1h", pattern="^(15m|1h|4h)$", description="Timeframe for technical analysis"),
):
    """
    Get top 20 longs (gainers) and shorts (losers) from Binance Futures with technical analysis.

    - **limit**: Number of top gainers/losers to return (default 20, max 50)
    - **min_volume**: Minimum 24h volume in USDT to include (default 10M)
    - **timeframe**: Timeframe for technical analysis (15m, 1h, 4h)
    """
    result = await get_futures_top_long_short(
        limit=limit,
        min_volume=min_volume,
        timeframe=timeframe,
    )

    if "error" in result:
        return {"error": result["error"], "longs": [], "shorts": []}

    return result