"""Test fixtures. Tests run against a REAL PostgreSQL database.

Set TEST_DATABASE_URL (defaults to a local database named ayaka_test). Never
point it at production: every test truncates all tables.
"""
from __future__ import annotations

import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://ayaka:ayaka@localhost:5432/ayaka_test")
os.environ["APP_ENV"] = "test"
os.environ["APP_BASE_URL"] = "http://testserver"
os.environ["JWT_SECRET"] = "test-jwt-secret-" + "x" * 32
os.environ["API_KEY_PEPPER"] = "test-pepper-" + "y" * 32
os.environ["SERVE_STATIC"] = "1"
os.environ["LOGIN_MAX_ATTEMPTS"] = "5"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from backend.database import get_engine  # noqa: E402
from backend.main import app  # noqa: E402
from backend.migrate import migrate  # noqa: E402

TABLES = ["api_usage", "activity_logs", "user_settings", "user_sessions", "api_keys", "user_records",
          "rate_limit_buckets", "users"]


@pytest.fixture(scope="session", autouse=True)
def _schema():
    migrate(verbose=False)
    yield


@pytest.fixture(autouse=True)
def _clean_db():
    with get_engine().begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
    yield


def make_client() -> TestClient:
    return TestClient(app, base_url="http://testserver")


@pytest.fixture
def client() -> TestClient:
    return make_client()


def register(client: TestClient, username: str = "ayaka", email: str | None = None,
             password: str = "Sup3r-secret!") -> dict:
    r = client.post("/api/v1/auth/register", json={
        "username": username, "email": email or f"{username}@example.com",
        "password": password, "confirm_password": password,
    })
    assert r.status_code == 201, r.text
    data = r.json()["data"]
    client.headers["X-CSRF-Token"] = data["csrf_token"]
    return data


def create_key(client: TestClient, **overrides) -> dict:
    body = {"name": "Test key", "environment": "development", "permissions": ["read"], **overrides}
    r = client.post("/api/v1/keys", json=body)
    assert r.status_code == 201, r.text
    return r.json()["data"]


@pytest.fixture
def user_client(client):
    register(client)
    return client
