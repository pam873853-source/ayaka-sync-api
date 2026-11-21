"""Authentication / authorization dependencies.

Two kinds of principals exist:

* **Session** – a signed-in dashboard user (HttpOnly JWT cookie bound to a row in
  ``user_sessions`` so it can be revoked). Unsafe methods require a CSRF token.
* **API key** – ``Authorization: Bearer ayk_...`` (or ``X-API-Key``). Every
  request is rate limited, checked against the key's permissions and allowed
  endpoints, and recorded in ``api_usage``.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from . import security
from .config import get_settings
from .database import get_db
from .models import ApiKey, User, UserSession
from .responses import AppError, auth_required, permission_denied
from .services import audit_service, key_service, rate_limiter

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@dataclass
class Principal:
    user: User
    via: str  # "session" | "api_key"
    session: UserSession | None = None
    api_key: ApiKey | None = None
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        if self.via == "session":
            return True
        return permission in self.permissions or "admin" in self.permissions


# ------------------------------------------------------------------ helpers
def extract_api_key(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token.startswith("ayk_"):
            return token
        raise AppError(401, "INVALID_API_KEY", "Invalid API key")
    header_key = request.headers.get("x-api-key")
    return header_key.strip() if header_key else None


def check_origin(request: Request) -> None:
    """Reject cross-site state-changing browser requests (defence in depth with SameSite)."""
    origin = request.headers.get("origin")
    if not origin or origin == "null":
        return  # non-browser clients / same-origin navigations without Origin
    origin = origin.rstrip("/")
    settings = get_settings()
    own = f"{request.url.scheme}://{request.headers.get('host', '')}"
    forwarded_host = request.headers.get("x-forwarded-host")
    candidates = {own}
    if forwarded_host:
        candidates.add(f"{request.headers.get('x-forwarded-proto', 'https')}://{forwarded_host}")
    if origin in settings.cors_origins or origin in candidates:
        return
    raise AppError(403, "CSRF_FAILED", "Cross-site request blocked")


def _session_principal(request: Request, db: Session, *, enforce_csrf: bool = True) -> Principal:
    token = request.cookies.get(security.ACCESS_COOKIE)
    if not token:
        raise auth_required()
    try:
        payload = security.decode_access_token(token)
    except security.TokenExpired:
        raise AppError(401, "TOKEN_EXPIRED", "Session token expired")
    except security.TokenInvalid:
        raise auth_required("Invalid session")
    try:
        sid = uuid.UUID(payload["sid"])
        uid = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise auth_required("Invalid session")
    sess = db.get(UserSession, sid)
    now = datetime.now(timezone.utc)
    if sess is None or sess.user_id != uid or sess.revoked_at is not None or sess.expires_at <= now:
        raise AppError(401, "SESSION_REVOKED", "Session is no longer valid")
    user = db.get(User, uid)
    if user is None or not user.is_active:
        raise auth_required("Account is not active")
    if request.method in UNSAFE_METHODS and enforce_csrf:
        check_origin(request)
        if not security.csrf_valid(sid, request.headers.get(security.CSRF_HEADER)):
            raise AppError(403, "CSRF_FAILED", "Missing or invalid CSRF token")
    request.state.user_id = user.id
    return Principal(user=user, via="session", session=sess)


def _api_key_principal(request: Request, db: Session, presented: str, permission: str | None) -> Principal:
    try:
        key, user = key_service.verify(db, presented)
    except AppError as err:
        owner = getattr(err, "owner_id", None)
        if owner:
            audit_service.record_detached(owner, "auth.failed", f"Rejected API key ({err.code})",
                                          {"code": err.code, "path": request.url.path}, request)
        raise
    # From here on the request is attributable -> usage is tracked even on errors.
    request.state.usage = {"user_id": user.id, "api_key_id": key.id, "api_key_name": key.name}
    request.state.user_id = user.id

    rl = rate_limiter.hit(f"key:{key.id}", key.rate_limit, 60)
    request.state.rate_headers = rl.headers()
    if not rl.allowed:
        raise AppError(429, "RATE_LIMIT_EXCEEDED",
                       f"Rate limit of {key.rate_limit} requests per minute exceeded",
                       headers=rl.headers())
    if not key_service.endpoint_allowed(key, request.url.path):
        raise permission_denied("This API key is not allowed to call this endpoint")
    principal = Principal(user=user, via="api_key", api_key=key, permissions=set(key.permissions))
    if permission and not principal.can(permission):
        raise permission_denied(f"This API key lacks the '{permission}' permission")
    return principal


# ------------------------------------------------------------- dependencies
def require_session(request: Request, db: Session = Depends(get_db)) -> Principal:
    """Dashboard-only endpoints (cookie session required, API keys rejected)."""
    if extract_api_key(request):
        raise permission_denied("This endpoint requires a dashboard session, not an API key")
    return _session_principal(request, db)


def require_access(permission: str | None):
    """Accept a dashboard session OR an API key holding ``permission``."""

    def dependency(request: Request, db: Session = Depends(get_db)) -> Principal:
        presented = extract_api_key(request)
        if presented:
            return _api_key_principal(request, db, presented, permission)
        return _session_principal(request, db)

    return dependency


def require_api_key(permission: str | None):
    """API-key-only endpoints (e.g. the developer example endpoint)."""

    def dependency(request: Request, db: Session = Depends(get_db)) -> Principal:
        presented = extract_api_key(request)
        if not presented:
            raise AppError(401, "AUTHENTICATION_REQUIRED",
                           "Provide an API key via 'Authorization: Bearer ayk_...'")
        return _api_key_principal(request, db, presented, permission)

    return dependency
