"""User settings (general, API preferences, notifications)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import Principal, require_session
from ..responses import ok
from ..schemas import SettingsUpdate
from ..services import audit_service, settings_service

router = APIRouter(prefix="/api/v1/settings", tags=["settings"])


@router.get("")
def get_settings_route(principal: Principal = Depends(require_session), db: Session = Depends(get_db)):
    return ok(settings_service.get_all(db, principal.user.id))


@router.patch("")
def update_settings(payload: SettingsUpdate, request: Request, principal: Principal = Depends(require_session),
                    db: Session = Depends(get_db)):
    changes = payload.model_dump(exclude_none=True)
    before = settings_service.get_all(db, principal.user.id)
    changed = {k: v for k, v in changes.items() if before.get(k) != v}
    if not changed:
        return ok(before, "No changes")
    after = settings_service.update(db, principal.user.id, changed)
    audit_service.record(db, principal.user.id, "settings.changed", "Settings changed",
                         {"fields": sorted(changed.keys()), "values": changed}, request)
    db.commit()
    return ok(after, "Settings saved")
