
import os
import json
import sys
from sqlalchemy.orm import Session
from database.connection import SessionLocal
from services.signal_service import get_signal_stats

def verify_strategy_stats():
    db = SessionLocal()
    try:
        print("Fetching signal stats with strategy breakdown...")
        stats = get_signal_stats(db)
        
        print("\nGlobal Stats:")
        print(f"Total: {stats['total_signals']}, Wins: {stats['wins']}, Losses: {stats['losses']}, Win Rate: {stats['win_rate']}%, P&L: {stats['total_pnl']}%")
        
        print("\nStrategy-wise Stats:")
        if not stats.get('strategy_stats'):
            print("No strategy stats found!")
        else:
            for s in stats['strategy_stats']:
                print(f"- {s['name']}: {s['wins']}W / {s['losses']}L ({s['win_rate']}%) | P&L: {s['total_pnl']}% | Total Signals: {s['total_signals']}")
                
    finally:
        db.close()

if __name__ == "__main__":
    verify_strategy_stats()
