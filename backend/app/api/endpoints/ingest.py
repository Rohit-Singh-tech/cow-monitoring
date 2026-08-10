from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
import json

from app.database import get_db
from app.schemas.packet import SensorPacketIngest, PredictRequest, RawPacketIngest
from app.models.datalogger import SensorPacket, RawPacket, DataloggerHeader, DataloggerPoint
from app.ml.model_loader import get_ml_manager

router = APIRouter()

@router.post("/predict")
def predict_xyz(payload: PredictRequest):
    """
    Run 78-feature extraction and XGBoost inference on provided XYZ raw accelerometer data.
    """
    if len(payload.x) == 0 or len(payload.y) == 0 or len(payload.z) == 0:
        raise HTTPException(status_code=400, detail="X, Y, and Z sample arrays must be non-empty.")
        
    manager = get_ml_manager()
    result = manager.predict(payload.x, payload.y, payload.z)
    result["device_id"] = payload.device_id
    result["samples_count"] = len(payload.x)
    return result

@router.post("/ingest/packet")
def ingest_sensor_packet(payload: SensorPacketIngest, db: Session = Depends(get_db)):
    """
    Ingest a telemetry packet containing XYZ accelerometer samples, store into database,
    and automatically compute ML activity & heat predictions.
    """
    # Store packet into sensor_packets table
    packet_entry = SensorPacket(
        app_id=payload.app_id,
        data={
            "device_id": payload.device_id,
            "samples_count": len(payload.samples),
            "samples": [s.model_dump() for s in payload.samples]
        }
    )
    db.add(packet_entry)
    db.commit()
    db.refresh(packet_entry)

    # Extract XYZ arrays
    x_vals = [s.x for s in payload.samples]
    y_vals = [s.y for s in payload.samples]
    z_vals = [s.z for s in payload.samples]

    # Run ML prediction
    manager = get_ml_manager()
    ml_prediction = manager.predict(x_vals, y_vals, z_vals)

    return {
        "status": "INGESTED_SUCCESS",
        "packet_id": packet_entry.id,
        "device_id": payload.device_id,
        "samples_ingested": len(payload.samples),
        "ml_inference": ml_prediction
    }

@router.post("/ingest/raw")
def ingest_raw_packet(payload: RawPacketIngest, db: Session = Depends(get_db)):
    """
    Ingest unparsed raw BLE replay packet payload into database queue.
    """
    raw_entry = RawPacket(
        payload=payload.payload,
        status=payload.status or "pending",
        processed_at=datetime.utcnow()
    )
    db.add(raw_entry)
    db.commit()
    db.refresh(raw_entry)

    return {
        "status": "RAW_PACKET_QUEUED",
        "raw_packet_id": raw_entry.id
    }
