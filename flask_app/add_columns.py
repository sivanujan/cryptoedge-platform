from sqlalchemy import text
from database.connection import engine

def add_columns():
    try:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE signals ADD COLUMN ai_analysis TEXT"))
            conn.execute(text("ALTER TABLE signals ADD COLUMN ai_score FLOAT"))
            conn.commit()
            print("Columns added successfully")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    add_columns()
