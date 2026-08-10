from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class CowBase(BaseModel):
    device_id: str
    name: str
    breed: Optional[str] = "HF Crossbreed"
    location: Optional[str] = "Shed 1 - AWaDH Farm"
    weight: Optional[str] = "450 kg"
    notes: Optional[str] = None

class CowCreate(CowBase):
    pass

class CowResponse(CowBase):
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
