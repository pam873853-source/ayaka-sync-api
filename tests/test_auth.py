from datetime import datetime, timedelta, timezone

import jwt

from backend.config import get_settings
from backend import security
from tests.conftest import make_client, register


def _replace_cookie(client, name, value):
    for c in list(client.cookies.jar):
        if c.name == name:
            client.cookies.jar.clear(c.domain, c.path, c.name)
    client.cookies.set(name, value)


def test_register_success_sets_httponly_cookie(client):
    r = client.post("/api/v1/auth/register", json={
        "username": "ayaka", "email": "Ayaka@Example.com", "password": "Sup3r-secret!",
        "confirm_password": "Sup3r-secret!"})
    assert r.status_code == 201
    body = r.json()
    assert body["success"] is True and body["data"]["user"]["email"] == "ayaka@example.com"
    assert "password_hash" not in body["data"]["user"]
    cookies = r.headers.get_list("set-cookie")
    access = next(c for c in cookies if c.startswith(security.ACCESS_COOKIE))
    assert "HttpOnly" in access and "SameSite=lax" in access
    # Password stored as Argon2 hash, never plaintext
    from sqlalchemy import text
    from backend.database import get_engine
    with get_engine().connect() as conn:
        h = conn.execute(text("SELECT password_hash FROM users")).scalar_one()
    assert h.startswith("$argon2id$") and "Sup3r-secret!" not in h


def test_register_duplicate_email_and_username(client):
    register(client, "ayaka")
    other = make_client()
    r = other.post("/api/v1/auth/register", json={"username": "other", "email": "AYAKA@example.com",
                                                  "password": "Sup3r-secret!", "confirm_password": "Sup3r-secret!"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "EMAIL_TAKEN"
    r = other.post("/api/v1/auth/register", json={"username": "Ayaka", "email": "new@example.com",
                                                  "password": "Sup3r-secret!", "confirm_password": "Sup3r-secret!"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "USERNAME_TAKEN"


def test_register_validation(client):
    r = client.post("/api/v1/auth/register", json={"username": "a b", "email": "bad", "password": "short",
                                                   "confirm_password": "short"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
    r = client.post("/api/v1/auth/register", json={"username": "abc", "email": "a@example.com",
                                                   "password": "Sup3r-secret!", "confirm_password": "nope"})
    assert r.status_code == 422
    r = client.post("/api/v1/auth/register", json={"username": "abc", "email": "a@example.com",
                                                   "password": "alllowercase", "confirm_password": "alllowercase"})
    assert r.status_code == 422


def test_login_success_with_email_or_username(client):
    register(client)
    for ident in ("ayaka", "AYAKA@example.com"):
        c = make_client()
        r = c.post("/api/v1/auth/login", json={"identifier": ident, "password": "Sup3r-secret!"})
        assert r.status_code == 200, r.text
        c.headers["X-CSRF-Token"] = r.json()["data"]["csrf_token"]
        assert c.get("/api/v1/auth/me").json()["data"]["user"]["username"] == "ayaka"


def test_login_wrong_password_and_bruteforce_lockout(client):
    register(client)
    c = make_client()
    for _ in range(5):
        r = c.post("/api/v1/auth/login", json={"identifier": "ayaka", "password": "wrong-pass1"})
        assert r.status_code == 401 and r.json()["error"]["code"] == "INVALID_CREDENTIALS"
    r = c.post("/api/v1/auth/login", json={"identifier": "ayaka", "password": "Sup3r-secret!"})
    assert r.status_code == 429 and r.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "Retry-After" in r.headers


def test_private_endpoints_require_auth(client):
    for path in ("/api/v1/auth/me", "/api/v1/keys", "/api/v1/dashboard/overview", "/api/v1/activity",
                 "/api/v1/settings", "/api/v1/profile", "/api/v1/analytics/overview"):
        r = client.get(path)
        assert r.status_code == 401, path
        assert r.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_logout_revokes_session(client):
    register(client)
    access = client.cookies.get(security.ACCESS_COOKIE)
    assert client.post("/api/v1/auth/logout").status_code == 200
    # Even if a stolen copy of the old access token is replayed, the session is revoked server-side.
    c = make_client()
    c.cookies.set(security.ACCESS_COOKIE, access)
    r = c.get("/api/v1/auth/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "SESSION_REVOKED"


def test_csrf_required_for_unsafe_methods(client):
    register(client)
    token = client.headers.pop("X-CSRF-Token")
    r = client.post("/api/v1/keys", json={"name": "x", "permissions": ["read"]})
    assert r.status_code == 403 and r.json()["error"]["code"] == "CSRF_FAILED"
    client.headers["X-CSRF-Token"] = token
    r = client.post("/api/v1/keys", json={"name": "x", "permissions": ["read"]}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "CSRF_FAILED"


def test_expired_token_then_refresh(client):
    data = register(client)
    s = get_settings()
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    expired = jwt.encode({"sub": data["user"]["id"], "sid": data["session"]["id"], "iss": "ayaka-sync-api",
                          "typ": "access", "iat": int(past.timestamp()) - 60, "exp": int(past.timestamp())},
                         s.jwt_secret, algorithm="HS256")
    _replace_cookie(client, security.ACCESS_COOKIE, expired)
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401 and r.json()["error"]["code"] == "TOKEN_EXPIRED"
    old_refresh = client.cookies.get(security.REFRESH_COOKIE, path="/api/v1/auth")
    r = client.post("/api/v1/auth/refresh")
    assert r.status_code == 200, r.text
    assert client.get("/api/v1/auth/me").status_code == 200
    # Old refresh token was rotated and cannot be reused.
    c = make_client()
    c.cookies.set(security.REFRESH_COOKIE, old_refresh, path="/api/v1/auth")
    assert c.post("/api/v1/auth/refresh").status_code == 401


def test_tampered_token_rejected(client):
    register(client)
    tok = client.cookies.get(security.ACCESS_COOKIE)
    _replace_cookie(client, security.ACCESS_COOKIE, tok[:-2] + ("AA" if not tok.endswith("AA") else "BB"))
    assert client.get("/api/v1/auth/me").status_code == 401


def test_logout_all_other_sessions(client):
    register(client)
    other = make_client()
    r = other.post("/api/v1/auth/login", json={"identifier": "ayaka", "password": "Sup3r-secret!"})
    assert r.status_code == 200
    sessions = client.get("/api/v1/auth/sessions").json()["data"]
    assert len(sessions) == 2 and sum(s["current"] for s in sessions) == 1
    r = client.post("/api/v1/auth/logout-all")
    assert r.json()["data"]["revoked"] == 1
    assert other.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me").status_code == 200


def test_session_hint_cookie_is_not_a_credential(client):
    r = client.post("/api/v1/auth/register", json={
        "username": "hinty", "email": "hint@example.com", "password": "Sup3r-secret!",
        "confirm_password": "Sup3r-secret!"})
    hint = next(c for c in r.headers.get_list("set-cookie") if c.startswith(security.HINT_COOKIE))
    assert hint.startswith(f"{security.HINT_COOKIE}=1;") and "HttpOnly" not in hint
    # The hint alone never authenticates.
    c = make_client()
    c.cookies.set(security.HINT_COOKIE, "1")
    assert c.get("/api/v1/auth/me").status_code == 401
    # Refresh without a refresh cookie clears the hint so the browser stops retrying.
    r = c.post("/api/v1/auth/refresh")
    assert r.status_code == 401
    assert any(h.startswith(f"{security.HINT_COOKIE}=") and "Max-Age=0" in h for h in r.headers.get_list("set-cookie"))
