"""Usage tracking for API-key authenticated requests.

Writes are done in an independent transaction *after* the response is built so a
logging failure never breaks the actual API call. If the database is briefly
unavailable, events are kept in a bounded in-process retry buffer and flushed on
the next successful write. Failure counters are exposed via
``GET /api/v1/health`` so problems are visible to monitoring.
"""
from __future__ import annotations

import logging
import threading
from collections import deque
from datetime import datetime, timezone

from sqlalchemy import text

from ..database import get_engine

log = logging.getLogger("ayaka.usage")

_BUFFER: deque[dict] = deque(maxlen=500)
_LOCK = threading.Lock()
STATS = {"written": 0, "failed": 0, "buffered": 0, "dropped": 0, "last_error": None, "last_error_at": None}

_INSERT = text(
    """
    INSERT INTO api_usage (user_id, api_key_id, api_key_name, request_id, endpoint, method,
                           status_code, response_time_ms, ip_address, user_agent, created_at)
    VALUES (:user_id, :api_key_id, :api_key_name, :request_id, :endpoint, :method,
            :status_code, :response_time_ms, :ip_address, :user_agent, :created_at)
    ON CONFLICT (request_id) DO NOTHING
    """
)
_TOUCH = text("UPDATE api_keys SET last_used_at = :ts WHERE id = :id AND (last_used_at IS NULL OR last_used_at < :ts)")


def record(event: dict) -> bool:
    """Persist one usage event (plus any buffered ones). Returns True on success."""
    event.setdefault("created_at", datetime.now(timezone.utc))
    with _LOCK:
        pending = list(_BUFFER) + [event]
        _BUFFER.clear()
    try:
        with get_engine().begin() as conn:
            conn.execute(_INSERT, pending)
            for e in pending:
                if e.get("api_key_id"):
                    conn.execute(_TOUCH, {"ts": e["created_at"], "id": e["api_key_id"]})
        STATS["written"] += len(pending)
        STATS["buffered"] = 0
        return True
    except Exception as exc:  # keep for retry, never raise into the request
        STATS["failed"] += 1
        STATS["last_error"] = type(exc).__name__
        STATS["last_error_at"] = datetime.now(timezone.utc).isoformat()
        log.warning("usage logging failed (%s); buffering %d events", type(exc).__name__, len(pending))
        with _LOCK:
            before = len(_BUFFER)
            for e in pending:
                if len(_BUFFER) == _BUFFER.maxlen:
                    STATS["dropped"] += 1
                _BUFFER.append(e)
            STATS["buffered"] = len(_BUFFER)
            del before
        return False


def health() -> dict:
    return {**STATS, "buffer_size": len(_BUFFER)}
