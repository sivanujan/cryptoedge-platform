from database.connection import SessionLocal
from database.models import Strategy

db = SessionLocal()
s = db.query(Strategy).get(28)
if s:
    s.python_code = s.python_code.replace('close >', "df['close'] >").replace('close <', "df['close'] <")
    db.commit()
    print("Fixed strategy 28")

s = db.query(Strategy).get(26)
if s:
    s.python_code = s.python_code.replace('close >', "df['close'] >").replace('close <', "df['close'] <")
    db.commit()
    print("Fixed strategy 26")
