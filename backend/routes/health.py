"""Health and configuration status."""
from __future__ import annotations

import time

from fastapi import APIRouter, Request

from ..config import get_settings
from ..database import DatabaseNotConfigured, ping
from ..responses import AppError, ok
from ..services import usage_service
from ..urls import public_base_url

router = APIRouter(prefix="/api/v1/health", tags=["health"])
STARTED = time.time()


@router.get("")
def health(request: Request):
    s = get_settings()
    return ok({
        "status": "ok",
        "app": s.app_name,
        "environment": s.app_env,
        "base_url": public_base_url(request),
        "base_url_source": s.base_url_source,
        "uptime_seconds": int(time.time() - STARTED),
        "configuration": {
            "database_url": "DATABASE_URL" not in s.missing_secrets,
            "jwt_secret": "JWT_SECRET" not in s.missing_secrets,
            "api_key_pepper": "API_KEY_PEPPER" not in s.missing_secrets,
            "app_base_url": s.base_url_source == "env",
            "missing": s.missing_secrets,
        },
        "usage_logging": usage_service.health(),
    }, "Service is running")


@router.get("/database")
def database_health():
    start = time.perf_counter()
    try:
        info = ping()
    except DatabaseNotConfigured:
        raise AppError(503, "DATABASE_NOT_CONFIGURED", "DATABASE_URL is not configured")
    except Exception as exc:
        raise AppError(503, "DATABASE_UNAVAILABLE", f"Database connection failed ({type(exc).__name__})")
    return ok({"status": "ok", "latency_ms": round((time.perf_counter() - start) * 1000, 1), **info},
              "Database reachable")
