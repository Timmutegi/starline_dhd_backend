from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging
from app.core.config import settings
from app.core.database import engine, Base
from app.middleware.audit_middleware import AuditMiddleware
from app.api.v1.auth import login, logout, password
from app.api.v1.users import crud as user_crud
from app.api.v1.clients import router as client_router
from app.api.v1.staff import router as staff_router
from app.api.v1.roles import router as roles_router
from app.api.v1.scheduling import router as scheduling_router
from app.api.v1.scheduling import time_clock, appointments, availability, calendar
from app.api.v1 import dashboard, documentation, notifications, tasks, admin, audit

# Import all models to ensure they're registered with SQLAlchemy before table creation
from app.models import (
    user, client, staff, scheduling, task as task_model,
    vitals_log, shift_note, incident_report, notification as notification_model,
    audit_log, meal_log, activity_log
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up Starline Backend...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified")
    yield
    logger.info("Shutting down...")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Add audit middleware for HIPAA compliance
app.add_middleware(
    AuditMiddleware,
    exclude_paths=["/docs", "/openapi.json", "/health", "/favicon.ico", "/", "/redoc"]
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "status_code": 500}
    )

@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.VERSION,
        "status": "running",
        "documentation": f"{settings.API_V1_STR}/docs"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "database": "connected",
        "version": settings.VERSION
    }

app.include_router(
    login.router,
    prefix=f"{settings.API_V1_STR}/auth",
    tags=["Authentication"]
)

app.include_router(
    logout.router,
    prefix=f"{settings.API_V1_STR}/auth",
    tags=["Authentication"]
)

app.include_router(
    password.router,
    prefix=f"{settings.API_V1_STR}/auth",
    tags=["Authentication"]
)

app.include_router(
    user_crud.router,
    prefix=f"{settings.API_V1_STR}/users",
    tags=["Users"]
)

app.include_router(
    client_router.router,
    prefix=f"{settings.API_V1_STR}/clients",
    tags=["Clients"]
)

app.include_router(
    staff_router.router,
    prefix=f"{settings.API_V1_STR}/staff",
    tags=["Staff Management"]
)

app.include_router(
    roles_router.router,
    prefix=f"{settings.API_V1_STR}/roles",
    tags=["Role Management"]
)

app.include_router(
    scheduling_router.router,
    prefix=f"{settings.API_V1_STR}/scheduling",
    tags=["Scheduling"]
)

app.include_router(
    time_clock.router,
    prefix=f"{settings.API_V1_STR}/scheduling/time-clock",
    tags=["Time Clock"]
)

app.include_router(
    appointments.router,
    prefix=f"{settings.API_V1_STR}/scheduling/appointments",
    tags=["Appointments"]
)

app.include_router(
    availability.router,
    prefix=f"{settings.API_V1_STR}/scheduling/availability",
    tags=["Staff Availability"]
)

app.include_router(
    calendar.router,
    prefix=f"{settings.API_V1_STR}/scheduling/calendar",
    tags=["Calendar"]
)

app.include_router(
    dashboard.router,
    prefix=f"{settings.API_V1_STR}/dashboard",
    tags=["Dashboard"]
)

app.include_router(
    documentation.router,
    prefix=f"{settings.API_V1_STR}/documentation",
    tags=["Documentation"]
)

app.include_router(
    notifications.router,
    prefix=f"{settings.API_V1_STR}/notifications",
    tags=["Notifications"]
)

app.include_router(
    tasks.router,
    prefix=f"{settings.API_V1_STR}/tasks",
    tags=["Tasks"]
)

app.include_router(
    admin.router,
    prefix=f"{settings.API_V1_STR}/admin",
    tags=["Admin"]
)

app.include_router(
    audit.router,
    prefix=f"{settings.API_V1_STR}"
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,
        log_level="info"
    )