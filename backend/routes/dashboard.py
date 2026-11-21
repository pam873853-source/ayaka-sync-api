"""Dashboard overview, recent request activity and in-app notifications."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import Principal, require_session
from ..models import ActivityLog, ApiKey, ApiUsage
from ..responses import ok
from ..services import analytics_service as svc
from ..services import settings_service

router = APIRouter(prefix="/api/v1/dashboard", tags=["dashboard"])


@router.get("/overview")
def overview(range: str = Query("30d", pattern="^(24h|7d|30d|90d)$"),
             principal: Principal = Depends(require_session), db: Session = Depends(get_db)):
    uid = principal.user.id
    tz = settings_service.get_one(db, uid, "timezone")
    w = svc.resolve_window(range, None, None, tz)
    cur = svc.summary(db, uid, w)
    prev = svc.summary(db, uid, w.previous())
    now = datetime.now(timezone.utc)
    not_expired = or_(ApiKey.expires_at.is_(None), ApiKey.expires_at > now)
    active = db.execute(select(func.count()).select_from(ApiKey).where(
        ApiKey.user_id == uid, ApiKey.status == "active", not_expired)).scalar_one()
    total_keys = db.execute(select(func.count()).select_from(ApiKey).where(ApiKey.user_id == uid)).scalar_one()
    created_in_window = db.execute(select(func.count()).select_from(ApiKey).where(
        ApiKey.user_id == uid, ApiKey.created_at >= w.start)).scalar_one()
    return ok({
        "total_requests": {"value": cur["total"], "previous": prev["total"],
                           "change": svc.pct_change(cur["total"], prev["total"])},
        "active_keys": {"value": active, "total": total_keys, "created_in_period": created_in_window},
        "successful_requests": {"value": cur["success"], "previous": prev["success"],
                                "change": svc.pct_change(cur["success"], prev["success"]),
                                "rate": cur["success_rate"]},
        "failed_requests": {"value": cur["failed"], "previous": prev["failed"],
                            "change": svc.pct_change(cur["failed"], prev["failed"]),
                            "rate": cur["error_rate"]},
        "avg_response_time_ms": cur["avg_response_time_ms"],
        "realtime": svc.realtime(db, uid),
    }, meta={"range": range, "start": w.start, "end": w.end})


@router.get("/recent-activity")
def recent_activity(
    page: int = Query(1, ge=1), per_page: int = Query(10, ge=1, le=100),
    search: str | None = Query(None, max_length=120),
    method: str | None = Query(None, pattern="^(GET|POST|PUT|PATCH|DELETE)$"),
    status: str | None = Query(None, pattern="^(success|error|2xx|3xx|4xx|5xx)$"),
    api_key_id: str | None = None,
    principal: Principal = Depends(require_session), db: Session = Depends(get_db),
):
    uid = principal.user.id
    conds = [ApiUsage.user_id == uid]
    if search:
        like = f"%{search.strip().lower()}%"
        conds.append(or_(func.lower(ApiUsage.endpoint).like(like), func.lower(ApiUsage.request_id).like(like),
                         func.lower(func.coalesce(ApiUsage.api_key_name, "")).like(like)))
    if method:
        conds.append(ApiUsage.method == method)
    if status == "success":
        conds.append(ApiUsage.status_code < 400)
    elif status == "error":
        conds.append(ApiUsage.status_code >= 400)
    elif status:
        base = int(status[0]) * 100
        conds.append(and_(ApiUsage.status_code >= base, ApiUsage.status_code < base + 100))
    if api_key_id:
        try:
            import uuid as _uuid
            conds.append(ApiUsage.api_key_id == _uuid.UUID(api_key_id))
        except ValueError:
            conds.append(ApiUsage.id == -1)
    total = db.execute(select(func.count()).select_from(ApiUsage).where(*conds)).scalar_one()
    rows = db.execute(
        select(ApiUsage, ApiKey.name, ApiKey.key_prefix).outerjoin(ApiKey, ApiKey.id == ApiUsage.api_key_id)
        .where(*conds).order_by(ApiUsage.created_at.desc(), ApiUsage.id.desc())
        .offset((page - 1) * per_page).limit(per_page)
    ).all()
    items = [{
        "request_id": u.request_id, "api_key_id": str(u.api_key_id) if u.api_key_id else None,
        "api_key_name": name or u.api_key_name or "Deleted key", "key_prefix": prefix,
        "endpoint": u.endpoint, "method": u.method, "status_code": u.status_code,
        "response_time_ms": u.response_time_ms, "created_at": u.created_at,
    } for u, name, prefix in rows]
    return ok(items, meta={"page": page, "per_page": per_page, "total": total,
                           "total_pages": max(1, math.ceil(total / per_page))})


@router.get("/notifications")
def notifications(principal: Principal = Depends(require_session), db: Session = Depends(get_db)):
    """In-app alerts derived from real data, filtered by the user's notification settings."""
    uid = principal.user.id
    prefs = settings_service.get_all(db, uid)
    now = datetime.now(timezone.utc)
    items: list[dict] = []
    if prefs["notify_key_expiration"]:
        soon = db.execute(select(ApiKey).where(
            ApiKey.user_id == uid, ApiKey.status != "revoked", ApiKey.expires_at.is_not(None),
            ApiKey.expires_at > now, ApiKey.expires_at <= now + timedelta(days=7))).scalars().all()
        for k in soon:
            items.append({"type": "key_expiration", "level": "warning", "created_at": k.expires_at,
                          "title": "API key expiring soon",
                          "body": f"\u201c{k.name}\u201d expires on {k.expires_at.date().isoformat()}."})
        expired = db.execute(select(ApiKey).where(
            ApiKey.user_id == uid, ApiKey.status != "revoked", ApiKey.expires_at.is_not(None),
            ApiKey.expires_at <= now, ApiKey.expires_at > now - timedelta(days=7))).scalars().all()
        for k in expired:
            items.append({"type": "key_expired", "level": "error", "created_at": k.expires_at,
                          "title": "API key expired", "body": f"\u201c{k.name}\u201d has expired."})
    if prefs["notify_api_errors"]:
        since = now - timedelta(hours=24)
        total, failed = db.execute(select(func.count(), func.count().filter(ApiUsage.status_code >= 500))
                                   .where(ApiUsage.user_id == uid, ApiUsage.created_at >= since)).one()
        if failed:
            items.append({"type": "api_errors", "level": "error", "created_at": now,
                          "title": "Server errors in the last 24h",
                          "body": f"{failed} of {total} requests returned a 5xx status."})
        rl = db.execute(select(func.count()).where(ApiUsage.user_id == uid, ApiUsage.created_at >= since,
                                                   ApiUsage.status_code == 429)).scalar_one()
        if rl:
            items.append({"type": "rate_limited", "level": "warning", "created_at": now,
                          "title": "Rate limit reached",
                          "body": f"{rl} request(s) were rejected with 429 in the last 24h."})
    if prefs["notify_security"]:
        failed_auth = db.execute(select(ActivityLog).where(
            ActivityLog.user_id == uid, ActivityLog.event_type == "auth.failed",
            ActivityLog.created_at >= now - timedelta(days=3)).order_by(ActivityLog.created_at.desc()).limit(5)
        ).scalars().all()
        for a in failed_auth:
            items.append({"type": "security", "level": "warning", "created_at": a.created_at,
                          "title": "Failed authentication", "body": a.description})
    items.sort(key=lambda i: i["created_at"], reverse=True)
    return ok(items[:20])
