import logging
import pandas as pd
from sqlalchemy.orm import Session
from database.connection import SessionLocal
from database.models import Signal, Coin
from services.binance_service import get_ohlcv
from services.indicator_service import add_volatility

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def backfill():
    db: Session = SessionLocal()
    try:
        # Get signals without volatility (limit to 100 most recent to avoid rate limits)
        signals = db.query(Signal).filter(Signal.volatility.is_(None)).order_by(Signal.created_at.desc()).limit(100).all()
        
        if not signals:
            logger.info("No signals found for backfilling.")
            return

        logger.info(f"Starting backfill for {len(signals)} signals...")
        
        # Cache for OHLCV data to avoid redundant API calls
        ohlcv_cache = {}

        for sig in signals:
            try:
                coin = db.query(Coin).filter_by(id=sig.coin_id).first()
                if not coin:
                    continue
                
                cache_key = f"{coin.symbol}_{sig.timeframe}"
                if cache_key in ohlcv_cache:
                    df = ohlcv_cache[cache_key]
                else:
                    df = get_ohlcv(coin.symbol, sig.timeframe, limit=200)
                    if df is not None:
                        df = add_volatility(df)
                        ohlcv_cache[cache_key] = df
                
                if df is not None and "volatility_atr" in df.columns:
                    # Find the row closest to signal creation time
                    # For simplicity, just use the last value if it's a recent signal
                    vol = float(df["volatility_atr"].iloc[-1])
                    sig.volatility = round(vol, 2)
                    logger.info(f"Updated {coin.symbol} [{sig.timeframe}] volatility to {sig.volatility}%")
                else:
                    logger.warning(f"Could not get volatility for {coin.symbol} [{sig.timeframe}]")
            
            except Exception as e:
                logger.error(f"Error backfilling signal {sig.id}: {e}")
        
        db.commit()
        logger.info("Backfill complete.")

    except Exception as e:
        logger.error(f"Backfill fatal error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    backfill()
