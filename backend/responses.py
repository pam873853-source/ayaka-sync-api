"""Consistent JSON envelopes and application errors."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ok(data: Any = None, message: str = "Request successful", status_code: int = 200,
       meta: dict | None = None, headers: dict | None = None) -> JSONResponse:
    body = {
        "success": True,
        "message": message,
        "data": data if data is not None else {},
        "meta": {"timestamp": now_iso(), **(meta or {})},
    }
    return JSONResponse(jsonable_encoder(body), status_code=status_code, headers=headers)


def error_body(code: str, message: str, details: Any = None, request_id: str | None = None) -> dict:
    err: dict[str, Any] = {"code": code}
    if details is not None:
        err["details"] = details
    meta: dict[str, Any] = {"timestamp": now_iso()}
    if request_id:
        meta["request_id"] = request_id
    return {"success": False, "message": message, "error": err, "meta": meta}


class AppError(Exception):
    """Raise anywhere to return a consistent error response."""

    def __init__(self, status_code: int, code: str, message: str, details: Any = None,
                 headers: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers or {}


# Convenience constructors -------------------------------------------------
def auth_required(msg: str = "Authentication required") -> AppError:
    return AppError(401, "AUTHENTICATION_REQUIRED", msg)


def permission_denied(msg: str = "You do not have permission to perform this action") -> AppError:
    return AppError(403, "PERMISSION_DENIED", msg)


def not_found(msg: str = "Resource not found") -> AppError:
    return AppError(404, "RESOURCE_NOT_FOUND", msg)


def validation(msg: str, details: Any = None) -> AppError:
    return AppError(422, "VALIDATION_ERROR", msg, details)


def conflict(code: str, msg: str) -> AppError:
    return AppError(409, code, msg)
