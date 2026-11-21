"""API key management endpoints."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from .. import security
from ..database import get_db
from ..dependencies import Principal, require_access, require_session
from ..models import ApiKey, ApiUsage
from ..responses import AppError, ok, validation
from ..schemas import ApiKeyCreate, ApiKeyUpdate
from ..services import audit_service, key_service, settings_service

router = APIRouter(prefix="/api/v1/keys", tags=["api-keys"])
MAX_KEYS_PER_USER = 50


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _require_password_for_admin(principal: Principal, requested: list[str] | None, current: list[str],
                                password: str | None) -> None:
    """Escalating to the admin permission requires re-authentication."""
    if requested and "admin" in requested and "admin" not in current:
        if not password or not security.verify_password(password, principal.user.password_hash):
            raise AppError(403, "PERMISSION_DENIED",
                           "Granting the admin permission requires your current password")


def _status_clause(status: str, now: datetime):
    if status == "revoked":
        return ApiKey.status == "revoked"
    if status == "expired":
        return and_(ApiKey.status != "revoked", ApiKey.expires_at.is_not(None), ApiKey.expires_at <= now)
    not_expired = or_(ApiKey.expires_at.is_(None), ApiKey.expires_at > now)
    if status == "disabled":
        return and_(ApiKey.status == "disabled", not_expired)
    return and_(ApiKey.status == "active", not_expired)


@router.get("")
def list_keys(
    search: str | None = Query(None, max_length=80),
    environment: str | None = Query(None, pattern="^(development|production)$"),
    status: str | None = Query(None, pattern="^(active|expired|revoked|disabled)$"),
    sort: str = Query("created_desc", pattern="^(created_desc|created_asc|name|last_used)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    principal: Principal = Depends(require_access("admin")),
    db: Session = Depends(get_db),
):
    now = utcnow()
    conds = [ApiKey.user_id == principal.user.id]
    if search:
        like = f"%{search.strip().lower()}%"
        conds.append(or_(func.lower(ApiKey.name).like(like), func.lower(ApiKey.key_prefix).like(like)))
    if environment:
        conds.append(ApiKey.environment == environment)
    if status:
        conds.append(_status_clause(status, now))
    order = {
        "created_desc": ApiKey.created_at.desc(),
        "created_asc": ApiKey.created_at.asc(),
        "name": func.lower(ApiKey.name).asc(),
        "last_used": ApiKey.last_used_at.desc().nulls_last(),
    }[sort]
    total = db.execute(select(func.count()).select_from(ApiKey).where(*conds)).scalar_one()
    rows = db.execute(select(ApiKey).where(*conds).order_by(order, ApiKey.id)
                      .offset((page - 1) * per_page).limit(per_page)).scalars().all()
    counts = dict(db.execute(
        select(ApiKey.environment, func.count()).where(ApiKey.user_id == principal.user.id)
        .group_by(ApiKey.environment)).all())
    return ok([key_service.serialize(k) for k in rows], meta={
        "page": page, "per_page": per_page, "total": total,
        "total_pages": max(1, math.ceil(total / per_page)),
        "counts": {"development": counts.get("development", 0), "production": counts.get("production", 0)},
    })


@router.post("", status_code=201)
def create_key(payload: ApiKeyCreate, request: Request, principal: Principal = Depends(require_session),
               db: Session = Depends(get_db)):
    user = principal.user
    existing = db.execute(select(func.count()).select_from(ApiKey).where(
        ApiKey.user_id == user.id, ApiKey.status != "revoked")).scalar_one()
    if existing >= MAX_KEYS_PER_USER:
        raise validation(f"You can have at most {MAX_KEYS_PER_USER} non-revoked API keys")
    _require_password_for_admin(principal, payload.permissions, [], payload.current_password)

    prefs = settings_service.get_all(db, user.id)
    environment = payload.environment or prefs["default_environment"]
    rate_limit = payload.rate_limit or int(prefs["default_rate_limit"])
    expires_at = payload.expires_at or key_service.default_expiry(int(prefs["default_key_expiration_days"]))

    key, full = key_service.create(
        db, user, name=payload.name, description=payload.description, environment=environment,
        permissions=list(payload.permissions), rate_limit=rate_limit, expires_at=expires_at,
        allowed_endpoints=payload.allowed_endpoints,
    )
    audit_service.record(db, user.id, "key.created", f"API key \u201c{key.name}\u201d created", {
        "key_id": str(key.id), "key_prefix": key.key_prefix, "environment": key.environment,
        "permissions": key.permissions,
    }, request)
    db.commit()
    data = key_service.serialize(key)
    data["secret"] = full  # returned exactly once; only its HMAC is stored
    return ok(data, "API key created. Copy it now — it will not be shown again.", status_code=201)


@router.get("/{key_id}")
def get_key(key_id: str, principal: Principal = Depends(require_access("admin")), db: Session = Depends(get_db)):
    key = key_service.get_owned(db, principal.user.id, key_id)
    since = utcnow() - timedelta(days=30)
    total, failed, avg_rt = db.execute(
        select(func.count(), func.count().filter(ApiUsage.status_code >= 400),
               func.coalesce(func.avg(ApiUsage.response_time_ms), 0))
        .where(ApiUsage.api_key_id == key.id, ApiUsage.created_at >= since)
    ).one()
    data = key_service.serialize(key)
    data["usage_30d"] = {"total": total, "failed": failed, "successful": total - failed,
                         "avg_response_time_ms": round(float(avg_rt), 1)}
    return ok(data)


@router.patch("/{key_id}")
def update_key(key_id: str, payload: ApiKeyUpdate, request: Request,
               principal: Principal = Depends(require_session), db: Session = Depends(get_db)):
    key = key_service.get_owned(db, principal.user.id, key_id)
    if key.status == "revoked":
        raise AppError(409, "API_KEY_REVOKED", "Revoked keys cannot be modified")
    _require_password_for_admin(principal, payload.permissions, key.permissions, payload.current_password)

    changes: dict = {}
    event = "key.updated"
    if payload.name is not None and payload.name != key.name:
        changes["name"] = {"from": key.name, "to": payload.name}
        key.name = payload.name
    if payload.description is not None and payload.description != key.description:
        changes["description"] = True
        key.description = payload.description
    if payload.permissions is not None and sorted(payload.permissions) != sorted(key.permissions):
        changes["permissions"] = {"from": key.permissions, "to": list(payload.permissions)}
        key.permissions = list(payload.permissions)
    if payload.rate_limit is not None and payload.rate_limit != key.rate_limit:
        changes["rate_limit"] = {"from": key.rate_limit, "to": payload.rate_limit}
        key.rate_limit = payload.rate_limit
    if payload.allowed_endpoints is not None and payload.allowed_endpoints != (key.allowed_endpoints or []):
        changes["allowed_endpoints"] = payload.allowed_endpoints
        key.allowed_endpoints = payload.allowed_endpoints
    if payload.clear_expiration and key.expires_at is not None:
        changes["expires_at"] = None
        key.expires_at = None
    elif payload.expires_at is not None:
        changes["expires_at"] = payload.expires_at.isoformat()
        key.expires_at = payload.expires_at
    if payload.enabled is not None:
        target = "active" if payload.enabled else "disabled"
        if target != key.status:
            changes["status"] = {"from": key.status, "to": target}
            key.status = target
            if len(changes) == 1:
                event = "key.enabled" if payload.enabled else "key.disabled"
    if not changes:
        return ok(key_service.serialize(key), "No changes")
    key.updated_at = utcnow()
    db.flush()
    descr = {
        "key.enabled": f"API key \u201c{key.name}\u201d enabled",
        "key.disabled": f"API key \u201c{key.name}\u201d disabled",
    }.get(event, f"API key \u201c{key.name}\u201d updated")
    audit_service.record(db, principal.user.id, event, descr,
                         {"key_id": str(key.id), "changes": list(changes.keys())}, request)
    db.commit()
    return ok(key_service.serialize(key), "API key updated")


@router.post("/{key_id}/revoke")
def revoke_key(key_id: str, request: Request, principal: Principal = Depends(require_access("admin")),
               db: Session = Depends(get_db)):
    key = key_service.get_owned(db, principal.user.id, key_id)
    if key.status == "revoked":
        raise AppError(409, "API_KEY_REVOKED", "This API key is already revoked")
    key.status = "revoked"
    key.revoked_at = utcnow()
    key.updated_at = key.revoked_at
    audit_service.record(db, principal.user.id, "key.revoked", f"API key \u201c{key.name}\u201d revoked",
                         {"key_id": str(key.id), "key_prefix": key.key_prefix, "via": principal.via}, request)
    db.commit()
    return ok(key_service.serialize(key), "API key revoked")


@router.post("/{key_id}/regenerate")
def regenerate_key(key_id: str, request: Request, principal: Principal = Depends(require_session),
                   db: Session = Depends(get_db)):
    key = key_service.get_owned(db, principal.user.id, key_id)
    if key.status == "revoked":
        raise AppError(409, "API_KEY_REVOKED", "Revoked keys cannot be regenerated. Create a new key instead.")
    old_prefix = key.key_prefix
    full = key_service.regenerate(db, key)
    audit_service.record(db, principal.user.id, "key.regenerated", f"API key \u201c{key.name}\u201d regenerated",
                         {"key_id": str(key.id), "old_prefix": old_prefix, "new_prefix": key.key_prefix}, request)
    db.commit()
    data = key_service.serialize(key)
    data["secret"] = full
    return ok(data, "API key regenerated. The previous secret no longer works.")


@router.delete("/{key_id}")
def delete_key(key_id: str, request: Request, principal: Principal = Depends(require_session),
               db: Session = Depends(get_db)):
    key = key_service.get_owned(db, principal.user.id, key_id)
    meta = {"key_id": str(key.id), "key_prefix": key.key_prefix, "name": key.name}
    db.delete(key)
    audit_service.record(db, principal.user.id, "key.deleted", f"API key \u201c{meta['name']}\u201d deleted",
                         meta, request)
    db.commit()
    return ok({"id": meta["key_id"]}, "API key deleted")
