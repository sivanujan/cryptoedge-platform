"""
breakout_scanner.py — Main Breakout Scanner that:
1. Fetches top gainers/losers from Binance Futures
2. Computes all indicators per coin
3. Filters via signal_filter.py
4. Saves valid signals (score >= 4) to the DB
"""
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any

import pandas as pd

from scanner.indicators import (
    calculate_rsi,
    calculate_atr,
    calculate_vwap,
    calculate_volume_ratio,
    calculate_key_level,
    calculate_rs_vs_btc,
)
from scanner.signal_filter import evaluate_signal

logger = logging.getLogger(__name__)

# Stablecoins to exclude from scanning
STABLECOIN_KEYWORDS = {"USDC", "BUSD", "TUSD", "DAI", "USDT", "FDUSD", "USDP"}


def _is_stable(symbol: str) -> bool:
    """Return True if the base asset is a stablecoin."""
    base = symbol.replace("USDT", "").replace("/", "").replace(":USDT", "")
    return base in STABLECOIN_KEYWORDS


def _fetch_ohlcv_as_df(exchange, symbol: str, timeframe: str = "5m", limit: int = 100):
    """Fetch OHLCV from CCXT exchange and return as DataFrame."""
    try:
        raw = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        if not raw or len(raw) < 30:
            return None
        df = pd.DataFrame(raw, columns=["open_time", "open", "high", "low", "close", "volume"])
        df = df.astype({"open": float, "high": float, "low": float, "close": float, "volume": float})
        return df
    except Exception as e:
        logger.warning(f"[FETCH] Failed for {symbol}: {e}")
        return None


