"""Cryptographic primitives: passwords, API keys, session tokens, JWT, CSRF."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from .config import get_settings

# Argon2id with OWASP-recommended parameters (19 MiB, t=2, p=1).
_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
_DUMMY_HASH = _hasher.hash("ayaka-dummy-password-for-timing")

KEY_ALPHABET = string.ascii_letters + string.digits
KEY_SECRET_LENGTH = 40  # ~238 bits of entropy
KEY_PREFIX_VISIBLE = 8
ENV_PREFIX = {"production": "ayk_live_", "development": "ayk_test_"}

ACCESS_COOKIE = "ayaka_access"
REFRESH_COOKIE = "ayaka_refresh"
CSRF_COOKIE = "ayaka_csrf"
HINT_COOKIE = "ayaka_signed_in"  # value "1" only; carries no credential
CSRF_HEADER = "x-csrf-token"


# ---------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Constant-ish time verification; runs a dummy verify when user is unknown."""
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return False


def password_strength_errors(password: str) -> list[str]:
    errors = []
    if len(password) < 8:
        errors.append("Password must be at least 8 characters long")
    if len(password) > 128:
        errors.append("Password must be at most 128 characters long")
    classes = sum([
        any(c.islower() for c in password),
        any(c.isupper() for c in password),
        any(c.isdigit() for c in password),
        any(not c.isalnum() for c in password),
    ])
    if classes < 2:
        errors.append("Password must mix at least two of: lowercase, uppercase, digits, symbols")
    return errors


# ----------------------------------------------------------------- API keys
def generate_api_key(environment: str) -> tuple[str, str, str]:
    """Return (full_key, display_prefix, key_hash). Full key is shown once only."""
    prefix = ENV_PREFIX[environment]
    secret = "".join(secrets.choice(KEY_ALPHABET) for _ in range(KEY_SECRET_LENGTH))
    full = prefix + secret
    return full, prefix + secret[:KEY_PREFIX_VISIBLE], hash_api_key(full)


def hash_api_key(full_key: str) -> str:
    """HMAC-SHA256 with a server-side pepper; irreversible without the pepper."""
    pepper = get_settings().api_key_pepper.encode()
    return hmac.new(pepper, full_key.encode(), hashlib.sha256).hexdigest()


def looks_like_api_key(value: str) -> bool:
    return any(value.startswith(p) for p in ENV_PREFIX.values()) and len(value) <= 80


# --------------------------------------------------------- session / tokens
def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user_id: uuid.UUID, session_id: uuid.UUID) -> tuple[str, datetime]:
    s = get_settings()
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=s.jwt_expires_minutes)
    payload = {
        "sub": str(user_id),
        "sid": str(session_id),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "iss": "ayaka-sync-api",
        "typ": "access",
    }
    return jwt.encode(payload, s.jwt_secret, algorithm="HS256"), exp


class TokenExpired(Exception):
    pass


class TokenInvalid(Exception):
    pass


def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token, get_settings().jwt_secret, algorithms=["HS256"], issuer="ayaka-sync-api",
            options={"require": ["exp", "sub", "sid"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpired() from exc
    except jwt.PyJWTError as exc:
        raise TokenInvalid() from exc
    if payload.get("typ") != "access":
        raise TokenInvalid()
    return payload


# --------------------------------------------------------------------- CSRF
def csrf_token_for(session_id: uuid.UUID | str) -> str:
    """Session-bound CSRF token (signed double-submit pattern)."""
    key = get_settings().jwt_secret.encode()
    return hmac.new(key, f"csrf:{session_id}".encode(), hashlib.sha256).hexdigest()


def csrf_valid(session_id: uuid.UUID | str, supplied: str | None) -> bool:
    if not supplied:
        return False
    return hmac.compare_digest(csrf_token_for(session_id), supplied)


def new_request_id() -> str:
    return "req_" + secrets.token_hex(12)
