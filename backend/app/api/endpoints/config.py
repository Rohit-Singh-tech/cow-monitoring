from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.ui_parameter import ActivityConfig

router = APIRouter()

DEFAULT_ACTIVITIES_MAP = {
    "RES": {"code": "RES", "name": "Standing Rest", "color": "#64748b", "icon": "fa-pause", "category": "Normal"},
    "RUS": {"code": "RUS", "name": "Ruminating", "color": "#06b6d4", "icon": "fa-arrows-spin", "category": "Normal"},
    "MOV": {"code": "MOV", "name": "Walking", "color": "#f59e0b", "icon": "fa-person-walking", "category": "Active"},
    "FEP": {"code": "FEP", "name": "Feeding", "color": "#10b981", "icon": "fa-bowl-food", "category": "Normal"},
    "FED": {"code": "FED", "name": "Feeding", "color": "#10b981", "icon": "fa-bowl-food", "category": "Normal"},
    "DRN": {"code": "DRN", "name": "Drinking", "color": "#3b82f6", "icon": "fa-glass-water", "category": "Normal"},
    "LCK": {"code": "LCK", "name": "Licking", "color": "#ec4899", "icon": "fa-hand-sparkles", "category": "Normal"},
    "REL": {"code": "REL", "name": "Lying Rest", "color": "#8b5cf6", "icon": "fa-bed", "category": "Normal"},
    "URI": {"code": "URI", "name": "Urinating", "color": "#eab308", "icon": "fa-droplet", "category": "Normal"},
    "DEF": {"code": "DEF", "name": "Defecating", "color": "#a16207", "icon": "fa-circle-dot", "category": "Normal"},
    "ATT": {"code": "ATT", "name": "Aggressive", "color": "#ef4444", "icon": "fa-triangle-exclamation", "category": "Active"},
    "GRZ": {"code": "GRZ", "name": "Grazing", "color": "#10b981", "icon": "fa-wheat-awn", "category": "Normal"},
    "OTH": {"code": "OTH", "name": "Other", "color": "#94a3b8", "icon": "fa-question", "category": "Normal"}
}

_ACTIVITIES_CACHE = None

@router.get("/activities")
def get_activities(db: Session = Depends(get_db)):
    global _ACTIVITIES_CACHE
    if _ACTIVITIES_CACHE:
        return {"success": True, "activities": _ACTIVITIES_CACHE}

    try:
        configs = db.query(ActivityConfig).all()
        if configs:
            activity_map = {}
            for cfg in configs:
                activity_map[cfg.code] = {
                    "code": cfg.code,
                    "name": cfg.name,
                    "color": cfg.color,
                    "icon": cfg.icon,
                    "category": cfg.category
                }
            _ACTIVITIES_CACHE = activity_map
            return {"success": True, "activities": activity_map}
    except Exception as e:
        pass

    return {"success": True, "activities": DEFAULT_ACTIVITIES_MAP}

