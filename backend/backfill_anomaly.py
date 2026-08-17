import asyncio
from sqlalchemy import text
from app.database import SessionLocal
from app.ml.model_loader import get_ml_manager
from app.models.tag_registry import TagRegistry
from app.models.datalogger import DataloggerHeader, DataloggerPoint, MLInference

def backfill_anomaly_scores():
    db = SessionLocal()
    manager = get_ml_manager()
    try:
        # Get all devices
        devices = db.query(TagRegistry.device_id).all()
        for (dev_id,) in devices:
            dev_id = str(dev_id)
            print(f"Backfilling device {dev_id}...")
            
            # Get latest header for device
            header = db.query(DataloggerHeader).filter(
                DataloggerHeader.device_id == dev_id
            ).order_by(DataloggerHeader.id.desc()).first()
            
            if not header:
                continue
                
            # Get inference
            inference = db.query(MLInference).filter(
                MLInference.header_id == header.id
            ).first()
            
            if inference and (inference.anomaly_score is None or inference.anomaly_score == 0.0):
                # Fetch points
                points = db.query(DataloggerPoint).filter(
                    DataloggerPoint.header_id == header.id
                ).order_by(DataloggerPoint.point_index.asc()).all()
                
                if points:
                    x_buf = [p.x for p in points if p.x is not None]
                    y_buf = [p.y for p in points if p.y is not None]
                    z_buf = [p.z for p in points if p.z is not None]
                    
                    if len(x_buf) > 0:
                        pred = manager.predict(x_buf, y_buf, z_buf)
                        score = pred.get("anomaly_detection", {}).get("score", 0.0)
                        inference.anomaly_score = score
                        db.commit()
                        print(f"Updated {dev_id} anomaly_score to {score}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()
        print("Backfill complete.")

if __name__ == "__main__":
    backfill_anomaly_scores()
