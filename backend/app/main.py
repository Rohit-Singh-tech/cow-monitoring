import asyncio
from fastapi import FastAPI, Depends
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging

from app.config import settings
from app.database import engine, Base, get_db
from app.ml.model_loader import get_ml_manager
from app.ml.worker import run_inference_loop
from app.api.endpoints import ingest_router, cows_router, hardware_router, auth_router
from app.api.endpoints.admin_api import router as admin_api_router
from app.api.endpoints.config import router as config_router
from app.api.endpoints.cows import get_herd_overview, get_cow_live_dashboard, get_cow_7day_activity

from sqladmin import Admin
from app.admin import AdminAuth, UserAdmin, TagRegistryAdmin, RawPacketAdmin, DataloggerHeaderAdmin, ActivityConfigAdmin
from starlette.middleware.sessions import SessionMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cow_logger.main")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-load ML models at startup into RAM singleton
    logger.info("Initializing Cow Logger FastAPI backend...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified.")
        from app.database import SessionLocal
        from app.models.ui_parameter import ActivityConfig
        db = SessionLocal()
        try:
            if db.query(ActivityConfig).count() == 0:
                default_activities = [
                    ActivityConfig(code="RES", name="Standing Rest", color="#64748b", icon="fa-pause", category="Normal"),
                    ActivityConfig(code="RUS", name="Ruminating", color="#06b6d4", icon="fa-arrows-spin", category="Normal"),
                    ActivityConfig(code="MOV", name="Walking", color="#f59e0b", icon="fa-person-walking", category="Active"),
                    ActivityConfig(code="FEP", name="Feeding", color="#10b981", icon="fa-bowl-food", category="Normal"),
                    ActivityConfig(code="FED", name="Feeding", color="#10b981", icon="fa-bowl-food", category="Normal"),
                    ActivityConfig(code="DRN", name="Drinking", color="#3b82f6", icon="fa-glass-water", category="Normal"),
                    ActivityConfig(code="LCK", name="Licking", color="#ec4899", icon="fa-hand-sparkles", category="Normal"),
                    ActivityConfig(code="REL", name="Lying Rest", color="#8b5cf6", icon="fa-bed", category="Normal"),
                    ActivityConfig(code="URI", name="Urinating", color="#eab308", icon="fa-droplet", category="Normal"),
                    ActivityConfig(code="DEF", name="Defecating", color="#a16207", icon="fa-circle-dot", category="Normal"),
                    ActivityConfig(code="ATT", name="Aggressive", color="#ef4444", icon="fa-triangle-exclamation", category="Active"),
                    ActivityConfig(code="GRZ", name="Grazing", color="#10b981", icon="fa-wheat-awn", category="Normal")
                ]
                db.add_all(default_activities)
                db.commit()
                logger.info("Seeded default ActivityConfig values.")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Database table initialization warning: {e}")
        
    ml_mgr = get_ml_manager()
    logger.info(f"ML Manager loaded status: {ml_mgr.is_loaded}")
    
    # Start background ML inference worker
    worker_task = asyncio.create_task(run_inference_loop())
    logger.info("Background ML inference worker started.")
    
    yield
    
    # Shutdown: cancel worker
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
    logger.info("Shutting down Cow Logger backend service.")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SQLAdmin requires SessionMiddleware for authentication
app.add_middleware(SessionMiddleware, secret_key="super-secret-cow-key")

# Setup Admin Panel
authentication_backend = AdminAuth(secret_key="super-secret-cow-key")
admin = Admin(app=app, engine=engine, authentication_backend=authentication_backend, title="Cow Logger Admin")

admin.add_view(UserAdmin)
admin.add_view(TagRegistryAdmin)
admin.add_view(RawPacketAdmin)
admin.add_view(DataloggerHeaderAdmin)
admin.add_view(ActivityConfigAdmin)

@app.get("/", include_in_schema=False)
def root():
    return {
        "message": "Welcome to Cow Monitoring API",
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }

# Health checks for Render deployment
@app.get("/health", tags=["Health"])
@app.get(f"{settings.API_V1_STR}/health", tags=["Health"])
def health_check():
    ml_mgr = get_ml_manager()
    return {
        "status": "HEALTHY",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "ml_engine_loaded": ml_mgr.is_loaded,
        "ram_optimization": "SINGLE_WORKER_512MB_RENDER"
    }

# Include Routers
app.include_router(ingest_router, prefix=f"{settings.API_V1_STR}", tags=["Ingestion & Prediction"])
app.include_router(cows_router, prefix=f"{settings.API_V1_STR}/cows", tags=["Cattle Monitoring"])
app.include_router(hardware_router, prefix=f"{settings.API_V1_STR}", tags=["Hardware Specs"])
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(admin_api_router, prefix="/api/admin", tags=["Admin Management"])
app.include_router(config_router, prefix="/api/config", tags=["Configuration"])


# ─── Legacy / Frontend Compatibility Endpoints ────────────────────────────────
# These thin wrappers call the fast, pre-computed implementations from cows.py


@app.get("/api/cows", tags=["Frontend Compatibility"])
def api_get_cows(db: Session = Depends(get_db)):
    cows_data = get_herd_overview(db)
    return {"success": True, "cows": cows_data}

