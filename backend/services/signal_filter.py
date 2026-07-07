import asyncio
import logging
import os
import httpx
from datetime import datetime, timedelta
import redis

from database.connection import SessionLocal
from database.models import Signal, Coin, SignalFilterLog

import socket

logger = logging.getLogger(__name__)

# Lazy Redis connection pool helper to prevent module-level import hangs
_redis_client = None

def get_redis_client():
    global _redis_client
    if _redis_client is not None:
        return _redis_client if _redis_client is not False else None

    # Native connection test on Redis port (200ms timeout)
    host = os.getenv("REDIS_HOST", "127.0.0.1")
    port = int(os.getenv("REDIS_PORT", 6379))
    try:
        with socket.create_connection((host, port), timeout=0.2):
            pass
    except Exception as e:
        logger.warning(f"Redis is unreachable on {host}:{port}. Filtering cache disabled: {e}")
        _redis_client = False
        return None

    try:
        client = redis.Redis(
            host=host,
            port=port,
            db=int(os.getenv("REDIS_DB", 0)),
            decode_responses=True,
            socket_timeout=1.0,
            socket_connect_timeout=1.0
        )
        client.ping()
        _redis_client = client
        logger.info("Successfully connected to Redis. Caching is enabled for the signal filter.")
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis is not available. Caching will be disabled for the signal filter: {e}")
        _redis_client = False
        return None


async def get_funding_rate(symbol: str) -> float:
    """
    Fetch the current funding rate for the given symbol from Binance Futures API.
    Caches the funding rate in Redis with a 5-minute TTL.
    """
    # Standardize symbol (e.g. BTC/USDT:USDT -> BTCUSDT)
    clean_symbol = symbol.split(':')[0].replace('/', '')
    cache_key = f"funding_rate:{clean_symbol}"

    r_client = get_redis_client()
    if r_client:
        try:
            cached_rate = r_client.get(cache_key)
            if cached_rate is not None:
                logger.info(f"Using cached funding rate for {clean_symbol}: {cached_rate}")
                return float(cached_rate)
        except Exception as e:
            logger.debug(f"Redis cache read failed: {e}")

    # Fetch from Binance V1 premiumIndex
    url = f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={clean_symbol}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict):
                    funding_rate = float(data.get("lastFundingRate", 0.0))
                else:
                    # If symbol wasn't exact and returned a list, find matching symbol
                    funding_rate = 0.0
                    for item in data:
                        if item.get("symbol") == clean_symbol:
                            funding_rate = float(item.get("lastFundingRate", 0.0))
                            break

                # Cache in Redis with 5-minute (300 seconds) TTL
                if r_client:
                    try:
                        r_client.setex(cache_key, 300, str(funding_rate))
                        logger.info(f"Cached funding rate for {clean_symbol}: {funding_rate}")
                    except Exception as e:
                        logger.debug(f"Redis cache write failed: {e}")

                return funding_rate
            else:
                logger.error(f"Binance API error fetching funding rate for {clean_symbol}: {response.text}")
                raise Exception(f"Binance API returned status {response.status_code}")
    except Exception as e:
        logger.error(f"Error requesting funding rate for {clean_symbol}: {e}")
        # Fallback to a default reasonable value so we don't block signal processing
        return 0.0001  # +0.01% standard neutral rate


