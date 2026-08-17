import os
import sys
import time
from sqlalchemy import create_engine
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from main import app

def profile_api():
    client = TestClient(app)
    
    print("Sending request to /api/cow/9/live...")
    t0 = time.time()
    res = client.get("/api/cow/9/live")
    t1 = time.time()
    
    print(f"Status: {res.status_code}")
    print(f"Time taken: {t1 - t0:.4f} seconds")

if __name__ == "__main__":
    profile_api()
