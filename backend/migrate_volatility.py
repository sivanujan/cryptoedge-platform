from database.connection import engine
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    with engine.connect() as conn:
        # Add volatility to signals
        try:
            conn.execute(text("ALTER TABLE signals ADD COLUMN volatility FLOAT"))
            conn.commit()
            logger.info("Added 'volatility' column to 'signals' table.")
        except Exception as e:
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                logger.info("'volatility' column already exists in 'signals' table.")
            else:
                logger.error(f"Error adding column to 'signals': {e}")

        # Add volatility to backtest_results
        try:
            conn.execute(text("ALTER TABLE backtest_results ADD COLUMN volatility FLOAT"))
            conn.commit()
            logger.info("Added 'volatility' column to 'backtest_results' table.")
        except Exception as e:
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                logger.info("'volatility' column already exists in 'backtest_results' table.")
            else:
                logger.error(f"Error adding column to 'backtest_results': {e}")

if __name__ == "__main__":
    migrate()
