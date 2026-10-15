import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api import chat, donations, items
from .config import APP_VERSION, SERVICE_NAME, chat_mode, cors_origins, database_url
from .db import init_db, safe_database_url
from .logging_config import REQUEST_ID_HEADER, RequestLoggingMiddleware, configure_logging

LOG_LEVEL = configure_logging()
log = logging.getLogger(__name__)


def log_startup_report() -> None:
    """One block of log lines that answers 'what is this process running with?'."""
    _, db_source = database_url()
    origins, origins_source = cors_origins()
    log.info("Starting %s v%s (log level %s)", SERVICE_NAME, APP_VERSION, logging.getLevelName(LOG_LEVEL))
    log.info("Config comes from process environment variables; the backend does not read a .env file itself")
    log.info("Database URL: %s (source: %s)", safe_database_url(), db_source)
    log.info("CORS origins: %s (source: %s)", ",".join(origins), origins_source)
    if chat_mode() == "ai":
        model = os.getenv("OPENROUTER_MODEL", "").strip() or chat.DEFAULT_MODEL
        log.info("Chat mode: ai (OPENROUTER_API_KEY is set, model %s)", model)
    else:
        log.info("Chat mode: demo (OPENROUTER_API_KEY is not set)")
    available, detail = init_db()
    if available:
        log.info("Database: available")
    else:
        log.error("Database: UNAVAILABLE (%s); donations will answer 503, shop and chat keep working", detail)


@asynccontextmanager
async def lifespan(_: FastAPI):
    log_startup_report()
    yield
    log.info("Shutting down %s", SERVICE_NAME)


app = FastAPI(
    title="Online Orthodox Church API",
    version=APP_VERSION,
    description="Backend API for church shop, prayer requests, and pastoral services.",
    lifespan=lifespan,
)

_origins, _ = cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    # No cookies are used (only Bearer tokens), and "*" must not be combined with credentials.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[REQUEST_ID_HEADER],
)
# Added last = outermost, so preflight requests and error responses are logged and carry the request id too.
app.add_middleware(RequestLoggingMiddleware)


# Readable Russian texts for Pydantic's built-in (English) messages; custom validators already use Russian.
RU_MESSAGES = {
    "missing": "Обязательное поле.",
    "literal_error": "Недопустимое значение.",
    "string_type": "Ожидается строка.",
    "string_too_short": "Слишком короткое значение.",
    "string_too_long": "Слишком длинное значение.",
    "json_invalid": "Некорректный JSON в теле запроса.",
}


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """422 with readable messages and without echoing the submitted values (they may be card data)."""
    errors = []
    for err in exc.errors():
        kind = err.get("type", "")
        msg = RU_MESSAGES.get(kind) or str(err.get("msg", "Invalid value")).removeprefix("Value error, ")
        errors.append({"loc": list(err.get("loc", ())), "msg": msg, "type": kind})
    log.info("Validation failed for %s %s: fields=%s", request.method, request.url.path, [e["loc"][1:] for e in errors])
    return JSONResponse({"detail": errors}, status_code=422)


app.include_router(items.router)
app.include_router(chat.router)
app.include_router(donations.router)


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint for container readiness."""
    return {"status": "ok", "service": SERVICE_NAME}
