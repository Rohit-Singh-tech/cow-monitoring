import os
import sys
from sqlalchemy import create_engine, text

# Add the backend dir to sys.path so we can import app modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config import settings

def create_index_concurrently():
    # Use AUTOCOMMIT isolation level because CREATE INDEX CONCURRENTLY cannot run inside a transaction block
    engine = create_engine(settings.sqlalchemy_database_url, isolation_level="AUTOCOMMIT")
    
    with engine.connect() as conn:
        print("Creating index on datalogger_points.header_id concurrently...")
        try:
            conn.execute(text("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_datalogger_points_header_id ON datalogger_points (header_id);"))
            print("Successfully created index!")
        except Exception as e:
            print(f"Error creating index: {e}")

if __name__ == "__main__":
    create_index_concurrently()
