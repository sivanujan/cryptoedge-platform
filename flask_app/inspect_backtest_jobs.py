import os
from sqlalchemy import create_engine, inspect
from dotenv import load_dotenv

load_dotenv()
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "crypto_platform")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL)

try:
    inspector = inspect(engine)
    if "backtest_jobs" in inspector.get_table_names():
        columns = inspector.get_columns("backtest_jobs")
        print("Columns in 'backtest_jobs':")
        for c in columns:
            print(f" - {c['name']} ({c['type']})")
    else:
        print("Table 'backtest_jobs' does not exist!")
except Exception as e:
    print(f"Error: {e}")
