"""Append-only activity (audit) log writer."""
from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from ..database import standalone_session
from ..models import ActivityLog

log = logging.getLogger("ayaka.audit")

EVENT_TYPES = {
    "auth.register": "Account created",
    "auth.login": "Signed in",
    "auth.logout": "Signed out",
    "auth.logout_all": "Signed out of all sessions",
    "auth.failed": "Failed authentication",
    "auth.session_revoked": "Session revoked",
    "key.created": "API key created",
    "key.updated": "API key updated",
    "key.revoked": "API key revoked",
    "key.deleted": "API key deleted",
    "key.regenerated": "API key regenerated",
    "key.enabled": "API key enabled",
    "key.disabled": "API key disabled",
    "profile.updated": "Profile updated",
    "password.changed": "Password changed",
    "settings.changed": "Settings changed",
}

SENSITIVE_KEYS = {"password", "current_password", "new_password", "confirm_password", "token", "key", "secret", "authorization"}


def client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()[:64]
    real = request.headers.get("x-real-ip")
    if real:
        return real[:64]
    return request.client.host[:64] if request.client else None


def user_agent(request: Request | None) -> str | None:
    if request is None:
        return None
    ua = request.headers.get("user-agent")
    return ua[:300] if ua else None


def _scrub(meta: dict[str, Any] | None) -> dict[str, Any]:
    if not meta:
        return {}
    return {k: v for k, v in meta.items() if k.lower() not in SENSITIVE_KEYS}


def record(db: Session, user_id: uuid.UUID, event_type: str, description: str | None = None,
           metadata: dict | None = None, request: Request | None = None) -> None:
    """Add an audit entry inside the caller's transaction."""
    db.add(ActivityLog(
        user_id=user_id,
        event_type=event_type,
        description=(description or EVENT_TYPES.get(event_type, event_type))[:500],
        metadata_=_scrub(metadata),
        ip_address=client_ip(request),
        user_agent=user_agent(request),
    ))


def record_detached(user_id: uuid.UUID, event_type: str, description: str | None = None,
                    metadata: dict | None = None, request: Request | None = None) -> None:
    """Write in an independent transaction (survives the caller's rollback)."""
    try:
        with standalone_session() as db:
            record(db, user_id, event_type, description, metadata, request)
    except Exception:  # never break the request because of audit write problems
        log.exception("failed to write audit event %s", event_type)
