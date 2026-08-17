import os
import sys
from sqlalchemy import create_engine, text

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.config import settings

def analyze_worker():
    engine = create_engine(settings.sqlalchemy_database_url)
    with engine.connect() as conn:
        print("\n--- EXPLAIN ANALYZE WORKER QUERY ---")
        sql = """
            EXPLAIN ANALYZE SELECT h.id 
            FROM datalogger_headers h
            LEFT JOIN ml_inferences m ON h.id = m.header_id
            WHERE m.id IS NULL
            ORDER BY h.id DESC
            LIMIT 50
        """
        res = conn.execute(text(sql)).fetchall()
        for r in res:
            print(r[0])

if __name__ == "__main__":
    analyze_worker()
