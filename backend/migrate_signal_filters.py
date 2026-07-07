from database.connection import engine
from database.models import Base as ModelsBase
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate():
    # Create tables defined in database/models.py (including the new signal_filter_logs table)
    logger.info("Creating tables defined in database/models.py (like signal_filter_logs)...")
    ModelsBase.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        # Add filter_status to signals
        try:
            conn.execute(text("ALTER TABLE signals ADD COLUMN filter_status VARCHAR(20)"))
            conn.commit()
            logger.info("Added 'filter_status' column to 'signals' table.")
        except Exception as e:
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                logger.info("'filter_status' column already exists in 'signals' table.")
            else:
                logger.error(f"Error adding filter_status to 'signals': {e}")

        # Add filter_reason to signals
        try:
            conn.execute(text("ALTER TABLE signals ADD COLUMN filter_reason VARCHAR(100)"))
            conn.commit()
            logger.info("Added 'filter_reason' column to 'signals' table.")
        except Exception as e:
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                logger.info("'filter_reason' column already exists in 'signals' table.")
            else:
                logger.error(f"Error adding filter_reason to 'signals': {e}")

if __name__ == "__main__":
    migrate()
