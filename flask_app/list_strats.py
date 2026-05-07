from database.connection import SessionLocal
from database.models import Strategy

db = SessionLocal()
strats = db.query(Strategy).all()
for s in strats:
    print(f"ID: {s.id}, Name: {s.name}, HasPine: {bool(s.pine_script)}, HasPython: {bool(s.python_code)}")
db.close()
