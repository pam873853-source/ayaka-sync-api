"""Authentication: register, login, logout, refresh, me, sessions."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import security
from ..config import get_settings
from ..database import get_db
from ..dependencies import Principal, check_origin, require_session
from ..models import User, UserSession
from ..responses import AppError, conflict, ok, validation
from ..schemas import LoginIn, RegisterIn
from ..services import audit_service, rate_limiter, settings_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
REFRESH_PATH = "/api/v1/auth"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def serialize_user(user: User) -> dict:
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


# ---------------------------------------------------------- cookie helpers
def set_auth_cookies(response: JSONResponse, access: str, refresh: str, remember: bool) -> None:
    s = get_settings()
    response.set_cookie(
        security.ACCESS_COOKIE, access, max_age=s.jwt_expires_minutes * 60, httponly=True,
        secure=s.cookie_secure, samesite="lax", path="/",
    )
    response.set_cookie(
        security.REFRESH_COOKIE, refresh,
        max_age=(s.refresh_remember_days * 86400) if remember else None,
        httponly=True, secure=s.cookie_secure, samesite="strict", path=REFRESH_PATH,
    )
    # Non-sensitive hint ("a session may exist") so public pages can skip /auth/me for guests.
    response.set_cookie(
        security.HINT_COOKIE, "1", max_age=(s.refresh_remember_days * 86400) if remember else None,
        httponly=False, secure=s.cookie_secure, samesite="lax", path="/",
    )


def clear_auth_cookies(response: JSONResponse) -> None:
    s = get_settings()
    response.delete_cookie(security.ACCESS_COOKIE, path="/", secure=s.cookie_secure, httponly=True, samesite="lax")
    response.delete_cookie(security.REFRESH_COOKIE, path=REFRESH_PATH, secure=s.cookie_secure, httponly=True,
                           samesite="strict")
    response.delete_cookie(security.HINT_COOKIE, path="/", secure=s.cookie_secure, samesite="lax")


def open_session(db: Session, user: User, request: Request, remember: bool) -> tuple[UserSession, str, str]:
    s = get_settings()
    refresh = security.new_refresh_token()
    days = s.refresh_remember_days if remember else s.refresh_expires_days
    sess = UserSession(
        user_id=user.id, token_hash=security.hash_token(refresh), remember_me=remember,
        expires_at=utcnow() + timedelta(days=days),
        user_agent=audit_service.user_agent(request), ip_address=audit_service.client_ip(request),
    )
    db.add(sess)
    db.flush()
    access, _ = security.create_access_token(user.id, sess.id)
    return sess, access, refresh


def session_payload(user: User, sess: UserSession, db: Session) -> dict:
    return {
        "user": serialize_user(user),
        "csrf_token": security.csrf_token_for(sess.id),
        "session": {"id": str(sess.id), "expires_at": sess.expires_at, "remember_me": sess.remember_me},
        "settings": settings_service.get_all(db, user.id),
    }


def _rate_limited(result: rate_limiter.RateLimitResult, message: str) -> AppError:
    return AppError(429, "RATE_LIMIT_EXCEEDED", message, headers=result.headers())


# ----------------------------------------------------------------- routes
@router.post("/register", status_code=201)
def register(payload: RegisterIn, request: Request, db: Session = Depends(get_db)):
    check_origin(request)
    ip = audit_service.client_ip(request) or "unknown"
    rl = rate_limiter.hit(f"register:ip:{ip}", 10, 3600)
    if not rl.allowed:
        raise _rate_limited(rl, "Too many registrations from this network. Try again later.")
    errors = security.password_strength_errors(payload.password)
    if errors:
        raise validation(errors[0], [{"field": "password", "message": e} for e in errors])
    if db.execute(select(User.id).where(func.lower(User.email) == payload.email.lower())).first():
        raise conflict("EMAIL_TAKEN", "This email is already registered")
    if db.execute(select(User.id).where(func.lower(User.username) == payload.username.lower())).first():
        raise conflict("USERNAME_TAKEN", "This username is already taken")

    user = User(username=payload.username, email=payload.email.lower(),
                password_hash=security.hash_password(payload.password))
    db.add(user)
    try:
        db.flush()
    except IntegrityError:  # concurrent registration with the same email/username
        db.rollback()
        raise conflict("ACCOUNT_EXISTS", "This email or username is already registered")
    db.refresh(user)
    sess, access, refresh = open_session(db, user, request, remember=False)
    audit_service.record(db, user.id, "auth.register", "Account created", {"username": user.username}, request)
    audit_service.record(db, user.id, "auth.login", "Signed in after registration", {"session_id": str(sess.id)}, request)
    data = session_payload(user, sess, db)
    db.commit()
    resp = ok(data, "Account created", status_code=201)
    set_auth_cookies(resp, access, refresh, remember=False)
    return resp


@router.get("/availability")
def availability(request: Request, email: str | None = Query(None, max_length=254),
                 username: str | None = Query(None, max_length=32), db: Session = Depends(get_db)):
    ip = audit_service.client_ip(request) or "unknown"
    rl = rate_limiter.hit(f"availability:ip:{ip}", 30, 60)
    if not rl.allowed:
        raise _rate_limited(rl, "Too many checks. Slow down.")
    data: dict = {}
    if email:
        data["email_available"] = db.execute(
            select(User.id).where(func.lower(User.email) == email.strip().lower())).first() is None
    if username:
        data["username_available"] = db.execute(
            select(User.id).where(func.lower(User.username) == username.strip().lower())).first() is None
    return ok(data)


@router.post("/login")
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    check_origin(request)
    s = get_settings()
    ident = payload.identifier.strip().lower()
    ip = audit_service.client_ip(request) or "unknown"
    ip_key, id_key = f"login:ip:{ip}", f"login:id:{ident}"

    for key, limit in ((ip_key, s.login_max_attempts * 3), (id_key, s.login_max_attempts)):
        peek = rate_limiter.peek(key, limit, s.login_window_seconds)
        if not peek.allowed:
            raise _rate_limited(peek, "Too many failed sign-in attempts. Try again later.")

    user = db.execute(select(User).where(
        or_(func.lower(User.email) == ident, func.lower(User.username) == ident))).scalar_one_or_none()
    valid = security.verify_password(payload.password, user.password_hash if user else None)
    if not valid or user is None or not user.is_active:
        rate_limiter.hit(ip_key, s.login_max_attempts * 3, s.login_window_seconds)
        rate_limiter.hit(id_key, s.login_max_attempts, s.login_window_seconds)
        if user is not None:
            audit_service.record_detached(user.id, "auth.failed", "Failed sign-in attempt",
                                          {"reason": "invalid_password" if not valid else "inactive"}, request)
        raise AppError(401, "INVALID_CREDENTIALS", "Invalid email/username or password")

    rate_limiter.reset(id_key)
    if security.password_needs_rehash(user.password_hash):
        user.password_hash = security.hash_password(payload.password)
    sess, access, refresh = open_session(db, user, request, remember=payload.remember_me)
    audit_service.record(db, user.id, "auth.login", "Signed in",
                         {"session_id": str(sess.id), "remember_me": payload.remember_me}, request)
    data = session_payload(user, sess, db)
    db.commit()
    resp = ok(data, "Signed in")
    set_auth_cookies(resp, access, refresh, payload.remember_me)
    return resp


@router.post("/refresh")
def refresh(request: Request, db: Session = Depends(get_db)):
    check_origin(request)
    token = request.cookies.get(security.REFRESH_COOKIE)
    sess = None
    if token:
        sess = db.execute(select(UserSession).where(UserSession.token_hash == security.hash_token(token))
                          ).scalar_one_or_none()
    if sess is None or sess.revoked_at is not None or sess.expires_at <= utcnow():
        resp = JSONResponse({"success": False, "message": "Session expired. Please sign in again.",
                             "error": {"code": "SESSION_EXPIRED"}, "meta": {}}, status_code=401)
        clear_auth_cookies(resp)
        return resp
    user = db.get(User, sess.user_id)
    if user is None or not user.is_active:
        raise AppError(401, "AUTHENTICATION_REQUIRED", "Account is not active")
    new_refresh = security.new_refresh_token()  # rotate on every use
    sess.token_hash = security.hash_token(new_refresh)
    sess.last_seen_at = utcnow()
    access, _ = security.create_access_token(user.id, sess.id)
    data = session_payload(user, sess, db)
    db.commit()
    resp = ok(data, "Session refreshed")
    set_auth_cookies(resp, access, new_refresh, sess.remember_me)
    return resp


@router.post("/logout")
def logout(request: Request, principal: Principal = Depends(require_session), db: Session = Depends(get_db)):
    sess = db.get(UserSession, principal.session.id)
    sess.revoked_at = utcnow()
    audit_service.record(db, principal.user.id, "auth.logout", "Signed out", {"session_id": str(sess.id)}, request)
    db.commit()
    resp = ok(None, "Signed out")
    clear_auth_cookies(resp)
    return resp


@router.get("/me")
def me(principal: Principal = Depends(require_session), db: Session = Depends(get_db)):
    return ok(session_payload(principal.user, principal.session, db))


@router.get("/sessions")
def list_sessions(principal: Principal = Depends(require_session), db: Session = Depends(get_db)):
    rows = db.execute(
        select(UserSession).where(UserSession.user_id == principal.user.id, UserSession.revoked_at.is_(None),
                                  UserSession.expires_at > utcnow())
        .order_by(UserSession.last_seen_at.desc()).limit(50)
    ).scalars().all()
    return ok([{
        "id": str(r.id), "user_agent": r.user_agent, "ip_address": r.ip_address,
        "created_at": r.created_at, "last_seen_at": r.last_seen_at, "expires_at": r.expires_at,
        "remember_me": r.remember_me, "current": r.id == principal.session.id,
    } for r in rows])


@router.post("/sessions/{session_id}/revoke")
def revoke_session(session_id: str, request: Request, principal: Principal = Depends(require_session),
                   db: Session = Depends(get_db)):
    try:
        sid = uuid.UUID(session_id)
    except ValueError:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Session not found")
    sess = db.get(UserSession, sid)
    if sess is None or sess.user_id != principal.user.id or sess.revoked_at is not None:
        raise AppError(404, "RESOURCE_NOT_FOUND", "Session not found")
    sess.revoked_at = utcnow()
    audit_service.record(db, principal.user.id, "auth.session_revoked", "Session revoked",
                         {"session_id": session_id}, request)
    db.commit()
    resp = ok(None, "Session revoked")
    if sid == principal.session.id:
        clear_auth_cookies(resp)
    return resp


@router.post("/logout-all")
def logout_all(request: Request, include_current: bool = Query(False),
               principal: Principal = Depends(require_session), db: Session = Depends(get_db)):
    stmt = update(UserSession).where(UserSession.user_id == principal.user.id, UserSession.revoked_at.is_(None))
    if not include_current:
        stmt = stmt.where(UserSession.id != principal.session.id)
    count = db.execute(stmt.values(revoked_at=utcnow())).rowcount
    audit_service.record(db, principal.user.id, "auth.logout_all",
                         "Signed out of all sessions" if include_current else "Signed out of all other sessions",
                         {"revoked": count}, request)
    db.commit()
    resp = ok({"revoked": count}, f"{count} session(s) signed out")
    if include_current:
        clear_auth_cookies(resp)
    return resp
