"""Analytics queries over ``api_usage`` — all scoped to a single user."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..responses import validation

RANGES = {"24h": timedelta(hours=24), "7d": timedelta(days=7), "30d": timedelta(days=30), "90d": timedelta(days=90)}
MAX_CUSTOM_DAYS = 366


@dataclass
class Window:
    start: datetime
    end: datetime
    label: str
    bucket: str  # "hour" | "day"
    tz: str

    @property
    def span(self) -> timedelta:
        return self.end - self.start

    def previous(self) -> "Window":
        return Window(self.start - self.span, self.start, f"previous_{self.label}", self.bucket, self.tz)


def _zone(tz: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz)
    except Exception:
        return ZoneInfo("UTC")


def resolve_window(range_: str, start: date | None, end: date | None, tz: str) -> Window:
    now = datetime.now(timezone.utc)
    if range_ == "custom":
        if not start or not end:
            raise validation("Custom range requires start and end dates")
        if end < start:
            raise validation("End date must be on or after start date")
        if (end - start).days > MAX_CUSTOM_DAYS:
            raise validation(f"Custom range cannot exceed {MAX_CUSTOM_DAYS} days")
        z = _zone(tz)
        s = datetime.combine(start, time.min, z).astimezone(timezone.utc)
        e = min(datetime.combine(end + timedelta(days=1), time.min, z).astimezone(timezone.utc), now)
        if e <= s:
            raise validation("Custom range is in the future")
        bucket = "hour" if (e - s) <= timedelta(days=2) else "day"
        return Window(s, e, "custom", bucket, tz)
    if range_ not in RANGES:
        raise validation("range must be one of 24h, 7d, 30d, 90d, custom")
    return Window(now - RANGES[range_], now, range_, "hour" if range_ == "24h" else "day", tz)


def _key_filter(api_key_id: uuid.UUID | None) -> str:
    return " AND api_key_id = :key_id" if api_key_id else ""


def _params(user_id, w: Window, api_key_id=None, **extra) -> dict:
    p = {"uid": user_id, "start": w.start, "end": w.end, "tz": w.tz, **extra}
    if api_key_id:
        p["key_id"] = api_key_id
    return p


def summary(db: Session, user_id: uuid.UUID, w: Window, api_key_id: uuid.UUID | None = None) -> dict:
    row = db.execute(text(f"""
        SELECT count(*) AS total,
               count(*) FILTER (WHERE status_code < 400) AS success,
               count(*) FILTER (WHERE status_code >= 400) AS failed,
               coalesce(avg(response_time_ms), 0) AS avg_rt,
               coalesce(percentile_cont(0.95) WITHIN GROUP (ORDER BY response_time_ms), 0) AS p95_rt
        FROM api_usage
        WHERE user_id = :uid AND created_at >= :start AND created_at < :end {_key_filter(api_key_id)}
    """), _params(user_id, w, api_key_id)).mappings().one()
    total = int(row["total"])
    return {
        "total": total,
        "success": int(row["success"]),
        "failed": int(row["failed"]),
        "success_rate": round(row["success"] / total * 100, 2) if total else None,
        "error_rate": round(row["failed"] / total * 100, 2) if total else None,
        "avg_response_time_ms": round(float(row["avg_rt"]), 1),
        "p95_response_time_ms": round(float(row["p95_rt"]), 1),
    }


def pct_change(current: float, previous: float) -> float | None:
    if previous == 0:
        return None  # no baseline: a percentage would be meaningless
    return round((current - previous) / previous * 100, 1)


def calendar_counts(db: Session, user_id: uuid.UUID, tz: str) -> dict:
    """Requests today / this week (Mon-based) / this month in the user's timezone."""
    z = _zone(tz)
    local_now = datetime.now(z)
    today = datetime.combine(local_now.date(), time.min, z)
    week = today - timedelta(days=today.weekday())
    month = today.replace(day=1)
    row = db.execute(text("""
        SELECT count(*) FILTER (WHERE created_at >= :today) AS today,
               count(*) FILTER (WHERE created_at >= :week) AS week,
               count(*) FILTER (WHERE created_at >= :month) AS month,
               count(*) AS all_time
        FROM api_usage WHERE user_id = :uid AND created_at >= :floor
    """), {"uid": user_id, "today": today, "week": week, "month": month,
           "floor": min(week, month)}).mappings().one()
    all_time = db.execute(text("SELECT count(*) FROM api_usage WHERE user_id = :uid"), {"uid": user_id}).scalar_one()
    return {"today": row["today"], "this_week": row["week"], "this_month": row["month"], "all_time": all_time}


