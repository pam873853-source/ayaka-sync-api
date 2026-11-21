"""Profile, password change and account deletion."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .. import security
from ..database import get_db
from ..dependencies import Principal, require_access, require_session
from ..models import ApiKey, ApiUsage, User, UserSession
from ..responses import AppError, conflict, ok, validation
from ..schemas import ChangePasswordIn, DeleteAccountIn, ProfileUpdate
from ..services import audit_service, settings_service
from .auth import clear_auth_cookies, serialize_user

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


def _profile(db: Session, user: User) -> dict:
    prefs = settings_service.get_all(db, user.id)
    keys = db.execute(select(func.count()).select_from(ApiKey).where(ApiKey.user_id == user.id)).scalar_one()
    reqs = db.execute(select(func.count()).select_from(ApiUsage).where(ApiUsage.user_id == user.id)).scalar_one()
    return {**serialize_user(user), "display_name": prefs["display_name"], "bio": prefs["bio"],
            "timezone": prefs["timezone"], "stats": {"api_keys": keys, "total_requests": reqs}}


@router.get("")
def get_profile(principal: Principal = Depends(require_access("profile")), db: Session = Depends(get_db)):
    return ok(_profile(db, principal.user))


@router.patch("")
def update_profile(payload: ProfileUpdate, request: Request, principal: Principal = Depends(require_session),
                   db: Session = Depends(get_db)):
    user = db.get(User, principal.user.id)
    changed: list[str] = []
    if payload.email is not None and payload.email.lower() != user.email:
        if not payload.current_password or not security.verify_password(payload.current_password, user.password_hash):
            raise AppError(403, "PERMISSION_DENIED", "Changing your email requires your current password")
        if db.execute(select(User.id).where(func.lower(User.email) == payload.email.lower(), User.id != user.id)).first():
            raise conflict("EMAIL_TAKEN", "This email is already registered")
        user.email = payload.email.lower()
        changed.append("email")
    if payload.username is not None and payload.username != user.username:
        if db.execute(select(User.id).where(func.lower(User.username) == payload.username.lower(),
                                            User.id != user.id)).first():
            raise conflict("USERNAME_TAKEN", "This username is already taken")
        user.username = payload.username
        changed.append("username")
    extra = {}
    if payload.display_name is not None:
        extra["display_name"] = payload.display_name
    if payload.bio is not None:
        extra["bio"] = payload.bio
    if extra:
        before = settings_service.get_all(db, user.id)
        if any(before[k] != v for k, v in extra.items()):
            settings_service.update(db, user.id, extra)
            changed.extend(k for k, v in extra.items() if before[k] != v)
    if not changed:
        return ok(_profile(db, user), "No changes")
    user.updated_at = datetime.now(timezone.utc)
    audit_service.record(db, user.id, "profile.updated", "Profile updated", {"fields": changed}, request)
    db.commit()
    return ok(_profile(db, user), "Profile updated")


@router.post("/change-password")
def change_password(payload: ChangePasswordIn, request: Request, principal: Principal = Depends(require_session),
                    db: Session = Depends(get_db)):
    user = db.get(User, principal.user.id)
    if not security.verify_password(payload.current_password, user.password_hash):
        audit_service.record_detached(user.id, "auth.failed", "Incorrect current password on password change",
                                      None, request)
        raise AppError(403, "INVALID_CREDENTIALS", "Current password is incorrect")
    errors = security.password_strength_errors(payload.new_password)
    if errors:
        raise validation(errors[0], [{"field": "new_password", "message": e} for e in errors])
    if security.verify_password(payload.new_password, user.password_hash):
        raise validation("New password must be different from the current password")
    user.password_hash = security.hash_password(payload.new_password)
    user.updated_at = datetime.now(timezone.utc)
    revoked = 0
    if payload.logout_other_sessions:
        revoked = db.execute(update(UserSession).where(
            UserSession.user_id == user.id, UserSession.revoked_at.is_(None),
            UserSession.id != principal.session.id).values(revoked_at=datetime.now(timezone.utc))).rowcount
    audit_service.record(db, user.id, "password.changed", "Password changed",
                         {"other_sessions_revoked": revoked}, request)
    db.commit()
    return ok({"other_sessions_revoked": revoked}, "Password changed")


@router.post("/delete-account")
def delete_account(payload: DeleteAccountIn, request: Request, principal: Principal = Depends(require_session),
                   db: Session = Depends(get_db)):
    user = db.get(User, principal.user.id)
    if not security.verify_password(payload.password, user.password_hash):
        raise AppError(403, "INVALID_CREDENTIALS", "Password is incorrect")
    db.delete(user)  # cascades to keys, usage, sessions, settings, logs, records
    db.commit()
    resp = ok(None, "Account deleted")
    clear_auth_cookies(resp)
    return resp
