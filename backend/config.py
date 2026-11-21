"""Application configuration loaded from environment variables.

All secrets come from the environment. Nothing sensitive is hardcoded.
"""
from __future__ import annotations

import os
import secrets
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from urllib.parse import urlsplit

try:  # Optional: load a local .env during development.
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional
    pass

log = logging.getLogger("ayaka.config")


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(value: str | None, default: int) -> int:
    try:
        return int(value) if value not in (None, "") else default
    except ValueError:
        return default


def normalize_database_url(url: str) -> str:
    """Force the psycopg (v3) SQLAlchemy driver regardless of the URL scheme Neon gives."""
    if not url:
        return url
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def is_loopback_url(url: str) -> bool:
    """True for localhost-style URLs, which can never be a public base URL."""
    if not url:
        return False
    host = urlsplit(url if "://" in url else f"http://{url}").hostname or ""
    return host.lower() in LOOPBACK_HOSTS or host.lower().endswith(".localhost")


def resolve_base_url(environ: dict | None = None) -> tuple[str, str]:
    """Pick the public base URL and report where it came from.

    Order: explicit ``APP_BASE_URL`` (ignored on Vercel when it points at localhost) →
    Vercel system variables (production domain, then the deployment URL) → localhost.
    Returns ``(url, source)`` where source is ``env`` | ``vercel`` | ``default``.
    """
    env = os.environ if environ is None else environ
    explicit = (env.get("APP_BASE_URL") or "").strip().rstrip("/")
    on_vercel = bool(env.get("VERCEL"))
    if explicit and not (on_vercel and is_loopback_url(explicit)):
        if "://" not in explicit:
            explicit = "https://" + explicit
        return explicit, "env"
    if on_vercel:
        vercel_env = (env.get("VERCEL_ENV") or "").lower()
        candidates = []
        if vercel_env == "production":
            candidates.append(env.get("VERCEL_PROJECT_PRODUCTION_URL"))
        candidates += [env.get("VERCEL_BRANCH_URL"), env.get("VERCEL_URL"), env.get("VERCEL_PROJECT_PRODUCTION_URL")]
        for host in candidates:
            host = (host or "").strip().rstrip("/")
            if host:
                return (host if "://" in host else f"https://{host}"), "vercel"
    return "http://localhost:8000", "default"


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    app_base_url: str
    database_url: str
    jwt_secret: str
    jwt_expires_minutes: int
    refresh_expires_days: int
    refresh_remember_days: int
    api_key_pepper: str
    cors_origins: list[str] = field(default_factory=list)
    rate_limit_default: int = 60
    login_max_attempts: int = 10
    login_window_seconds: int = 900
    log_level: str = "INFO"
    serve_static: bool = True
    is_serverless: bool = False
    missing_secrets: list[str] = field(default_factory=list)
    # "env" = APP_BASE_URL, "vercel" = Vercel system variables, "default" = localhost fallback.
    base_url_source: str = "env"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cookie_secure(self) -> bool:
        # Secure cookies in production and on Vercel (always HTTPS); allow plain http://localhost locally.
        return self.is_production or self.is_serverless or self.app_base_url.startswith("https://")


@lru_cache
def get_settings() -> Settings:
    app_env = os.getenv("APP_ENV", "development").strip().lower()
    base_url, base_url_source = resolve_base_url()
    if base_url_source != "env" and os.getenv("APP_BASE_URL"):
        log.warning("APP_BASE_URL=%s points at localhost on Vercel; using %s instead",
                    os.getenv("APP_BASE_URL"), base_url)
    missing: list[str] = []

    jwt_secret = os.getenv("JWT_SECRET", "")
    pepper = os.getenv("API_KEY_PEPPER", "")
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        missing.append("DATABASE_URL")
    if not jwt_secret:
        missing.append("JWT_SECRET")
        # Ephemeral secret so local dev works; sessions reset on restart.
        jwt_secret = secrets.token_urlsafe(48)
    if not pepper:
        missing.append("API_KEY_PEPPER")
        pepper = secrets.token_urlsafe(48)
    if missing:
        log.warning("Missing environment variables: %s", ", ".join(missing))

    raw_origins = os.getenv("CORS_ORIGINS", "")
    origins = [o.strip().rstrip("/") for o in raw_origins.split(",") if o.strip()]
    for o in (base_url, *(f"https://{h.strip().rstrip('/')}" for h in (
            os.getenv("VERCEL_URL"), os.getenv("VERCEL_BRANCH_URL"), os.getenv("VERCEL_PROJECT_PRODUCTION_URL")) if h)):
        if o and o not in origins:
            origins.append(o)

    is_serverless = bool(os.getenv("VERCEL")) or _bool(os.getenv("SERVERLESS"))

    return Settings(
        app_name=os.getenv("APP_NAME", "Ayaka Sync API"),
        app_env=app_env,
        app_base_url=base_url,
        database_url=normalize_database_url(db_url),
        jwt_secret=jwt_secret,
        jwt_expires_minutes=_int(os.getenv("JWT_EXPIRES_MINUTES"), 30),
        refresh_expires_days=_int(os.getenv("REFRESH_EXPIRES_DAYS"), 1),
        refresh_remember_days=_int(os.getenv("REFRESH_REMEMBER_DAYS"), 30),
        api_key_pepper=pepper,
        cors_origins=origins,
        rate_limit_default=_int(os.getenv("RATE_LIMIT_DEFAULT"), 60),
        login_max_attempts=_int(os.getenv("LOGIN_MAX_ATTEMPTS"), 10),
        login_window_seconds=_int(os.getenv("LOGIN_WINDOW_SECONDS"), 900),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        serve_static=_bool(os.getenv("SERVE_STATIC"), default=not is_serverless),
        is_serverless=is_serverless,
        missing_secrets=missing,
        base_url_source=base_url_source,
    )
