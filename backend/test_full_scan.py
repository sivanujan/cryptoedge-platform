
import asyncio
import logging
from database.connection import SessionLocal
from services.scanner_service import run_scanner

# Setup logging to stdout
logging.basicConfig(level=logging.INFO)

def manual_full_scan():
    print("Pre-scan check...")
    db = SessionLocal()
    from database.models import CoinStrategyMap
    active_maps = db.query(CoinStrategyMap).filter_by(is_active=True).count()
    print(f"Total active assignments to scan: {active_maps}")
    db.close()
    
    print("Starting manual full scan...")
    # run_scanner is a sync function called by APScheduler
    run_scanner()
    print("Manual full scan finished.")

if __name__ == "__main__":
    manual_full_scan()
