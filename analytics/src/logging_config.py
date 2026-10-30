"""Minimal logging setup for the analytics service (same format as the backend, see backend/app/logging_config.py).

LOG_LEVEL (env, default INFO) controls every logger under the `analytics` package.
"""
import contextvars
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s [%(request_id)s] %(message)s"
REQUEST_ID_HEADER = "X-Request-ID"

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
log = logging.getLogger(__name__)


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging(raw_level: str) -> int:
    """Attach one stream handler to the `analytics` logger. An unknown level falls back to INFO."""
    level = logging.getLevelName(raw_level.strip().upper())
    valid = isinstance(level, int)
    level = level if valid else logging.INFO
    logger = logging.getLogger("analytics")
    logger.setLevel(level)
    for handler in list(logger.handlers):
        if getattr(handler, "_church_handler", False):
            logger.removeHandler(handler)
    handler = logging.StreamHandler()
    handler._church_handler = True  # type: ignore[attr-defined]
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    handler.addFilter(RequestIdFilter())
    logger.addHandler(handler)
    logging.getLogger("uvicorn.access").disabled = True
    if not valid:
        log.warning("Unknown LOG_LEVEL %r, using INFO", raw_level)
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
                response = JSONResponse({"detail": "Internal server error."}, status_code=500)
            duration_ms = (time.perf_counter() - started) * 1000
            level = logging.WARNING if response.status_code >= 500 else logging.INFO
            log.log(
                level, "%s %s -> %s in %.1f ms", request.method, request.url.path, response.status_code, duration_ms
            )
            response.headers[REQUEST_ID_HEADER] = request_id
            return response
        finally:
            request_id_var.reset(token)
