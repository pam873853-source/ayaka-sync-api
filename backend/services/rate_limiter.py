"""Distributed fixed-window rate limiter backed by PostgreSQL.

Vercel may run many concurrent function instances, so in-memory counters would
not be shared. A single atomic ``INSERT ... ON CONFLICT DO UPDATE ... RETURNING``
on Neon gives a consistent counter across every instance with one round-trip.
"""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import text

from ..database import get_engine

log = logging.getLogger("ayaka.ratelimit")

_UPSERT = text(
    """
    INSERT INTO rate_limit_buckets (bucket_key, window_start, count, expires_at)
    VALUES (:key, :window_start, :inc, :expires_at)
    ON CONFLICT (bucket_key, window_start)
    DO UPDATE SET count = rate_limit_buckets.count + :inc
    RETURNING count
    """
)
_PEEK = text("SELECT count FROM rate_limit_buckets WHERE bucket_key = :key AND window_start = :window_start")
_CLEAN = text("DELETE FROM rate_limit_buckets WHERE expires_at < now()")
_RESET = text("DELETE FROM rate_limit_buckets WHERE bucket_key = :key")


@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    remaining: int
    reset_at: int  # unix seconds
    retry_after: int

    def headers(self) -> dict[str, str]:
        h = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(self.remaining, 0)),
            "X-RateLimit-Reset": str(self.reset_at),
        }
        if not self.allowed:
            h["Retry-After"] = str(max(self.retry_after, 1))
        return h


def _window(window_seconds: int, now: float | None = None) -> tuple[datetime, int]:
    now = time.time() if now is None else now
    start = int(now // window_seconds) * window_seconds
    return datetime.fromtimestamp(start, tz=timezone.utc), start + window_seconds


def hit(key: str, limit: int, window_seconds: int = 60, now: float | None = None) -> RateLimitResult:
    """Count one request and report whether it is within the limit."""
    window_start, reset_at = _window(window_seconds, now)
    current = time.time() if now is None else now
    with get_engine().begin() as conn:
        count = conn.execute(_UPSERT, {
            "key": key[:160], "window_start": window_start, "inc": 1,
            "expires_at": datetime.fromtimestamp(reset_at + window_seconds, tz=timezone.utc),
        }).scalar_one()
        if random.random() < 0.02:  # opportunistic cleanup of expired buckets
            conn.execute(_CLEAN)
    return RateLimitResult(
        allowed=count <= limit, limit=limit, remaining=limit - count,
        reset_at=reset_at, retry_after=int(reset_at - current) + 1,
    )


def peek(key: str, limit: int, window_seconds: int) -> RateLimitResult:
    window_start, reset_at = _window(window_seconds)
    with get_engine().connect() as conn:
        count = conn.execute(_PEEK, {"key": key[:160], "window_start": window_start}).scalar() or 0
    return RateLimitResult(
        allowed=count < limit, limit=limit, remaining=limit - count,
        reset_at=reset_at, retry_after=int(reset_at - time.time()) + 1,
    )


def reset(key: str) -> None:
    with get_engine().begin() as conn:
        conn.execute(_RESET, {"key": key[:160]})