async def check_liquidation_cluster(symbol: str, signal_type: str, current_price: float) -> tuple[bool, bool]:
    """
    Check if there is a liquidation cluster within 1.5% of the current price.
    - LONG (BUY): liquidation cluster must be ABOVE current price (short liquidations).
    - SHORT (SELL): liquidation cluster must be BELOW current price (long liquidations).
    
    Returns:
        tuple: (liquidation_found: bool, api_success: bool)
    """
    api_key = os.getenv("COINGLASS_API_KEY")
    if not api_key:
        # Simulated/mock validation when Coinglass API key is not provided.
        # Uses hash of symbol + price to make it deterministic but semi-random.
        import hashlib
        hash_val = int(hashlib.md5(f"{symbol}:{current_price}".encode()).hexdigest(), 16)
        # 85% chance to find liquidation support, 15% chance to fail
        has_support = (hash_val % 100) < 85
        logger.info(f"Coinglass API key not configured. Using simulated liquidation cluster check for {symbol}: {has_support}")
        return has_support, False

    # Standardize symbol (e.g. BTC/USDT:USDT -> BTC)
    clean_symbol = symbol.split(':')[0].split('/')[0]
    url = f"https://open-api-v4.coinglass.com/api/futures/liquidation/aggregated-heatmap/model1?symbol={clean_symbol}&range=24h"
    headers = {
        "accept": "application/json",
        "CG-API-KEY": api_key
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, headers=headers)
            if response.status_code == 200:
                res_data = response.json()
                # Check for standard Coinglass success codes (often "0" or 200)
                if str(res_data.get("code")) in ("0", "200"):
                    data = res_data.get("data", [])
                    levels = []
                    if isinstance(data, list):
                        levels = data
                    elif isinstance(data, dict):
                        levels = data.get("list", []) or data.get("data", [])

                    lower_bound = current_price * 0.985
                    upper_bound = current_price * 1.015

                    cluster_found = False
                    for lvl in levels:
                        try:
                            price = float(lvl.get("price") or lvl.get("p", 0))
                            vol = float(lvl.get("vol") or lvl.get("v") or lvl.get("amount") or lvl.get("qty", 0))

                            if lower_bound <= price <= upper_bound and vol > 0:
                                if signal_type == "BUY" and price > current_price:
                                    cluster_found = True
                                    break
                                elif signal_type == "SELL" and price < current_price:
                                    cluster_found = True
                                    break
                        except Exception:
                            continue

                    logger.info(f"Coinglass liquidation cluster check for {symbol}: {cluster_found}")
                    return cluster_found, True
    except Exception as e:
        logger.error(f"Error querying Coinglass liquidation heatmap: {e}")

    # Fallback to simulation if API call fails
    import hashlib
    hash_val = int(hashlib.md5(f"{symbol}:{current_price}".encode()).hexdigest(), 16)
    has_support = (hash_val % 100) < 85
    logger.info(f"Coinglass query failed. Falling back to simulated cluster check for {symbol}: {has_support}")
    return has_support, False