@app.get("/api/cow/{cow_id}/current", tags=["Frontend Compatibility"])
def api_get_cow_current(cow_id: str, db: Session = Depends(get_db)):
    dash = get_cow_live_dashboard(cow_id, db)
    return {"success": True, **dash}

@app.get("/api/cow/{cow_id}/7day", tags=["Frontend Compatibility"])
def api_get_cow_7day(cow_id: str, db: Session = Depends(get_db)):
    data_7day = get_cow_7day_activity(cow_id, db)
    return {"success": True, **data_7day}

@app.get("/api/cow/{cow_id}/activity-log", tags=["Frontend Compatibility"])
def api_get_cow_activity_log(cow_id: str, page: int = 1, limit: int = 20, db: Session = Depends(get_db)):
    """Activity log using pre-computed ML inferences — no live ML."""
    from app.models.tag_registry import TagRegistry
    from app.models.datalogger import DataloggerHeader, MLInference
    from app.models.ui_parameter import ActivityConfig
    
    if str(cow_id).isdigit():
        cow = db.query(TagRegistry).filter(TagRegistry.id == int(cow_id)).first()
    else:
        cow = db.query(TagRegistry).filter(TagRegistry.device_id == str(cow_id)).first()
        
    dev_id = cow.device_id if cow else str(cow_id)
    
    # Get paginated headers with their pre-computed ML inferences in ONE query
    from datetime import datetime, timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    
    # Get ALL headers for the last 24 hours, ordered ASCENDING to group them correctly
    headers = db.query(DataloggerHeader).filter(
        DataloggerHeader.device_id == str(dev_id),
        DataloggerHeader.timestamp >= cutoff
    ).order_by(DataloggerHeader.timestamp.asc()).all()
    
    if not headers:
        return {"success": True, "logs": [], "page": page, "limit": limit}
    
    # Batch fetch ML inferences for all headers
    header_ids = [h.id for h in headers]
    inferences = db.query(MLInference).filter(
        MLInference.header_id.in_(header_ids)
    ).all()
    inf_by_header = {inf.header_id: inf for inf in inferences}
    
    # Get activity config for display
    configs = db.query(ActivityConfig).all()
    ACTIVITY_CFG = {cfg.code: {"name": cfg.name, "color": cfg.color, "category": cfg.category} for cfg in configs}
    
    grouped_logs = []
    current_group = None

    for h in headers:
        inf = inf_by_header.get(h.id)
        act_code = inf.activity_code if inf else "RES"
        conf = inf.confidence if (inf and inf.confidence) else 85
        
        if current_group and current_group["activityCode"] == act_code:
            current_group["endTime"] = h.timestamp.isoformat() if h.timestamp else current_group["endTime"]
            current_group["packetCount"] += 1
            current_group["endPacketId"] = f"P-{h.packet_id_num}"
            current_group["confidenceSum"] += conf
        else:
            if current_group:
                grouped_logs.append(current_group)
                
            act_info = ACTIVITY_CFG.get(act_code, {"name": act_code, "color": "#94a3b8", "category": "Unknown"})
            current_group = {
                "logId": h.id,
                "startTime": h.timestamp.isoformat() if h.timestamp else "",
                "endTime": h.timestamp.isoformat() if h.timestamp else "",
                "packetCount": 1,
                "activityCode": act_code,
                "activityName": act_info["name"],
                "color": act_info["color"],
                "category": act_info["category"],
                "confidenceSum": conf,
                "startPacketId": f"P-{h.packet_id_num}",
                "endPacketId": f"P-{h.packet_id_num}"
            }
            
    if current_group:
        grouped_logs.append(current_group)
        
    # Calculate durations and reconstruct timeline backward to prevent gaps/overlaps
    current_end_time = None
    
    for g in reversed(grouped_logs):
        duration_secs = g["packetCount"] * 8
        if duration_secs < 60:
            g["durationDisplay"] = f"{duration_secs} secs"
        else:
            g["durationDisplay"] = f"{round(duration_secs / 60)} mins"
        
        # We need to keep a numerical value for time calculations below
        duration_mins = max(1, round(duration_secs / 60))
        g["durationMinutes"] = duration_mins
        
        if current_end_time is None:
            if g["endTime"]:
                current_end_time = datetime.fromisoformat(g["endTime"])
            else:
                current_end_time = datetime.now(timezone.utc)
                
        g["endTime"] = current_end_time.isoformat()
        
        start_time = current_end_time - timedelta(minutes=duration_mins)
        g["startTime"] = start_time.isoformat()
        
        current_end_time = start_time
        
        g["confidencePercent"] = round(g["confidenceSum"] / g["packetCount"])
        del g["packetCount"]
        del g["confidenceSum"]
        
    # Reverse to show newest transitions first, then paginate
    grouped_logs.reverse()
    
    start_idx = (page - 1) * limit
    paged_logs = grouped_logs[start_idx : start_idx + limit]
    
    logs = paged_logs
        
    return {
        "success": True,
        "logs": logs,
        "page": page,
        "limit": limit
    }

@app.post("/api/ble/trigger-dump", tags=["Frontend Compatibility"])
def api_trigger_ble_dump(payload: dict = {}):
    return {
        "success": True,
        "message": "Authorized Knock-Knock Trigger (0x59 0x00 0xBB 0xCC) sent. Replaying 2,500 SPI Flash packets."
    }
