from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.ui_parameter import ActivityConfig

router = APIRouter()

@router.get("/activities")
def get_activities(db: Session = Depends(get_db)):
    configs = db.query(ActivityConfig).all()
    # Map them by code for easy frontend consumption
    activity_map = {}
    for cfg in configs:
        activity_map[cfg.code] = {
            "code": cfg.code,
            "name": cfg.name,
            "color": cfg.color,
            "icon": cfg.icon,
            "category": cfg.category
        }
    return {"success": True, "activities": activity_map}
