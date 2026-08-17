from app.database import engine
from sqlalchemy import text
import logging

def add_column():
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE ml_inferences ADD COLUMN anomaly_score FLOAT DEFAULT 0.0;"))
            print("Column anomaly_score added successfully.")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    add_column()
