import logging
import asyncio
from flask import Blueprint, jsonify, request
from services.futures_analysis_service import get_futures_top_long_short

logger = logging.getLogger(__name__)
futures_bp = Blueprint('futures', __name__, url_prefix='/api/v1/futures')

@futures_bp.route("/top-long-short", methods=["GET"])
def get_top_long_short():
    """Get top 20 longs and shorts from Binance Futures."""
    limit = int(request.args.get("limit", 20))
    timeframe = request.args.get("timeframe", "1h")
    
    result = asyncio.run(get_futures_top_long_short(limit=limit, timeframe=timeframe))
    
    if "error" in result:
        return jsonify({"error": result["error"], "longs": [], "shorts": []})
    return jsonify(result)
