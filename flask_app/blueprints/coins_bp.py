import logging
from flask import Blueprint, jsonify, request
from database.connection import SessionLocal
from database.models import Coin

logger = logging.getLogger(__name__)
coins_bp = Blueprint('coins', __name__, url_prefix='/api/v1/coins')

@coins_bp.route("", methods=["GET"])
def list_coins():
    """Return all active coins."""
    db = SessionLocal()
    try:
        coins = db.query(Coin).filter_by(is_active=True).all()
        return jsonify([{"symbol": c.symbol, "id": c.id} for c in coins])
    finally:
        db.close()

@coins_bp.route("/<path:symbol>/price", methods=["GET"])
def get_coin_price(symbol):
    """Fetch current price for a coin."""
    from services.binance_service import get_ticker_price
    try:
        price = get_ticker_price(symbol)
        return jsonify({"symbol": symbol, "price": price})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@coins_bp.route("/sync", methods=["POST"])
def sync_coins():
    """Fetch USDT pairs from Binance."""
    from services.binance_service import get_all_usdt_pairs
    db = SessionLocal()
    try:
        pairs = get_all_usdt_pairs()
        added = 0
        for symbol in pairs:
            if not db.query(Coin).filter_by(symbol=symbol).first():
                base = symbol.split('/')[0]
                db.add(Coin(symbol=symbol, base_asset=base, is_active=True))
                added += 1
        db.commit()
        return jsonify({"added": added, "synced": db.query(Coin).count()})
    finally:
        db.close()