async def run_breakout_scanner() -> Dict[str, Any]:
    """
    Main scanner coroutine. Designed to run every 15 minutes via APScheduler.
    Returns a summary dict with scan results.
    """
    print("\n" + "="*60)
    print(f"[BREAKOUT SCANNER] Starting run at {datetime.utcnow().isoformat()}Z")
    print("="*60)

    from services.binance_service import get_swap_exchange
    from database.connection import SessionLocal
    from database.scanner_models import BreakoutSignal, ScannerRun

    db = SessionLocal()
    signals_saved = []
    total_scanned = 0

    try:
        exchange = get_swap_exchange()

        # ── Step 1: Fetch all tickers ──────────────────────────────────
        print("[SCANNER] Fetching all USDT futures tickers...")
        tickers = exchange.fetch_tickers()

        usdt_tickers = {}
        for sym, tick in tickers.items():
            if not sym.endswith("/USDT:USDT"):
                continue
            if _is_stable(sym):
                continue
            change = float(tick.get("percentage", 0) or 0)
            vol = float(tick.get("quoteVolume", 0) or 0)
            if vol < 5_000_000:  # Min 5M USDT volume
                continue
            usdt_tickers[sym] = {
                "symbol": sym,
                "price": float(tick.get("last", 0) or 0),
                "change_24h": change,
                "volume_24h": vol,
            }

        print(f"[SCANNER] Found {len(usdt_tickers)} qualifying USDT futures pairs")

        # ── Step 2: Get BTC 24h change for RS calc ─────────────────────
        btc_key = "BTC/USDT:USDT"
        btc_change = float(tickers.get(btc_key, {}).get("percentage", 0) or 0)
        print(f"[SCANNER] BTC 24h change: {btc_change:.2f}%")

        # ── Step 3: Pick top 10 gainers + top 10 losers ────────────────
        sorted_tickers = sorted(usdt_tickers.values(), key=lambda x: x["change_24h"])
        top_losers = sorted_tickers[:10]    # Bottom 10 → SHORT candidates
        top_gainers = sorted_tickers[-10:][::-1]  # Top 10 → LONG candidates

        candidates = [
            (item, "LONG") for item in top_gainers
        ] + [
            (item, "SHORT") for item in top_losers
        ]

        print(f"[SCANNER] {len(top_gainers)} LONG candidates, {len(top_losers)} SHORT candidates")

        # ── Step 4-6: Analyze each coin ───────────────────────────────
        for ticker_data, direction in candidates:
            symbol = ticker_data["symbol"]
            price = ticker_data["price"]
            change_24h = ticker_data["change_24h"]

            if price <= 0:
                continue

            total_scanned += 1
            print(f"[SCAN] {symbol} ({direction}) | Price: {price:.6f} | 24h: {change_24h:.2f}%")

            try:
                # Fetch candle data
                df = _fetch_ohlcv_as_df(exchange, symbol, timeframe="5m", limit=120)
                if df is None:
                    print(f"  [SKIP] Insufficient candle data for {symbol}")
                    continue

                # Calculate all indicators
                rsi_val = calculate_rsi(df["close"], period=14)
                atr_val = calculate_atr(df, period=14)
                vwap_val = calculate_vwap(df)
                vol_ratio = calculate_volume_ratio(df, period=20)
                key_levels = calculate_key_level(df, lookback=20)
                rs_val = calculate_rs_vs_btc(change_24h, btc_change)

                indicators = {
                    "rsi": rsi_val,
                    "atr": atr_val,
                    "vwap": vwap_val,
                    "volume_ratio": vol_ratio,
                    "key_levels": key_levels,
                    "rs_vs_btc": rs_val,
                }

                print(f"  RSI={rsi_val:.1f} | ATR={atr_val:.6f} | VolRatio={vol_ratio:.2f}x | RS={rs_val:.2f}%")

                # Evaluate confluence
                result = evaluate_signal(indicators, price, direction)
                score = result["score"]
                print(f"  Score={score}/5 | Valid={result['valid']} | Checks={result['checks']}")

                # ── Step 7: Save if score >= 4 ───────────────────────
                if result["valid"]:
                    clean_symbol = symbol.split(":")[0].replace("/", "")

                    # Avoid duplicates (same symbol + direction active)
                    existing = db.query(BreakoutSignal).filter_by(
                        symbol=clean_symbol,
                        direction=direction,
                        status="ACTIVE"
                    ).first()

                    if existing:
                        print(f"  [SKIP] Duplicate active signal for {clean_symbol} {direction}")
                        continue

                    signal_row = BreakoutSignal(
                        symbol=clean_symbol,
                        direction=direction,
                        entry_price=price,
                        stop_loss=result["sl"],
                        take_profit_1=result["tp1"],
                        take_profit_2=result["tp2"],
                        atr=atr_val,
                        rsi=rsi_val,
                        volume_ratio=vol_ratio,
                        rs_vs_btc=rs_val,
                        vwap=vwap_val,
                        signal_score=score,
                        status="ACTIVE",
                    )
                    db.add(signal_row)
                    db.flush()  # Get the ID before commit

                    signals_saved.append({
                        "symbol": clean_symbol,
                        "direction": direction,
                        "score": score,
                        "entry": price,
                        "sl": result["sl"],
                        "tp1": result["tp1"],
                        "tp2": result["tp2"],
                    })
                    print(f"  ✅ SIGNAL SAVED: {clean_symbol} {direction} | Entry={price} | SL={result['sl']:.6f}")

            except Exception as e:
                logger.warning(f"[ERROR] Failed to process {symbol}: {e}")
                print(f"  [ERROR] {symbol}: {e}")
                continue

        db.commit()

        # ── Step 8: Save run summary ───────────────────────────────────
        run_log = ScannerRun(
            total_scanned=total_scanned,
            signals_generated=len(signals_saved),
        )
        db.add(run_log)
        db.commit()

        summary = {
            "total_scanned": total_scanned,
            "signals_generated": len(signals_saved),
            "signals": signals_saved,
            "run_at": datetime.utcnow().isoformat() + "Z",
        }

        print(f"\n[BREAKOUT SCANNER] Run complete: {total_scanned} scanned, {len(signals_saved)} signals generated")
        print("="*60 + "\n")
        return summary

    except Exception as e:
        logger.error(f"[BREAKOUT SCANNER] Fatal error: {e}")
        print(f"[BREAKOUT SCANNER] Fatal error: {e}")
        db.rollback()
        return {"error": str(e), "total_scanned": 0, "signals_generated": 0}
    finally:
        db.close()
