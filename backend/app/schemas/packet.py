from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class XYZSample(BaseModel):
    x: int
    y: int
    z: int

class SensorPacketIngest(BaseModel):
    app_id: str = Field(default="cow_logger_collar", example="cow_logger_collar")
    device_id: str = Field(example="COW-BLE-001")
    timestamp: Optional[str] = None
    samples: List[XYZSample] = Field(..., description="Array of XYZ accelerometer readings (10 Hz)")

class PredictRequest(BaseModel):
    device_id: str = Field(default="COW-BLE-001")
    x: List[float] = Field(..., description="Array of X-axis accelerometer samples")
    y: List[float] = Field(..., description="Array of Y-axis accelerometer samples")
    z: List[float] = Field(..., description="Array of Z-axis accelerometer samples")

class RawPacketIngest(BaseModel):
    payload: Dict[str, Any]
    status: Optional[str] = "pending"
