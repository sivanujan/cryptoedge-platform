import os
import logging
import json
from flask import Flask, send_from_directory, jsonify, request
from flask_sock import Sock
from flask_cors import CORS
from dotenv import load_dotenv
from database.connection import SessionLocal, init_db
from database.models import Setting
from scheduler import start_scheduler

from blueprints.strategies_bp import strategies_bp
from blueprints.signals_bp import signals_bp
from blueprints.coins_bp import coins_bp
from blueprints.backtest_bp import backtest_bp
from blueprints.analysis_bp import analysis_bp
from blueprints.futures_bp import futures_bp
from blueprints.dashboard_bp import dashboard_bp
from blueprints.scanner_bp import scanner_bp

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Use 'static' folder to serve built React app
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
app = Flask(__name__, static_folder=static_dir, static_url_path='')
app.url_map.strict_slashes = False
sock = Sock(app)

# WebSocket registries
price_clients = set()
signal_clients = set()

# Initialize DB on startup
with app.app_context():
    logger.info("Initializing database...")
    init_db()
    
    # Start scheduler
    logger.info("Starting scheduler...")
    start_scheduler()

# Register Blueprints
app.register_blueprint(strategies_bp)
app.register_blueprint(signals_bp)
app.register_blueprint(coins_bp)
app.register_blueprint(backtest_bp)
app.register_blueprint(analysis_bp)
app.register_blueprint(futures_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(scanner_bp)

@app.route("/api/v1/settings", methods=["GET", "POST"])
def api_settings():
    db = SessionLocal()
    try:
        if request.method == "POST":
            data = request.json
            for key, value in data.items():
                setting = db.query(Setting).filter_by(key=key).first()
                if setting:
                    setting.value = str(value)
                else:
                    db.add(Setting(key=key, value=str(value)))
            db.commit()
            return jsonify({"status": "success"})
        
        settings_rows = db.query(Setting).all()
        return jsonify({row.key: row.value for row in settings_rows})
    finally:
        db.close()

@app.route("/health")
@app.route("/api/v1/health")
def health():
    return jsonify({"status": "ok", "service": "CryptoEdge Integrated Flask API"})

# Native WebSocket Routes
@sock.route('/ws/prices')
def price_ws(ws):
    price_clients.add(ws)
    logger.info(f"Client connected to /ws/prices (Total: {len(price_clients)})")
    try:
        while True:
            # Keep connection alive
            ws.receive()
    except Exception:
        pass
    finally:
        price_clients.remove(ws)
        logger.info("Client disconnected from /ws/prices")

@sock.route('/ws/signals')
def signal_ws(ws):
    signal_clients.add(ws)
    logger.info(f"Client connected to /ws/signals (Total: {len(signal_clients)})")
    try:
        while True:
            ws.receive()
    except Exception:
        pass
    finally:
        signal_clients.remove(ws)
        logger.info("Client disconnected from /ws/signals")

CORS(app)

@app.before_request
def log_request_info():
    if not request.path.startswith('/static'):
        logger.info(f"Request: {request.method} {request.path} {request.args.to_dict()}")

# Health v1 for older clients
@app.route('/api/v1/health')
def health_v1():
    return jsonify({"status": "ok", "version": "1.0.0"}), 200

# Explicit SPA routes (must be AFTER API routes)
@app.route('/dashboard')
@app.route('/signals')
@app.route('/screener')
@app.route('/strategies')
@app.route('/analysis')
@app.route('/backtest')
@app.route('/settings')
@app.route('/')
def spa_page():
    return send_from_directory(app.static_folder, 'index.html')

# Catch-all for any other frontend paths
@app.route('/<path:path>')
def catch_all(path):
    # Do not catch API or WebSocket routes
    if path.startswith('api/') or path.startswith('ws/') or request.headers.get('Upgrade') == 'websocket':
        return jsonify({"error": "Not Found", "path": path}), 404
        
    if os.path.exists(os.path.join(app.static_folder, path)):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, 'index.html')

def broadcast_to_prices(data):
    count = len(price_clients)
    if count > 0:
        logger.info(f"Broadcasting prices to {count} clients")
    for ws in list(price_clients):
        try:
            ws.send(json.dumps(data))
        except Exception as e:
            logger.error(f"Price WS error: {e}")
            price_clients.discard(ws)

def broadcast_to_signals(data):
    for ws in list(signal_clients):
        try:
            ws.send(json.dumps(data))
        except Exception as e:
            logger.error(f"Signal WS error: {e}")
            signal_clients.discard(ws)

# Bridge for services
import services.scanner_service
services.scanner_service.broadcast_price = broadcast_to_prices
services.scanner_service.broadcast_signal = broadcast_to_signals

# Serve React App for all non-matching routes (using 404 handler for SPA routing fallback)

# Serve React App for all non-matching routes (using 404 handler for SPA routing fallback)
@app.errorhandler(404)
def handle_404(e):
    # Do NOT serve HTML for API or WebSocket requests that truly don't exist
    if request.path.startswith('/api/') or request.path.startswith('/ws/') or request.headers.get('Upgrade') == 'websocket':
        logger.warning(f"404 for API/WS: {request.path} [Upgrade: {request.headers.get('Upgrade')}]")
        return jsonify({"error": "Not Found", "path": request.path}), 404
        
    # Otherwise, it's a frontend route - serve index.html with a 200 status
    return send_from_directory(app.static_folder, 'index.html'), 200

if __name__ == "__main__":
    # use_reloader=False is REQUIRED for flask-sock WebSockets to work on Windows.
    # The Werkzeug stat-based reloader intercepts the HTTP Upgrade request before
    # flask-sock can handle it, producing "Invalid frame header" on the client.
    app.run(host="127.0.0.1", port=8000, debug=True, use_reloader=False, threaded=True)
