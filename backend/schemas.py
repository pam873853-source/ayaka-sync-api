"""Pydantic request schemas (server-side validation)."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal
from zoneinfo import ZoneInfo, available_timezones

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from .models import PERMISSIONS

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_.-]{3,32}$")
ENDPOINT_RE = re.compile(r"^/api/v1/[a-zA-Z0-9/_\-*{}]*$")
Permission = Literal["read", "write", "delete", "analytics", "profile", "admin"]
Environment = Literal["development", "production"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# -------------------------------------------------------------------- auth
class RegisterIn(Strict):
    username: str = Field(min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=1, max_length=128)

    @field_validator("username")
    @classmethod
    def _username(cls, v: str) -> str:
        if not USERNAME_RE.match(v):
            raise ValueError("Username may contain letters, digits, '.', '_' and '-' only (3-32 chars)")
        return v

    @model_validator(mode="after")
    def _match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class LoginIn(Strict):
    identifier: str = Field(min_length=3, max_length=254, description="Email or username")
    password: str = Field(min_length=1, max_length=128)
    remember_me: bool = False


# ---------------------------------------------------------------- api keys
class _KeyCommon(Strict):
    @field_validator("permissions", check_fields=False)
    @classmethod
    def _perms(cls, v):
        if v is None:
            return v
        v = sorted(set(v), key=PERMISSIONS.index)
        if not v:
            raise ValueError("Select at least one permission")
        return v

    @field_validator("allowed_endpoints", check_fields=False)
    @classmethod
    def _endpoints(cls, v):
        if v is None:
            return v
        cleaned = []
        for item in v:
            item = item.strip()
            if not item:
                continue
            if not ENDPOINT_RE.match(item) or len(item) > 120:
                raise ValueError(f"Invalid endpoint pattern: {item!r}. Use paths like /api/v1/records or /api/v1/records/*")
            cleaned.append(item)
        if len(cleaned) > 20:
            raise ValueError("At most 20 allowed endpoints")
        return cleaned

    @field_validator("expires_at", check_fields=False)
    @classmethod
    def _expiry(cls, v):
        if v is None:
            return v
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        if v <= datetime.now(timezone.utc):
            raise ValueError("Expiration date must be in the future")
        return v


class ApiKeyCreate(_KeyCommon):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=500)
    environment: Environment | None = None
    permissions: list[Permission] = Field(default_factory=lambda: ["read"])
    expires_at: datetime | None = None
    rate_limit: int | None = Field(default=None, ge=1, le=10000)
    allowed_endpoints: list[str] = Field(default_factory=list)
    current_password: str | None = Field(default=None, max_length=128,
                                         description="Required when requesting the admin permission")


class ApiKeyUpdate(_KeyCommon):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    permissions: list[Permission] | None = None
    expires_at: datetime | None = None
    clear_expiration: bool = False
    rate_limit: int | None = Field(default=None, ge=1, le=10000)
    allowed_endpoints: list[str] | None = None
    enabled: bool | None = None
    current_password: str | None = Field(default=None, max_length=128)


# ------------------------------------------------------- profile/settings
class ProfileUpdate(Strict):
    username: str | None = Field(default=None, min_length=3, max_length=32)
    email: EmailStr | None = None
    display_name: str | None = Field(default=None, max_length=80)
    bio: str | None = Field(default=None, max_length=300)
    current_password: str | None = Field(default=None, max_length=128)

    @field_validator("username")
    @classmethod
    def _username(cls, v):
        if v is not None and not USERNAME_RE.match(v):
            raise ValueError("Username may contain letters, digits, '.', '_' and '-' only (3-32 chars)")
        return v


class ChangePasswordIn(Strict):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=1, max_length=128)
    logout_other_sessions: bool = True

    @model_validator(mode="after")
    def _match(self):
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class DeleteAccountIn(Strict):
    password: str = Field(min_length=1, max_length=128)
    confirm: str = Field(description="Type DELETE to confirm")

    @field_validator("confirm")
    @classmethod
    def _confirm(cls, v):
        if v != "DELETE":
            raise ValueError("Type DELETE to confirm account deletion")
        return v


_TIMEZONES = None


def _valid_tz(name: str) -> bool:
    global _TIMEZONES
    if _TIMEZONES is None:
        _TIMEZONES = available_timezones() | {"UTC"}
    if name in _TIMEZONES:
        return True
    try:
        ZoneInfo(name)
        return True
    except Exception:
        return False


DateFormat = Literal["YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY", "DD MMM YYYY"]


class SettingsUpdate(Strict):
    timezone: str | None = Field(default=None, max_length=64)
    date_format: DateFormat | None = None
    default_environment: Environment | None = None
    default_rate_limit: int | None = Field(default=None, ge=1, le=10000)
    default_key_expiration_days: int | None = Field(default=None, ge=0, le=730,
                                                    description="0 means never expires")
    notify_api_errors: bool | None = None
    notify_key_expiration: bool | None = None
    notify_security: bool | None = None

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v):
        if v is not None and not _valid_tz(v):
            raise ValueError("Unknown timezone")
        return v


# ------------------------------------------------------------- records API
def _check_record_size(v: dict) -> dict:
    import json
    if len(json.dumps(v)) > 16_384:
        raise ValueError("Record data must be at most 16 KB")
    return v


class RecordIn(Strict):
    collection: str = Field(default="default", pattern=r"^[a-z0-9_-]{1,64}$")
    data: dict[str, Any]

    @field_validator("data")
    @classmethod
    def _size(cls, v):
        return _check_record_size(v)


class RecordUpdate(Strict):
    data: dict[str, Any]

    @field_validator("data")
    @classmethod
    def _size(cls, v):
        return _check_record_size(v)