def timeseries(db: Session, user_id: uuid.UUID, w: Window, api_key_id: uuid.UUID | None = None) -> list[dict]:
    rows = db.execute(text(f"""
        SELECT date_trunc(:unit, created_at AT TIME ZONE :tz) AS bucket,
               count(*) AS total,
               count(*) FILTER (WHERE status_code < 400) AS success,
               count(*) FILTER (WHERE status_code >= 400) AS failed,
               avg(response_time_ms) AS avg_rt,
               max(response_time_ms) AS max_rt
        FROM api_usage
        WHERE user_id = :uid AND created_at >= :start AND created_at < :end {_key_filter(api_key_id)}
        GROUP BY 1 ORDER BY 1
    """), _params(user_id, w, api_key_id, unit=w.bucket)).mappings().all()
    found = {r["bucket"]: r for r in rows}

    z = _zone(w.tz)
    step = timedelta(hours=1) if w.bucket == "hour" else timedelta(days=1)
    cursor = w.start.astimezone(z).replace(tzinfo=None, minute=0, second=0, microsecond=0)
    if w.bucket == "day":
        cursor = cursor.replace(hour=0)
    end_local = w.end.astimezone(z).replace(tzinfo=None)
    series = []
    while cursor <= end_local:
        r = found.get(cursor)
        series.append({
            "bucket": cursor.isoformat(),
            "total": int(r["total"]) if r else 0,
            "success": int(r["success"]) if r else 0,
            "failed": int(r["failed"]) if r else 0,
            "avg_response_time_ms": round(float(r["avg_rt"]), 1) if r and r["avg_rt"] is not None else None,
            "max_response_time_ms": int(r["max_rt"]) if r and r["max_rt"] is not None else None,
        })
        cursor += step
    return series


def peak(series: list[dict]) -> dict | None:
    if not series:
        return None
    best = max(series, key=lambda b: b["total"])
    return {"bucket": best["bucket"], "total": best["total"]} if best["total"] else None


def by_endpoint(db: Session, user_id: uuid.UUID, w: Window, limit: int = 10) -> list[dict]:
    rows = db.execute(text("""
        SELECT endpoint, method, count(*) AS total,
               count(*) FILTER (WHERE status_code >= 400) AS failed,
               avg(response_time_ms) AS avg_rt
        FROM api_usage WHERE user_id = :uid AND created_at >= :start AND created_at < :end
        GROUP BY endpoint, method ORDER BY total DESC, endpoint LIMIT :lim
    """), _params(user_id, w, lim=limit)).mappings().all()
    return [{"endpoint": r["endpoint"], "method": r["method"], "total": r["total"], "failed": r["failed"],
             "avg_response_time_ms": round(float(r["avg_rt"]), 1)} for r in rows]


def by_key(db: Session, user_id: uuid.UUID, w: Window, limit: int = 10) -> list[dict]:
    rows = db.execute(text("""
        SELECT u.api_key_id, coalesce(k.name, u.api_key_name, 'Deleted key') AS name,
               k.key_prefix, count(*) AS total,
               count(*) FILTER (WHERE u.status_code >= 400) AS failed
        FROM api_usage u LEFT JOIN api_keys k ON k.id = u.api_key_id
        WHERE u.user_id = :uid AND u.created_at >= :start AND u.created_at < :end
        GROUP BY u.api_key_id, k.name, u.api_key_name, k.key_prefix
        ORDER BY total DESC LIMIT :lim
    """), _params(user_id, w, lim=limit)).mappings().all()
    return [{"api_key_id": str(r["api_key_id"]) if r["api_key_id"] else None, "name": r["name"],
             "key_prefix": r["key_prefix"], "total": r["total"], "failed": r["failed"]} for r in rows]


def status_codes(db: Session, user_id: uuid.UUID, w: Window) -> list[dict]:
    rows = db.execute(text("""
        SELECT status_code, count(*) AS total FROM api_usage
        WHERE user_id = :uid AND created_at >= :start AND created_at < :end
        GROUP BY status_code ORDER BY total DESC LIMIT 12
    """), _params(user_id, w)).mappings().all()
    return [dict(r) for r in rows]


def realtime(db: Session, user_id: uuid.UUID) -> dict:
    now = datetime.now(timezone.utc)
    hour_ago = now - timedelta(minutes=60)
    per_minute = db.execute(text("""
        SELECT date_trunc('minute', created_at) AS minute, count(*) AS total,
               count(*) FILTER (WHERE status_code >= 400) AS failed
        FROM api_usage WHERE user_id = :uid AND created_at >= :since
        GROUP BY 1 ORDER BY 1
    """), {"uid": user_id, "since": hour_ago}).mappings().all()
    found = {r["minute"]: r for r in per_minute}
    start_minute = hour_ago.replace(second=0, microsecond=0) + timedelta(minutes=1)
    minutes = []
    for i in range(60):
        m = start_minute + timedelta(minutes=i)
        r = found.get(m)
        minutes.append({"minute": m.isoformat(), "total": int(r["total"]) if r else 0,
                        "failed": int(r["failed"]) if r else 0})
    w = Window(hour_ago, now, "1h", "hour", "UTC")
    s = summary(db, user_id, w)
    last5 = sum(m["total"] for m in minutes[-5:])
    top_ep = by_endpoint(db, user_id, w, 1)
    top_key = by_key(db, user_id, w, 1)
    last = db.execute(text("SELECT max(created_at) FROM api_usage WHERE user_id = :uid"), {"uid": user_id}).scalar()
    return {
        "window_minutes": 60,
        "requests_last_hour": s["total"],
        "requests_per_minute": round(last5 / 5, 2),
        "current_minute": minutes[-1]["total"],
        "success_rate": s["success_rate"],
        "failed_last_hour": s["failed"],
        "avg_response_time_ms": s["avg_response_time_ms"],
        "top_endpoint": top_ep[0] if top_ep else None,
        "top_key": top_key[0] if top_key else None,
        "last_request_at": last,
        "per_minute": minutes,
        "generated_at": now,
    }