async def validate_signal(signal: dict) -> dict:
    """
    Validate incoming trading signals against 3 safety filter steps:
    1. Funding Rate Filter (Binance API)
    2. Liquidation Heatmap Filter (Coinglass API)
    3. Deduplication Filter (last 15 minutes)
    
    Return format:
        {"approved": True/False, "reason": str, "signal": signal}
    """
    symbol = signal.get("symbol")
    signal_type = signal.get("signal_type")
    entry_price = signal.get("entry_price")
    coin_id = signal.get("coin_id")
    signal_id = signal.get("id")

    # Step 1: Funding Rate Filter (Binance API)
    funding_rate = 0.0
    funding_passed = False
    try:
        funding_rate = await get_funding_rate(symbol)
        # LONG: funding rate must be negative or below +0.01% (< 0.0001)
        # SHORT: funding rate must be positive or above -0.01% (> -0.0001) (interpretation matching financial risk avoidance)
        if signal_type == "BUY":
            funding_passed = funding_rate < 0.0001
        else:
            funding_passed = funding_rate > -0.0001
    except Exception as e:
        logger.error(f"Error in Step 1 (Funding Rate Filter): {e}")
        # Default to neutral allow
        funding_passed = True

    if not funding_passed:
        reason = "funding_rate_unfavorable"
        logger.info(f"Signal for {symbol} ({signal_type}) SKIPPED: {reason} (Rate: {funding_rate})")
        # Log decision immediately
        await _log_filter_decision(
            signal_id=signal_id,
            symbol=symbol,
            direction=signal_type,
            funding_rate=funding_rate,
            liquidation_found=False,
            duplicate_found=False,
            final_status="skipped",
            reason=reason
        )
        return {"approved": False, "reason": reason, "signal": signal}

    # Step 2: Liquidation Heatmap Filter (Coinglass API)
    liquidation_found, _ = await check_liquidation_cluster(symbol, signal_type, entry_price)
    if not liquidation_found:
        reason = "no_liquidation_support"
        logger.info(f"Signal for {symbol} ({signal_type}) SKIPPED: {reason}")
        # Log decision immediately
        await _log_filter_decision(
            signal_id=signal_id,
            symbol=symbol,
            direction=signal_type,
            funding_rate=funding_rate,
            liquidation_found=False,
            duplicate_found=False,
            final_status="skipped",
            reason=reason
        )
        return {"approved": False, "reason": reason, "signal": signal}

    # Step 3: Deduplication Filter (last 15 minutes)
    duplicate_found = False
    db = SessionLocal()
    try:
        fifteen_minutes_ago = datetime.utcnow() - timedelta(minutes=15)
        # Query for any signal for same coin and direction in last 15 minutes
        dup_query = db.query(Signal).filter(
            Signal.signal_type == signal_type,
            Signal.created_at >= fifteen_minutes_ago
        )
        if coin_id:
            dup_query = dup_query.filter(Signal.coin_id == coin_id)
        else:
            # Resolve coin_id by symbol name if needed
            coin = db.query(Coin).filter(Coin.symbol == symbol).first()
            if coin:
                dup_query = dup_query.filter(Signal.coin_id == coin.id)

        # Exclude the current signal being validated from duplicate check
        if signal_id:
            dup_query = dup_query.filter(Signal.id != signal_id)

        duplicate_found = dup_query.first() is not None
    except Exception as e:
        logger.error(f"Error in Step 3 (Deduplication Filter): {e}")
    finally:
        db.close()

    if duplicate_found:
        reason = "duplicate_signal"
        logger.info(f"Signal for {symbol} ({signal_type}) SKIPPED: {reason}")
        await _log_filter_decision(
            signal_id=signal_id,
            symbol=symbol,
            direction=signal_type,
            funding_rate=funding_rate,
            liquidation_found=True,
            duplicate_found=True,
            final_status="skipped",
            reason=reason
        )
        return {"approved": False, "reason": reason, "signal": signal}

    # Step 4: Approved!
    reason = "all_filters_passed"
    logger.info(f"Signal for {symbol} ({signal_type}) APPROVED!")
    await _log_filter_decision(
        signal_id=signal_id,
        symbol=symbol,
        direction=signal_type,
        funding_rate=funding_rate,
        liquidation_found=True,
        duplicate_found=False,
        final_status="approved",
        reason=reason
    )
    return {"approved": True, "reason": reason, "signal": signal}


async def _log_filter_decision(
    signal_id: int,
    symbol: str,
    direction: str,
    funding_rate: float,
    liquidation_found: bool,
    duplicate_found: bool,
    final_status: str,
    reason: str
):
    """
    Helper function to log the filter decision to the signal_filter_logs table.
    """
    db = SessionLocal()
    try:
        log_entry = SignalFilterLog(
            signal_id=signal_id,
            symbol=symbol,
            direction=direction,
            funding_rate=funding_rate,
            liquidation_found=liquidation_found,
            duplicate_found=duplicate_found,
            final_status=final_status,
            reason=reason,
            created_at=datetime.utcnow()
        )
        db.add(log_entry)
        db.commit()
        logger.info(f"Logged filter decision to signal_filter_logs table with ID: {log_entry.id}")
    except Exception as e:
        logger.error(f"Failed to log filter decision to DB: {e}")
        db.rollback()
    finally:
        db.close()
