"""Public URL helpers.

When ``APP_BASE_URL`` is set explicitly it wins. Otherwise the base URL follows the domain
the request actually arrived on (Vercel deployment URL, production alias or custom domain),
so documentation and examples never show ``localhost`` on a real deployment.
"""
from __future__ import annotations

from fastapi import Request

from .config import get_settings


def request_origin(request: Request) -> str:
    host = (request.headers.get("x-forwarded-host") or request.headers.get("host") or "").split(",")[0].strip()
    proto = (request.headers.get("x-forwarded-proto") or request.url.scheme or "https").split(",")[0].strip()
    return f"{proto}://{host}".rstrip("/") if host else ""


def public_base_url(request: Request | None = None) -> str:
    s = get_settings()
    if s.base_url_source == "env" or request is None:
        return s.app_base_url
    return request_origin(request) or s.app_base_url
