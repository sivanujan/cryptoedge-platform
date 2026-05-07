import logging
import asyncio
from flask import Blueprint, jsonify, request
from database.connection import SessionLocal
from services.analysis_service import analyze_coin_deep, chat_with_ai

logger = logging.getLogger(__name__)
analysis_bp = Blueprint('analysis', __name__, url_prefix='/api/v1/analysis')

@analysis_bp.route("/<symbol>", methods=["GET"])
def get_deep_analysis(symbol):
    """Trigger a deep scan/analysis for a specific coin."""
    db = SessionLocal()
    try:
        formatted_symbol = symbol.upper()
        if "/" not in formatted_symbol and not formatted_symbol.endswith("USDT"):
            formatted_symbol = f"{formatted_symbol}USDT"
            
        # Run async logic in sync Flask
        result = asyncio.run(analyze_coin_deep(formatted_symbol, db))
        
        if "error" in result:
            return jsonify({"error": result["error"]}), 500
        return jsonify(result)
    finally:
        db.close()

@analysis_bp.route("/chat", methods=["POST"])
def post_chat():
    """Handle AI chat queries and image analysis."""
    try:
        query = request.form.get("query", "")
        image_file = request.files.get("image")
        
        image_data = None
        if image_file:
            image_data = image_file.read()

        # If it's a JSON request without files
        if not query and not image_file:
            data = request.json
            if data:
                query = data.get("query", "")

        result = asyncio.run(chat_with_ai(query, image_data=image_data))
        
        if "error" in result:
            return jsonify({"error": result["error"]}), 500
        return jsonify(result)
    except Exception as e:
        logger.error(f"Chat route error: {e}")
        return jsonify({"error": str(e)}), 500
