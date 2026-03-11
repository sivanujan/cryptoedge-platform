import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks
    logger.info("Starting up, setting up main asyncio loop...")
    from services.scanner_service import set_main_loop
    import asyncio
    set_main_loop(asyncio.get_running_loop())

    logger.info("Initializing database tables...")
    from database.connection import init_db
    init_db()

    logger.info("Seeding default strategy...")
    _seed_default_strategy()

    logger.info("Starting scheduler...")
    from scheduler import start_scheduler
    start_scheduler()

    yield  # application is running

    # Shutdown tasks
    from scheduler import stop_scheduler
    stop_scheduler()
    logger.info("Shutdown complete.")

app = FastAPI(
    title="CryptoEdge Trading API",
    version="1.0.0",
    lifespan=lifespan,
)


# CORS — allow frontend dev server on both common ports
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
from routers import coins, strategies, backtest, signals, dashboard
from routers import settings as settings_router

app.include_router(dashboard.router)
app.include_router(coins.router)
app.include_router(strategies.router)
app.include_router(backtest.router)
app.include_router(signals.router)
app.include_router(settings_router.router)


@app.get("/health")
def health():
    """Instant health check — no DB dependency, always fast."""
    return {"status": "ok", "service": "CryptoEdge API"}


@app.get("/health/db")
def health_db():
    """Full health check including database connectivity."""
    from database.connection import SessionLocal
    try:
        db = SessionLocal()
        db.execute(__import__('sqlalchemy').text("SELECT 1"))
        db.close()
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "database": str(e)}


# ─────────────────────────────────────────────
#  WebSocket: Live Prices
# ─────────────────────────────────────────────
@app.websocket("/ws/prices")
async def ws_prices(websocket: WebSocket):
    from services.scanner_service import register_price_ws, unregister_price_ws
    from services.binance_service import get_current_price

    await websocket.accept()
    register_price_ws(websocket)
    logger.info("WebSocket price client connected")

    try:
        while True:
            # Push BTC and ETH prices every second
            try:
                btc = get_current_price("BTC/USDT")
                eth = get_current_price("ETH/USDT")
                await websocket.send_json({
                    "type": "prices",
                    "data": {
                        "BTC/USDT": btc,
                        "ETH/USDT": eth,
                    }
                })
            except Exception as e:
                logger.debug(f"Price WS send error: {e}")

            await asyncio.sleep(2)
    except WebSocketDisconnect:
        logger.info("WebSocket price client disconnected")
    finally:
        unregister_price_ws(websocket)


# ─────────────────────────────────────────────
#  WebSocket: Live Signals
# ─────────────────────────────────────────────
@app.websocket("/ws/signals")
async def ws_signals(websocket: WebSocket):
    from services.scanner_service import register_signal_ws, unregister_signal_ws

    await websocket.accept()
    register_signal_ws(websocket)
    logger.info("WebSocket signal client connected")

    try:
        # Keep connection alive
        while True:
            await asyncio.sleep(30)
            await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        logger.info("WebSocket signal client disconnected")
    finally:
        unregister_signal_ws(websocket)


def _seed_default_strategy():
    """Insert built-in strategies into DB if they don't exist."""
    from database.connection import SessionLocal
    from database.models import Strategy

    _BUILTIN_STRATEGIES = [
        {
            "name": "Golden Cross",
            "description": (
                "Uses EMA21/50/200 crossover with trend filter. "
                "Enters when fast EMA crosses above slow EMA with price above trend EMA."
            ),
            "parameters": {
                "fastLen": 21,
                "slowLen": 50,
                "trendLen": 200,
                "useTrendFilter": True,
                "maxDrawdownPct": 5.0,
            },
        },
        {
            "name": "Ulcer Trend Strategy",
            "description": (
                "Uses the Ulcer Index (downside volatility stress) combined with a Trend EMA. "
                "Enters long when stress is easing and price is in an uptrend. "
                "Enters short when stress is rising and price is in a downtrend. "
                "Exits on stress reversal, stop-loss (-2%), or take-profit (+4%)."
            ),
            "parameters": {
                "ui_length": 14,
                "ui_ma_length": 5,
                "trend_ema_length": 50,
                "allow_shorts": True,
                "stop_loss_pct": 2.0,
                "take_profit_pct": 4.0,
            },
        },
    ]

    db = SessionLocal()
    try:
        for s_data in _BUILTIN_STRATEGIES:
            existing = db.query(Strategy).filter_by(name=s_data["name"]).first()
            if not existing:
                strategy = Strategy(
                    name=s_data["name"],
                    description=s_data["description"],
                    parameters=s_data["parameters"],
                    is_active=True,
                )
                db.add(strategy)
                logger.info(f"Strategy seeded: {s_data['name']}")
        db.commit()
    except Exception as e:
        logger.error(f"Strategy seeding error: {e}")
        db.rollback()
    finally:
        db.close()
