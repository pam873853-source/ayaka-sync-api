"""User settings stored as key/value rows in ``user_settings``."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import UserSetting


def defaults() -> dict[str, Any]:
    return {
        "timezone": "UTC",
        "date_format": "YYYY-MM-DD",
        "default_environment": "development",
        "default_rate_limit": get_settings().rate_limit_default,
        "default_key_expiration_days": 0,
        "notify_api_errors": True,
        "notify_key_expiration": True,
        "notify_security": True,
        "display_name": "",
        "bio": "",
    }


def get_all(db: Session, user_id: uuid.UUID) -> dict[str, Any]:
    values = defaults()
    rows = db.execute(select(UserSetting.setting_key, UserSetting.setting_value)
                      .where(UserSetting.user_id == user_id)).all()
    for key, value in rows:
        if key in values:
            values[key] = value
    return values


def get_one(db: Session, user_id: uuid.UUID, key: str) -> Any:
    return get_all(db, user_id)[key]


def update(db: Session, user_id: uuid.UUID, changes: dict[str, Any]) -> dict[str, Any]:
    allowed = defaults().keys()
    for key, value in changes.items():
        if key not in allowed:
            continue
        stmt = insert(UserSetting).values(user_id=user_id, setting_key=key, setting_value=value)
        stmt = stmt.on_conflict_do_update(
            constraint="user_settings_user_key_uq",
            set_={"setting_value": stmt.excluded.setting_value, "updated_at": func.now()},
        )
        db.execute(stmt)
    return get_all(db, user_id)
