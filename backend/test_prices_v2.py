import sys
import os

# Add backend to path
sys.path.append(os.getcwd())

from database.connection import SessionLocal
from services.signal_service import get_live_signals, get_signal_history

def test():
    db = SessionLocal()
    try:
        print("Testing Live Signals...")
        live = get_live_signals(db)
        if live:
            s = live[0]
            print(f"Signal: {s['symbol']}, Entry: {s['entry_price']}, Current: {s['current_price']}, PnL: {s['pnl_percent']}%")
        else:
            print("No live signals found.")

        print("\nTesting Signal History...")
        history = get_signal_history(db, limit=5)
        signals = history.get('signals', [])
        for s in signals:
            print(f"Signal: {s['symbol']}, Status: {s['status']}, Entry: {s['entry_price']}, Current: {s['current_price']}, PnL: {s['pnl_percent']}%")
            
    finally:
        db.close()

if __name__ == "__main__":
    test()
