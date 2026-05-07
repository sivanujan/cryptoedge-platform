from database.connection import SessionLocal
from database.models import Signal, Coin

db = SessionLocal()
active_signals = db.query(Signal).filter_by(status='active').all()
print(f"Found {len(active_signals)} active signals:")
for sig in active_signals:
    print(f"ID: {sig.id}, Symbol: {sig.coin.symbol}, Entry: {sig.entry_price}")
db.close()
