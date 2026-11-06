from fastapi import Depends, FastAPI, HTTPException
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.db.database import engine
from app.core.config import settings
from app.core.request_guard import RequestGuardMiddleware
from app.core.observability import ObservabilityMiddleware, start_logging, stop_logging
from app.routers.operations import router as operations_router
from app.core.security import get_current_user
from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.permissions import router as permissions_router
from app.routers.settings import router as settings_router
from app.routers.access import router as access_router
from app.routers.leads import router as leads_router
from app.routers.customers import router as customers_router
from app.routers.followups import router as followups_router
from app.routers.quotations import router as quotations_router
from app.routers.reports import router as reports_router
from app.routers.workspace import router as workspace_router
from app.routers.customer_links import router as customer_links_router

@asynccontextmanager
async def lifespan(app):
    logging_enabled = start_logging()
    try:
        yield
    finally:
        stop_logging(logging_enabled)


app = FastAPI(
    title="ENGEN CRM API",
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(permissions_router)
app.include_router(settings_router)
app.include_router(access_router)
app.include_router(operations_router)
app.include_router(leads_router, dependencies=[Depends(get_current_user)])
app.include_router(customers_router, dependencies=[Depends(get_current_user)])
app.include_router(followups_router, dependencies=[Depends(get_current_user)])
app.include_router(quotations_router, dependencies=[Depends(get_current_user)])
app.include_router(customer_links_router, dependencies=[Depends(get_current_user)])
app.include_router(workspace_router, dependencies=[Depends(get_current_user)])
app.include_router(reports_router, dependencies=[Depends(get_current_user)])
app.add_middleware(RequestGuardMiddleware)
app.add_middleware(ObservabilityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After", "X-Request-ID"],
)


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "message": "ENGEN CRM API is running"
    }


@app.get("/api/db-health", dependencies=[Depends(get_current_user)])
def database_health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return {
            "database": "connected",
            "status": "success"
        }

    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database is unavailable")
