"""Central logging setup and the request-logging middleware.

LOG_LEVEL (env, default INFO) controls the verbosity of every logger under the `backend` package.
Every log line carries the id of the HTTP request it belongs to, so one request can be followed
across modules. Never log secrets, card data or full user messages here: log lengths and ids instead.
"""
import contextvars
import logging
import os
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s [%(request_id)s] %(message)s"
REQUEST_ID_HEADER = "X-Request-ID"
PACKAGE_LOGGER = "backend"

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
log = logging.getLogger(__name__)


class RequestIdFilter(logging.Filter):
    """Copies the current request id onto every record so the format string can print it."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def resolve_log_level(raw: str | None) -> tuple[int, bool]:
    """Return (level, ok). An unknown name falls back to INFO with ok=False."""
    name = (raw or "INFO").strip().upper()
    level = logging.getLevelName(name)
    if isinstance(level, int):
        return level, True
    return logging.INFO, False


def configure_logging() -> int:
    """Attach one stream handler to the `backend` logger. Safe to call more than once."""
    level, ok = resolve_log_level(os.getenv("LOG_LEVEL"))
    logger = logging.getLogger(PACKAGE_LOGGER)
    logger.setLevel(level)
    for handler in list(logger.handlers):
        if getattr(handler, "_church_handler", False):
            logger.removeHandler(handler)
    handler = logging.StreamHandler()
    handler._church_handler = True  # type: ignore[attr-defined]
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.addFilter(RequestIdFilter())
    logger.addHandler(handler)
    # httpx logs every outgoing URL at INFO; chat.py logs the OpenRouter call itself.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    # Our middleware already writes one access line per request.
    logging.getLogger("uvicorn.access").disabled = True
    if not ok:
        log.warning("Unknown LOG_LEVEL %r, using INFO", os.getenv("LOG_LEVEL"))
    return level


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs method, path, status and duration of each request and returns X-Request-ID."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = uuid.uuid4().hex[:8]
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            try:
                response = await call_next(request)
            except Exception:
                log.exception("Unhandled error in %s %s", request.method, request.url.path)
                response = JSONResponse({"detail": "Внутренняя ошибка сервера."}, status_code=500)
            duration_ms = (time.perf_counter() - started) * 1000
            level = logging.WARNING if response.status_code >= 500 else logging.INFO
            log.log(
                level, "%s %s -> %s in %.1f ms", request.method, request.url.path, response.status_code, duration_ms
            )
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            request_id_var.reset(token)
