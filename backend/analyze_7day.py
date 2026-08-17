import os
import sys
from sqlalchemy import create_engine, text

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.config import settings

def analyze_7day():
    engine = create_engine(settings.sqlalchemy_database_url)
    with engine.connect() as conn:
        print("\n--- EXPLAIN ANALYZE 7DAY GROUP BY ---")
        sql = """
            EXPLAIN ANALYZE SELECT DATE(timestamp) as day_date, COUNT(*) as pkt_count
            FROM datalogger_headers
            WHERE device_id = '9'
            GROUP BY DATE(timestamp)
            ORDER BY day_date DESC
            LIMIT 7
        """
        res = conn.execute(text(sql)).fetchall()
        for r in res:
            print(r[0])

if __name__ == "__main__":
    analyze_7day()
