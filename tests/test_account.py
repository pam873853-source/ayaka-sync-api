from tests.conftest import create_key, make_client, register


def test_settings_persist_and_apply_to_new_keys(user_client):
    r = user_client.patch("/api/v1/settings", json={"default_environment": "production", "default_rate_limit": 15,
                                                     "default_key_expiration_days": 30, "timezone": "Asia/Makassar"})
    assert r.status_code == 200
    s = user_client.get("/api/v1/settings").json()["data"]
    assert s["default_environment"] == "production" and s["timezone"] == "Asia/Makassar"
    r = user_client.post("/api/v1/keys", json={"name": "defaults", "permissions": ["read"]}).json()["data"]
    assert r["environment"] == "production" and r["secret"].startswith("ayk_live_")
    assert r["rate_limit"] == 15 and r["expires_at"] is not None
    assert user_client.patch("/api/v1/settings", json={"timezone": "Mars/Base"}).status_code == 422


def test_profile_update_and_password_change(user_client):
    r = user_client.patch("/api/v1/profile", json={"display_name": "Ayaka K."})
    assert r.json()["data"]["display_name"] == "Ayaka K."
    # email change requires password
    assert user_client.patch("/api/v1/profile", json={"email": "new@example.com"}).status_code == 403
    r = user_client.patch("/api/v1/profile", json={"email": "new@example.com", "current_password": "Sup3r-secret!"})
    assert r.json()["data"]["email"] == "new@example.com"
    r = user_client.post("/api/v1/profile/change-password", json={
        "current_password": "wrong", "new_password": "N3w-password!", "confirm_password": "N3w-password!"})
    assert r.status_code == 403
    r = user_client.post("/api/v1/profile/change-password", json={
        "current_password": "Sup3r-secret!", "new_password": "N3w-password!", "confirm_password": "N3w-password!"})
    assert r.status_code == 200
    c = make_client()
    assert c.post("/api/v1/auth/login", json={"identifier": "ayaka", "password": "Sup3r-secret!"}).status_code == 401
    assert c.post("/api/v1/auth/login", json={"identifier": "ayaka", "password": "N3w-password!"}).status_code == 200


def test_activity_log_filters_and_export(user_client):
    k = create_key(user_client, name="=cmd|' /C calc'!A0")
    user_client.post(f"/api/v1/keys/{k['id']}/revoke")
    user_client.patch("/api/v1/settings", json={"date_format": "DD/MM/YYYY"})
    all_ = user_client.get("/api/v1/activity").json()
    types = {e["event_type"] for e in all_["data"]}
    assert {"auth.register", "auth.login", "key.created", "key.revoked", "settings.changed"} <= types
    only = user_client.get("/api/v1/activity?event_type=key.revoked").json()["data"]
    assert len(only) == 1
    prefix = user_client.get("/api/v1/activity?event_type=key.*").json()["data"]
    assert len(prefix) == 2
    detail = user_client.get(f"/api/v1/activity/{only[0]['id']}").json()["data"]
    assert detail["metadata"]["key_id"] == k["id"]
    csv = user_client.get("/api/v1/activity/export")
    assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv")
    assert "key.created" in csv.text and "\"'=cmd" not in csv.text.split("\n")[0]
    # No endpoint exists to modify or delete logs
    assert user_client.delete(f"/api/v1/activity/{only[0]['id']}").status_code in (404, 405)
    # Other users can't read it
    m = make_client()
    register(m, "mallory")
    assert m.get(f"/api/v1/activity/{only[0]['id']}").status_code == 404


def test_delete_account_requires_password(user_client):
    assert user_client.post("/api/v1/profile/delete-account",
                            json={"password": "wrong", "confirm": "DELETE"}).status_code == 403
    assert user_client.post("/api/v1/profile/delete-account",
                            json={"password": "Sup3r-secret!", "confirm": "nope"}).status_code == 422
    assert user_client.post("/api/v1/profile/delete-account",
                            json={"password": "Sup3r-secret!", "confirm": "DELETE"}).status_code == 200
    assert make_client().post("/api/v1/auth/login",
                              json={"identifier": "ayaka", "password": "Sup3r-secret!"}).status_code == 401


def test_error_envelope_and_security_headers(client):
    r = client.get("/api/v1/does-not-exist")
    assert r.status_code == 404
    body = r.json()
    assert body["success"] is False and body["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert "timestamp" in body["meta"]
    assert r.headers["X-Content-Type-Options"] == "nosniff" and "X-Request-ID" in r.headers
    ok = client.get("/api/v1/health").json()
    assert ok["success"] is True and "timestamp" in ok["meta"]


def test_notifications(user_client):
    r = user_client.get("/api/v1/dashboard/notifications")
    assert r.status_code == 200 and isinstance(r.json()["data"], list)


def test_static_pages_served(client):
    for path in ("/", "/login", "/dashboard", "/keys", "/docs", "/assets/css/global.css"):
        assert client.get(path).status_code == 200, path
