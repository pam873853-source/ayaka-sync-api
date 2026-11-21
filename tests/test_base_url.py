"""Base URL must follow the real deployment domain, never fall back to localhost on Vercel."""
import dataclasses

from backend import config, urls
from backend.config import resolve_base_url


def test_explicit_app_base_url_wins():
    assert resolve_base_url({"APP_BASE_URL": "https://api.ayaka.dev/"}) == ("https://api.ayaka.dev", "env")
    assert resolve_base_url({"VERCEL": "1", "APP_BASE_URL": "api.ayaka.dev"}) == ("https://api.ayaka.dev", "env")


def test_localhost_default_only_off_vercel():
    assert resolve_base_url({}) == ("http://localhost:8000", "default")
    assert resolve_base_url({"APP_BASE_URL": "http://localhost:8000"}) == ("http://localhost:8000", "env")


def test_vercel_ignores_localhost_and_uses_system_urls():
    env = {"VERCEL": "1", "VERCEL_ENV": "production", "APP_BASE_URL": "http://localhost:8000",
           "VERCEL_URL": "ayaka-abc123.vercel.app", "VERCEL_PROJECT_PRODUCTION_URL": "ayaka-sync.vercel.app"}
    assert resolve_base_url(env) == ("https://ayaka-sync.vercel.app", "vercel")
    preview = {"VERCEL": "1", "VERCEL_ENV": "preview", "VERCEL_URL": "ayaka-abc123.vercel.app",
               "VERCEL_BRANCH_URL": "ayaka-git-dev.vercel.app"}
    assert resolve_base_url(preview) == ("https://ayaka-git-dev.vercel.app", "vercel")


def test_meta_and_health_follow_request_domain_when_not_pinned(client, monkeypatch):
    auto = dataclasses.replace(config.get_settings(), app_base_url="https://ayaka-abc.vercel.app",
                               base_url_source="vercel")
    monkeypatch.setattr(urls, "get_settings", lambda: auto)
    headers = {"x-forwarded-host": "sync.example.com", "x-forwarded-proto": "https"}
    meta = client.get("/api/v1/meta", headers=headers).json()["data"]
    assert meta["base_url"] == "https://sync.example.com"
    assert meta["api_base"] == "https://sync.example.com/api/v1"
    health = client.get("/api/v1/health", headers=headers).json()["data"]
    assert health["base_url"] == "https://sync.example.com" and "localhost" not in health["base_url"]


def test_meta_uses_pinned_app_base_url(client):
    meta = client.get("/api/v1/meta", headers={"x-forwarded-host": "other.example.com"}).json()["data"]
    assert meta["base_url"] == "http://testserver" and meta["base_url_source"] == "env"
