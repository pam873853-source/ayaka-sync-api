"""Analytics endpoints (session, or API key with the `analytics` permission)."""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import Principal, require_access
from ..responses import ok
from ..services import analytics_service as svc
from ..services import key_service, settings_service

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])
RANGE_PATTERN = "^(24h|7d|30d|90d|custom)$"


def _window(db: Session, principal: Principal, range_: str, start: date | None, end: date | None) -> svc.Window:
    tz = settings_service.get_one(db, principal.user.id, "timezone")
    return svc.resolve_window(range_, start, end, tz)


def _meta(w: svc.Window) -> dict:
    return {"range": w.label, "start": w.start, "end": w.end, "bucket": w.bucket, "timezone": w.tz}


def _key(db: Session, principal: Principal, api_key_id: str | None) -> uuid.UUID | None:
    if not api_key_id:
        return None
    return key_service.get_owned(db, principal.user.id, api_key_id).id


@router.get("/overview")
def overview(range: str = Query("7d", pattern=RANGE_PATTERN), start: date | None = None, end: date | None = None,
             api_key_id: str | None = None,
             principal: Principal = Depends(require_access("analytics")), db: Session = Depends(get_db)):
    w = _window(db, principal, range, start, end)
    kid = _key(db, principal, api_key_id)
    current = svc.summary(db, principal.user.id, w, kid)
    previous = svc.summary(db, principal.user.id, w.previous(), kid)
    series = svc.timeseries(db, principal.user.id, w, kid)
    return ok({
        **current,
        "calendar": svc.calendar_counts(db, principal.user.id, w.tz),
        "peak": svc.peak(series),
        "previous": previous,
        "change": {
            "total": svc.pct_change(current["total"], previous["total"]),
            "success": svc.pct_change(current["success"], previous["success"]),
            "failed": svc.pct_change(current["failed"], previous["failed"]),
            "avg_response_time_ms": svc.pct_change(current["avg_response_time_ms"], previous["avg_response_time_ms"]),
        },
    }, meta=_meta(w))


@router.get("/requests")
def requests_series(range: str = Query("7d", pattern=RANGE_PATTERN), start: date | None = None,
                    end: date | None = None, api_key_id: str | None = None,
                    principal: Principal = Depends(require_access("analytics")), db: Session = Depends(get_db)):
    w = _window(db, principal, range, start, end)
    series = svc.timeseries(db, principal.user.id, w, _key(db, principal, api_key_id))
    return ok({"series": series, "status_codes": svc.status_codes(db, principal.user.id, w)}, meta=_meta(w))


@router.get("/endpoints")
def endpoints(range: str = Query("7d", pattern=RANGE_PATTERN), start: date | None = None, end: date | None = None,
              limit: int = Query(10, ge=1, le=50),
              principal: Principal = Depends(require_access("analytics")), db: Session = Depends(get_db)):
    w = _window(db, principal, range, start, end)
    return ok(svc.by_endpoint(db, principal.user.id, w, limit), meta=_meta(w))


@router.get("/keys")
def keys(range: str = Query("7d", pattern=RANGE_PATTERN), start: date | None = None, end: date | None = None,
         limit: int = Query(10, ge=1, le=50),
         principal: Principal = Depends(require_access("analytics")), db: Session = Depends(get_db)):
    w = _window(db, principal, range, start, end)
    return ok(svc.by_key(db, principal.user.id, w, limit), meta=_meta(w))


@router.get("/response-times")
def response_times(range: str = Query("7d", pattern=RANGE_PATTERN), start: date | None = None,
                   end: date | None = None, api_key_id: str | None = None,
                   principal: Principal = Depends(require_access("analytics")), db: Session = Depends(get_db)):
    w = _window(db, principal, range, start, end)
    kid = _key(db, principal, api_key_id)
    series = svc.timeseries(db, principal.user.id, w, kid)
    s = svc.summary(db, principal.user.id, w, kid)
    return ok({
        "series": [{"bucket": b["bucket"], "avg_response_time_ms": b["avg_response_time_ms"],
                    "max_response_time_ms": b["max_response_time_ms"]} for b in series],
        "avg_response_time_ms": s["avg_response_time_ms"],
        "p95_response_time_ms": s["p95_response_time_ms"],
    }, meta=_meta(w))


@router.get("/realtime")
def realtime(principal: Principal = Depends(require_access("analytics")), db: Session = Depends(get_db)):
    return ok(svc.realtime(db, principal.user.id))
