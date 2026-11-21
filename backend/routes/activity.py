"""Activity (audit) log — read-only for users."""
from __future__ import annotations

import csv
import io
import math
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import Principal, require_session
from ..models import ActivityLog
from ..responses import not_found, ok
from ..services import settings_service
from ..services.audit_service import EVENT_TYPES

router = APIRouter(prefix="/api/v1/activity", tags=["activity"])
EXPORT_LIMIT = 10_000


def _conds(db: Session, principal: Principal, search, event_type, start: date | None, end: date | None):
    uid = principal.user.id
    conds = [ActivityLog.user_id == uid]
    if search:
        like = f"%{search.strip().lower()}%"
        conds.append(or_(func.lower(ActivityLog.description).like(like),
                         func.lower(ActivityLog.event_type).like(like),
                         func.lower(func.coalesce(ActivityLog.ip_address, "")).like(like)))
    if event_type:
        types = [t for t in event_type.split(",") if t]
        if len(types) == 1 and types[0].endswith(".*"):
            conds.append(ActivityLog.event_type.like(types[0][:-1] + "%"))
        else:
            conds.append(ActivityLog.event_type.in_(types))
    if start or end:
        try:
            tz = ZoneInfo(settings_service.get_one(db, uid, "timezone"))
        except Exception:
            tz = timezone.utc
        if start:
            conds.append(ActivityLog.created_at >= datetime.combine(start, time.min, tz))
        if end:
            conds.append(ActivityLog.created_at < datetime.combine(end + timedelta(days=1), time.min, tz))
    return conds


def _serialize(a: ActivityLog) -> dict:
    return {"id": a.id, "event_type": a.event_type, "label": EVENT_TYPES.get(a.event_type, a.event_type),
            "description": a.description, "metadata": a.metadata_, "ip_address": a.ip_address,
            "user_agent": a.user_agent, "created_at": a.created_at}


@router.get("")
def list_activity(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100),
                  search: str | None = Query(None, max_length=120),
                  event_type: str | None = Query(None, max_length=400),
                  start: date | None = None, end: date | None = None,
                  principal: Principal = Depends(require_session), db: Session = Depends(get_db)):
    conds = _conds(db, principal, search, event_type, start, end)
    total = db.execute(select(func.count()).select_from(ActivityLog).where(*conds)).scalar_one()
    rows = db.execute(select(ActivityLog).where(*conds).order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
                      .offset((page - 1) * per_page).limit(per_page)).scalars().all()
    return ok([_serialize(a) for a in rows], meta={
        "page": page, "per_page": per_page, "total": total, "total_pages": max(1, math.ceil(total / per_page)),
        "event_types": EVENT_TYPES,
    })


def _safe_cell(value) -> str:
    s = "" if value is None else str(value)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s  # CSV/formula injection guard


@router.get("/export")
def export_activity(search: str | None = Query(None, max_length=120),
                    event_type: str | None = Query(None, max_length=400),
                    start: date | None = None, end: date | None = None,
                    principal: Principal = Depends(require_session), db: Session = Depends(get_db)):
    conds = _conds(db, principal, search, event_type, start, end)
    rows = db.execute(select(ActivityLog).where(*conds).order_by(ActivityLog.created_at.desc())
                      .limit(EXPORT_LIMIT)).scalars().all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "timestamp_utc", "event_type", "description", "ip_address", "user_agent", "metadata"])
    import json
    for a in rows:
        writer.writerow([a.id, a.created_at.astimezone(timezone.utc).isoformat(), a.event_type,
                         _safe_cell(a.description), _safe_cell(a.ip_address), _safe_cell(a.user_agent),
                         _safe_cell(json.dumps(a.metadata_, default=str))])
    filename = f"ayaka-activity-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
    return Response(buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/{log_id}")
def get_activity(log_id: int, principal: Principal = Depends(require_session), db: Session = Depends(get_db)):
    a = db.execute(select(ActivityLog).where(ActivityLog.id == log_id,
                                             ActivityLog.user_id == principal.user.id)).scalar_one_or_none()
    if a is None:
        raise not_found("Log entry not found")
    return ok(_serialize(a))
