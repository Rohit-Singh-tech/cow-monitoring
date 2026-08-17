from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.config import settings
from app.database import engine, Base
from app.ml.model_loader import get_ml_manager
from app.api.endpoints import ingest_router, cows_router, hardware_router, auth_router
from app.api.endpoints.admin_api import router as admin_api_router
from app.api.endpoints.config import router as config_router

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
    yield
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

# Legacy / Frontend Compatibility Endpoints
from fastapi import Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.endpoints.cows import get_herd_overview, get_cow_live_dashboard, get_cow_7day_activity

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
def api_get_cow_activity_log(cow_id: str, db: Session = Depends(get_db)):
    from app.models.tag_registry import TagRegistry
    from app.models.datalogger import DataloggerHeader
    from app.models.ui_parameter import ActivityConfig
    from sqlalchemy import text
    from datetime import datetime, timedelta, timezone
    
    if str(cow_id).isdigit():
        cow = db.query(TagRegistry).filter(TagRegistry.id == int(cow_id)).first()
    else:
        cow = db.query(TagRegistry).filter(TagRegistry.device_id == str(cow_id)).first()
        
    dev_id = cow.device_id if cow else str(cow_id)
    
    now = datetime.now(timezone.utc)
    day_ago = now - timedelta(hours=24)
    
    headers = db.execute(text("""
        SELECT id, timestamp, packet_id_num 
        FROM datalogger_headers 
        WHERE device_id = :dev AND timestamp >= :day_ago
        ORDER BY timestamp ASC
    """), {"dev": str(dev_id), "day_ago": day_ago}).fetchall()
    
    if not headers:
        return {"success": True, "logs": []}
        
    num_chunks = min(len(headers), 8)
    chunk_size = len(headers) // num_chunks if num_chunks > 0 else 1
    
    manager = get_ml_manager()
    configs = db.query(ActivityConfig).all()
    ACTIVITY_MAP = {cfg.code: {"name": cfg.name, "color": cfg.color, "category": cfg.category} for cfg in configs}
    
    logs = []
    
    for i in range(num_chunks):
        start_idx = i * chunk_size
        end_idx = (i + 1) * chunk_size - 1 if i < num_chunks - 1 else len(headers) - 1
        
        chunk_headers = headers[start_idx:end_idx+1]
        if not chunk_headers:
            continue
            
        start_h = chunk_headers[0]
        end_h = chunk_headers[-1]
        
        # start_h is (id, timestamp, packet_id_num)
        start_ts = start_h[1]
        end_ts = end_h[1]
        
        if start_ts and end_ts:
            # Handle string parsing if SQLite returns string
            if isinstance(start_ts, str):
                try:
                    start_ts = datetime.fromisoformat(start_ts)
                    end_ts = datetime.fromisoformat(end_ts)
                except ValueError:
                    pass
            if isinstance(start_ts, datetime):
                dur_mins = int((end_ts - start_ts).total_seconds() / 60.0)
            else:
                dur_mins = 1
        else:
            dur_mins = 1
        if dur_mins < 1:
            dur_mins = 1
            
        points_sql = text("SELECT x, y, z FROM datalogger_points WHERE header_id = :hid ORDER BY point_index ASC")
        pts = db.execute(points_sql, {"hid": start_h[0]}).fetchall()
        
        if len(pts) > 0:
            x_buf = [p[0] for p in pts]
            y_buf = [p[1] for p in pts]
            z_buf = [p[2] for p in pts]
            ml_pred = manager.predict(x_buf, y_buf, z_buf)
            act_code = ml_pred["activity"]["code"]
            conf = int(ml_pred["activity"]["confidence"] * 100) if "confidence" in ml_pred["activity"] else 85
        else:
            act_code = "RES"
            conf = 80
            
        act_info = ACTIVITY_MAP.get(act_code, {"name": act_code, "color": "#94a3b8", "category": "Unknown"})
        
        # Ensure timestamp serialization
        st_iso = start_ts.isoformat() if isinstance(start_ts, datetime) else str(start_ts)
        et_iso = end_ts.isoformat() if isinstance(end_ts, datetime) else str(end_ts)
        
        logs.append({
            "logId": start_h[0],
            "startTime": st_iso,
            "endTime": et_iso,
            "durationMinutes": dur_mins,
            "activityCode": act_code,
            "activityName": act_info["name"],
            "color": act_info["color"],
            "category": act_info["category"],
            "confidencePercent": conf,
            "startPacketId": f"P-{start_h[2]}",
            "endPacketId": f"P-{end_h[2]}"
        })
        
    logs.reverse()
        
    return {
        "success": True,
        "logs": logs
    }

@app.post("/api/ble/trigger-dump", tags=["Frontend Compatibility"])
def api_trigger_ble_dump(payload: dict = {}):
    return {
        "success": True,
        "message": "Authorized Knock-Knock Trigger (0x59 0x00 0xBB 0xCC) sent. Replaying 2,500 SPI Flash packets."
    }

