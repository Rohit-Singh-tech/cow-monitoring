import os
import sys
from sqlalchemy import create_engine, text

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.config import settings

def analyze_queries():
    engine = create_engine(settings.sqlalchemy_database_url)
    with engine.connect() as conn:
        print("--- EXPLAIN ANALYZE MAX(id) ---")
        res = conn.execute(text("EXPLAIN ANALYZE SELECT MAX(id) FROM datalogger_headers WHERE device_id = '9'")).fetchall()
        for r in res:
            print(r[0])
            
        print("\n--- EXPLAIN ANALYZE ORDER BY id DESC LIMIT 1 ---")
        res = conn.execute(text("EXPLAIN ANALYZE SELECT id FROM datalogger_headers WHERE device_id = '9' ORDER BY id DESC LIMIT 1")).fetchall()
        for r in res:
            print(r[0])
            
        print("\n--- EXPLAIN ANALYZE points fetch ---")
        res = conn.execute(text("EXPLAIN ANALYZE SELECT * FROM datalogger_points WHERE header_id = (SELECT MAX(id) FROM datalogger_headers WHERE device_id = '9')")).fetchall()
        for r in res:
            print(r[0])

if __name__ == "__main__":
    analyze_queries()
