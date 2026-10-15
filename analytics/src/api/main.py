import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from analytics.src.api.routes.metrics import engine
from analytics.src.api.routes.metrics import router as metrics_router
from analytics.src.config import settings
from analytics.src.logging_config import REQUEST_ID_HEADER, RequestLoggingMiddleware, configure_logging

APP_VERSION = "1.1.0"
SERVICE_NAME = "church-analytics-api"

configure_logging(settings.LOG_LEVEL)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info("Starting %s v%s (environment %s, log level %s)", SERVICE_NAME, APP_VERSION, settings.ENVIRONMENT,
             settings.LOG_LEVEL.upper())
    log.info("Config comes from process environment variables (and a .env file in the working directory, if any)")
    log.info("Database URL: %s", settings.safe_database_url)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        log.info("Database: available")
    except Exception as exc:
        log.error("Database: UNAVAILABLE (%s); analytics endpoints will answer 503", type(exc).__name__)
    yield
    log.info("Shutting down %s", SERVICE_NAME)


app = FastAPI(
    title="Online Church Analytics Service",
    version=APP_VERSION,
    description="DWH serving layer providing financial and parishioner activity metrics.",
    lifespan=lifespan,
)

_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[REQUEST_ID_HEADER],
)
app.add_middleware(RequestLoggingMiddleware)

app.include_router(metrics_router)


@app.get("/health", tags=["System"])
async def health_check():
    """Analytics service health check."""
    return {"status": "ok", "service": SERVICE_NAME}
