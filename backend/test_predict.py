import os
import sys
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.ml.model_loader import get_ml_manager

def test_predict():
    manager = get_ml_manager()
    print("Models loaded. Running predict...")
    x = [0.0] * 80
    y = [0.0] * 80
    z = [0.0] * 80
    
    t0 = time.time()
    res = manager.predict(x, y, z)
    t1 = time.time()
    
    print(f"Prediction took {t1 - t0:.4f} seconds")

if __name__ == "__main__":
    test_predict()
