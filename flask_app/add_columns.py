from sqlalchemy import text
from database.connection import engine

def add_columns():
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE signals ADD COLUMN structure_sl FLOAT"))
            conn.execute(text("ALTER TABLE signals ADD COLUMN structure_tp FLOAT"))
            conn.execute(text("ALTER TABLE signals ADD COLUMN sl_pct FLOAT"))
            conn.execute(text("ALTER TABLE signals ADD COLUMN tp_pct FLOAT"))
            conn.execute(text("ALTER TABLE signals ADD COLUMN rr_ratio FLOAT"))
            conn.execute(text("ALTER TABLE signals ADD COLUMN sl_method VARCHAR(20)"))
            conn.commit()
            print("Columns added successfully")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    add_columns()
