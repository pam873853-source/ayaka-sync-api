"""API key lifecycle: create, verify, serialize, regenerate."""
from __future__ import annotations

import hmac
import re
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import security
from ..models import PERMISSIONS, ApiKey, User
from ..responses import AppError


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def effective_status(key: ApiKey, now: datetime | None = None) -> str:
    now = now or utcnow()
    if key.status == "revoked":
        return "revoked"
    if key.expires_at is not None and key.expires_at <= now:
        return "expired"
    if key.status == "disabled":
        return "disabled"
    return "active"


def serialize(key: ApiKey) -> dict:
    """Public representation. Never includes key_hash or the full secret."""
    return {
        "id": str(key.id),
        "name": key.name,
        "description": key.description,
        "key_prefix": key.key_prefix,
        "masked_key": f"{key.key_prefix}{'•' * 8}",
        "environment": key.environment,
        "permissions": sorted(key.permissions, key=PERMISSIONS.index),
        "allowed_endpoints": key.allowed_endpoints or [],
        "status": effective_status(key),
        "rate_limit": key.rate_limit,
        "expires_at": key.expires_at,
        "last_used_at": key.last_used_at,
        "created_at": key.created_at,
        "updated_at": key.updated_at,
        "revoked_at": key.revoked_at,
    }


def create(db: Session, user: User, *, name: str, description: str, environment: str,
           permissions: list[str], rate_limit: int, expires_at: datetime | None,
           allowed_endpoints: list[str]) -> tuple[ApiKey, str]:
    full, prefix, digest = security.generate_api_key(environment)
    key = ApiKey(
        user_id=user.id, name=name, description=description, key_prefix=prefix, key_hash=digest,
        environment=environment, permissions=permissions, allowed_endpoints=allowed_endpoints,
        status="active", rate_limit=rate_limit, expires_at=expires_at,
    )
    db.add(key)
    db.flush()
    db.refresh(key)
    return key, full


def regenerate(db: Session, key: ApiKey) -> str:
    full, prefix, digest = security.generate_api_key(key.environment)
    key.key_prefix = prefix
    key.key_hash = digest
    key.updated_at = utcnow()
    key.last_used_at = None
    db.flush()
    return full


def get_owned(db: Session, user_id: uuid.UUID, key_id: str) -> ApiKey:
    try:
        kid = uuid.UUID(str(key_id))
    except ValueError:
        raise AppError(404, "RESOURCE_NOT_FOUND", "API key not found")
    key = db.execute(select(ApiKey).where(ApiKey.id == kid, ApiKey.user_id == user_id)).scalar_one_or_none()
    if key is None:  # same response whether it doesn't exist or belongs to someone else
        raise AppError(404, "RESOURCE_NOT_FOUND", "API key not found")
    return key


def default_expiry(days: int) -> datetime | None:
    return utcnow() + timedelta(days=days) if days and days > 0 else None


# ------------------------------------------------------------- verification
def verify(db: Session, presented: str) -> tuple[ApiKey, User]:
    """Resolve a presented API key or raise an AppError with a precise code."""
    if not presented or not security.looks_like_api_key(presented):
        raise AppError(401, "INVALID_API_KEY", "Invalid API key")
    digest = security.hash_api_key(presented)
    key = db.execute(select(ApiKey).where(ApiKey.key_hash == digest)).scalar_one_or_none()
    if key is None or not hmac.compare_digest(key.key_hash, digest):
        raise AppError(401, "INVALID_API_KEY", "Invalid API key")
    # The environment prefix must match the key's environment.
    if not presented.startswith(security.ENV_PREFIX[key.environment]):
        raise AppError(401, "INVALID_API_KEY", "Invalid API key")
    user = db.get(User, key.user_id)
    if user is None or not user.is_active:
        raise AppError(401, "INVALID_API_KEY", "Invalid API key")
    status = effective_status(key)
    err = None
    if status == "revoked":
        err = AppError(401, "API_KEY_REVOKED", "This API key has been revoked")
    elif status == "expired":
        err = AppError(401, "API_KEY_EXPIRED", "This API key has expired")
    elif status == "disabled":
        err = AppError(403, "API_KEY_DISABLED", "This API key is disabled")
    if err is not None:
        err.owner_id = key.user_id  # lets the caller write a "failed authentication" audit entry
        raise err
    return key, user


def _pattern_to_regex(pattern: str) -> re.Pattern:
    # "/api/v1/records/*" matches the collection itself and everything below it.
    if pattern.endswith("/*"):
        base = _pattern_to_regex(pattern[:-2]).pattern[1:-3]
        return re.compile("^" + base + "(/.*)?$")
    out = ""
    for part in re.split(r"(\*|\{[^}]+\})", pattern):
        if part == "*":
            out += ".*"
        elif part.startswith("{") and part.endswith("}"):
            out += "[^/]+"
        else:
            out += re.escape(part)
    return re.compile("^" + out.rstrip("/") + "/?$")


def endpoint_allowed(key: ApiKey, path: str) -> bool:
    patterns = key.allowed_endpoints or []
    if not patterns:
        return True
    return any(_pattern_to_regex(p).match(path) for p in patterns)
