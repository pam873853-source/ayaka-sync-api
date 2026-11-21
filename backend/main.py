"""FastAPI application factory for Ayaka Sync API."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .middleware import RequestContextMiddleware, install_error_handlers
from .responses import ok
from .urls import public_base_url
from .routes import activity, analytics, api_keys, auth, dashboard, health, profile, public_api
from .routes import settings as settings_routes

PUBLIC_DIR = Path(__file__).resolve().parent.parent / "public"


def create_app() -> FastAPI:
    s = get_settings()
    logging.basicConfig(level=s.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    app = FastAPI(
        title=s.app_name,
        version="1.0.0",
        description="REST API key management, usage tracking and analytics.",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )

    install_error_handlers(app)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-CSRF-Token"],
        expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset",
                        "Retry-After"],
        max_age=600,
    )
    app.add_middleware(RequestContextMiddleware)

    @app.get("/api/v1/meta", tags=["health"])
    def meta(request: Request):
        base = public_base_url(request)
        return ok({"app_name": s.app_name, "base_url": base, "api_base": f"{base}/api/v1",
                   "base_url_source": s.base_url_source,
                   "environment": s.app_env, "rate_limit_default": s.rate_limit_default})

    for r in (health.router, auth.router, api_keys.router, dashboard.router, analytics.router,
              activity.router, profile.router, settings_routes.router, public_api.router):
        app.include_router(r)

    if s.serve_static and PUBLIC_DIR.exists():
        _mount_static(app)
    return app


def _mount_static(app: FastAPI) -> None:
    """Local-dev static hosting. On Vercel, files in public/ are served by the CDN."""
    app.mount("/assets", StaticFiles(directory=PUBLIC_DIR / "assets"), name="assets")
    not_found = PUBLIC_DIR / "404.html"

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(PUBLIC_DIR / "index.html")

    @app.get("/{page:path}", include_in_schema=False)
    def page(page: str):
        if page.startswith("api/"):
            return HTMLResponse(status_code=404)
        candidate = (PUBLIC_DIR / page).resolve()
        if PUBLIC_DIR not in candidate.parents and candidate != PUBLIC_DIR:
            return FileResponse(not_found, status_code=404)
        if candidate.is_file():
            return FileResponse(candidate)
        html = candidate.with_suffix(".html")
        if html.is_file():
            return FileResponse(html)
        return FileResponse(not_found, status_code=404)


app = create_app()
