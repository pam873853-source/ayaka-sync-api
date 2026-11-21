"""Request context, security headers, usage tracking and error handlers."""
from __future__ import annotations

import logging
import os
import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

from .config import get_settings
from .database import DatabaseNotConfigured
from .responses import AppError, error_body
from .security import new_request_id
from .services import audit_service, usage_service

log = logging.getLogger("ayaka.http")

API_CSP = "default-src 'none'; frame-ancestors 'none'"
DOCS_CSP = (
    "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com; "
    "frame-ancestors 'none'"
)


def page_csp() -> str:
    frame = os.getenv("FRAME_ANCESTORS", "'none'")
    return (
        "default-src 'self'; "
        "script-src 'self' https://cdn.jsdelivr.net https://unpkg.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data:; connect-src 'self'; "
        f"frame-ancestors {frame}; base-uri 'self'; form-action 'self'"
    )


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = new_request_id()
        request.state.request_id = request_id
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:  # last-resort guard: never leak a stack trace
            log.exception("unhandled error on %s %s", request.method, request.url.path)
            response = JSONResponse(
                error_body("INTERNAL_SERVER_ERROR", "An unexpected error occurred", request_id=request_id),
                status_code=500,
            )
        elapsed_ms = int((time.perf_counter() - start) * 1000)

        path = request.url.path
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        if os.getenv("FRAME_ANCESTORS", "'none'") == "'none'":
            response.headers["X-Frame-Options"] = "DENY"
        if get_settings().is_production:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        if path.startswith("/api/docs") or path.startswith("/api/redoc"):
            response.headers["Content-Security-Policy"] = DOCS_CSP
        elif path.startswith("/api/"):
            response.headers["Content-Security-Policy"] = API_CSP
            response.headers.setdefault("Cache-Control", "no-store")
        else:
            response.headers["Content-Security-Policy"] = page_csp()

        for k, v in (getattr(request.state, "rate_headers", None) or {}).items():
            response.headers[k] = v

        usage = getattr(request.state, "usage", None)
        if usage:
            await run_in_threadpool(usage_service.record, {
                **usage,
                "request_id": request_id,
                "endpoint": path[:255],
                "method": request.method,
                "status_code": response.status_code,
                "response_time_ms": elapsed_ms,
                "ip_address": audit_service.client_ip(request),
                "user_agent": audit_service.user_agent(request),
            })
        return response


def _rid(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return JSONResponse(error_body(exc.code, exc.message, exc.details, _rid(request)),
                            status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        details = []
        for e in exc.errors():
            loc = [str(p) for p in e.get("loc", []) if p not in ("body", "query", "path")]
            msg = str(e.get("msg", "Invalid value")).removeprefix("Value error, ")
            details.append({"field": ".".join(loc) or None, "message": msg})
        first = details[0]["message"] if details else "Invalid request"
        return JSONResponse(error_body("VALIDATION_ERROR", first, details, _rid(request)), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        codes = {404: "RESOURCE_NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 401: "AUTHENTICATION_REQUIRED",
                 403: "PERMISSION_DENIED"}
        code = codes.get(exc.status_code, "HTTP_ERROR")
        message = "Resource not found" if exc.status_code == 404 else str(exc.detail)
        return JSONResponse(error_body(code, message, request_id=_rid(request)), status_code=exc.status_code)

    @app.exception_handler(DatabaseNotConfigured)
    async def _db_missing(request: Request, exc: DatabaseNotConfigured):
        return JSONResponse(error_body("DATABASE_NOT_CONFIGURED",
                                       "Database is not configured. Set DATABASE_URL.", request_id=_rid(request)),
                            status_code=503)

    @app.exception_handler(OperationalError)
    async def _db_down(request: Request, exc: OperationalError):
        log.error("database unavailable: %s", type(exc).__name__)
        return JSONResponse(error_body("DATABASE_UNAVAILABLE", "Database is temporarily unavailable",
                                       request_id=_rid(request)), status_code=503)

    @app.exception_handler(DBAPIError)
    async def _db_error(request: Request, exc: DBAPIError):
        log.error("database error: %s", type(exc.orig).__name__ if exc.orig else type(exc).__name__)
        return JSONResponse(error_body("INTERNAL_SERVER_ERROR", "An unexpected error occurred",
                                       request_id=_rid(request)), status_code=500)
