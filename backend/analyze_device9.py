import os
import sys
from sqlalchemy import create_engine, text

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.config import settings

def analyze_device9():
    engine = create_engine(settings.sqlalchemy_database_url)
    with engine.connect() as conn:
        print("\n--- EXPLAIN ANALYZE MAX(id) for device9 ---")
        sql = "EXPLAIN ANALYZE SELECT MAX(id) FROM datalogger_headers WHERE device_id = 'device9'"
        res = conn.execute(text(sql)).fetchall()
        for r in res:
            print(r[0])
            
        print("\n--- EXPLAIN ANALYZE ORDER BY id DESC LIMIT 1 for device9 ---")
        sql2 = "EXPLAIN ANALYZE SELECT id FROM datalogger_headers WHERE device_id = 'device9' ORDER BY id DESC LIMIT 1"
        res2 = conn.execute(text(sql2)).fetchall()
        for r in res2:
            print(r[0])

if __name__ == "__main__":
    analyze_device9()
