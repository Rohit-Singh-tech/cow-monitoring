from app.api.endpoints.ingest import router as ingest_router
from app.api.endpoints.cows import router as cows_router
from app.api.endpoints.hardware import router as hardware_router
from app.api.endpoints.auth import router as auth_router

__all__ = ["ingest_router", "cows_router", "hardware_router", "auth_router"]
