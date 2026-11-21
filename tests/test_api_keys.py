from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from backend.database import get_engine
from tests.conftest import create_key, make_client, register


def bearer(secret):
    return {"Authorization": f"Bearer {secret}"}


def test_generate_key_format_and_hash_storage(user_client):
    data = create_key(user_client, environment="production")
    secret = data["secret"]
    assert secret.startswith("ayk_live_") and len(secret) == len("ayk_live_") + 40
    assert data["key_prefix"] == secret[:17]
    with get_engine().connect() as conn:
        stored = conn.execute(text("SELECT key_hash, key_prefix FROM api_keys")).one()
    assert secret not in stored.key_hash and len(stored.key_hash) == 64
    # The full secret is never returned again.
    listing = user_client.get("/api/v1/keys").json()
    assert "secret" not in listing["data"][0] and "key_hash" not in listing["data"][0]
    detail = user_client.get(f"/api/v1/keys/{data['id']}").json()["data"]
    assert "secret" not in detail and "key_hash" not in detail
    dev = create_key(user_client, environment="development")
    assert dev["secret"].startswith("ayk_test_")


def test_verify_key_and_usage_tracking(user_client):
    key = create_key(user_client)
    c = make_client()
    r = c.get("/api/v1/example", headers=bearer(key["secret"]))
    assert r.status_code == 200, r.text
    assert r.json()["data"]["key"]["prefix"] == key["key_prefix"]
    assert r.headers["X-RateLimit-Limit"] == "60" and r.headers["X-RateLimit-Remaining"] == "59"
    # X-API-Key header also works
    assert c.get("/api/v1/example", headers={"X-API-Key": key["secret"]}).status_code == 200
    with get_engine().connect() as conn:
        rows = conn.execute(text("SELECT endpoint, method, status_code FROM api_usage")).all()
    assert len(rows) == 2 and rows[0].endpoint == "/api/v1/example"
    # last_used_at updated
    assert user_client.get(f"/api/v1/keys/{key['id']}").json()["data"]["last_used_at"] is not None


def test_invalid_key(client):
    r = client.get("/api/v1/example", headers=bearer("ayk_test_" + "a" * 40))
    assert r.status_code == 401 and r.json()["error"]["code"] == "INVALID_API_KEY"
    r = client.get("/api/v1/example", headers=bearer("not-a-key"))
    assert r.status_code == 401 and r.json()["error"]["code"] == "INVALID_API_KEY"


def test_revoked_key_cannot_be_used(user_client):
    key = create_key(user_client)
    assert user_client.post(f"/api/v1/keys/{key['id']}/revoke").status_code == 200
    r = make_client().get("/api/v1/example", headers=bearer(key["secret"]))
    assert r.status_code == 401 and r.json()["error"]["code"] == "API_KEY_REVOKED"
    # revoked keys cannot be regenerated or edited
    assert user_client.post(f"/api/v1/keys/{key['id']}/regenerate").status_code == 409
    assert user_client.patch(f"/api/v1/keys/{key['id']}", json={"name": "x"}).status_code == 409
    # failed authentication is audited for the owner
    events = [e["event_type"] for e in user_client.get("/api/v1/activity").json()["data"]]
    assert "auth.failed" in events and "key.revoked" in events


def test_expired_key(user_client):
    key = create_key(user_client)
    with get_engine().begin() as conn:
        conn.execute(text("UPDATE api_keys SET expires_at = now() - interval '1 minute'"))
    r = make_client().get("/api/v1/example", headers=bearer(key["secret"]))
    assert r.status_code == 401 and r.json()["error"]["code"] == "API_KEY_EXPIRED"
    listed = user_client.get("/api/v1/keys?status=expired").json()["data"]
    assert len(listed) == 1 and listed[0]["status"] == "expired"


def test_expiration_must_be_future(user_client):
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    r = user_client.post("/api/v1/keys", json={"name": "x", "permissions": ["read"], "expires_at": past})
    assert r.status_code == 422


def test_disable_and_enable_key(user_client):
    key = create_key(user_client)
    user_client.patch(f"/api/v1/keys/{key['id']}", json={"enabled": False})
    r = make_client().get("/api/v1/example", headers=bearer(key["secret"]))
    assert r.status_code == 403 and r.json()["error"]["code"] == "API_KEY_DISABLED"
    user_client.patch(f"/api/v1/keys/{key['id']}", json={"enabled": True})
    assert make_client().get("/api/v1/example", headers=bearer(key["secret"])).status_code == 200


def test_regenerate_invalidates_old_secret(user_client):
    key = create_key(user_client)
    r = user_client.post(f"/api/v1/keys/{key['id']}/regenerate")
    new = r.json()["data"]["secret"]
    assert new != key["secret"]
    c = make_client()
    assert c.get("/api/v1/example", headers=bearer(key["secret"])).status_code == 401
    assert c.get("/api/v1/example", headers=bearer(new)).status_code == 200


def test_permission_validation(user_client):
    read_only = create_key(user_client, permissions=["read"])
    c = make_client()
    h = bearer(read_only["secret"])
    assert c.get("/api/v1/records", headers=h).status_code == 200
    r = c.post("/api/v1/records", headers=h, json={"data": {"a": 1}})
    assert r.status_code == 403 and r.json()["error"]["code"] == "PERMISSION_DENIED"
    assert c.get("/api/v1/analytics/overview", headers=h).status_code == 403
    assert c.get("/api/v1/profile", headers=h).status_code == 403
    assert c.get("/api/v1/keys", headers=h).status_code == 403
    # API keys can never reach session-only endpoints (key creation, settings...)
    assert c.post("/api/v1/keys", headers=h, json={"name": "x"}).status_code == 403

    rw = create_key(user_client, permissions=["read", "write", "delete", "analytics", "profile"])
    h2 = bearer(rw["secret"])
    rec = c.post("/api/v1/records", headers=h2, json={"collection": "notes", "data": {"a": 1}})
    assert rec.status_code == 201
    rid = rec.json()["data"]["id"]
    assert c.patch(f"/api/v1/records/{rid}", headers=h2, json={"data": {"a": 2}}).json()["data"]["data"] == {"a": 2}
    assert c.get("/api/v1/analytics/overview", headers=h2).status_code == 200
    assert c.get("/api/v1/profile", headers=h2).status_code == 200
    assert c.delete(f"/api/v1/records/{rid}", headers=h).status_code == 403
    assert c.delete(f"/api/v1/records/{rid}", headers=h2).status_code == 200


def test_admin_requires_password_and_is_not_default(user_client):
    key = create_key(user_client)
    assert key["permissions"] == ["read"]
    r = user_client.post("/api/v1/keys", json={"name": "adm", "permissions": ["admin"]})
    assert r.status_code == 403
    r = user_client.post("/api/v1/keys", json={"name": "adm", "permissions": ["admin"], "current_password": "nope"})
    assert r.status_code == 403
    adm = create_key(user_client, name="adm", permissions=["admin"], current_password="Sup3r-secret!")
    # escalation via PATCH also requires password
    r = user_client.patch(f"/api/v1/keys/{key['id']}", json={"permissions": ["read", "admin"]})
    assert r.status_code == 403
    # admin key can list and revoke keys over the API
    c = make_client()
    assert c.get("/api/v1/keys", headers=bearer(adm["secret"])).status_code == 200
    assert c.post(f"/api/v1/keys/{key['id']}/revoke", headers=bearer(adm["secret"])).status_code == 200


def test_unknown_permission_rejected(user_client):
    r = user_client.post("/api/v1/keys", json={"name": "x", "permissions": ["superuser"]})
    assert r.status_code == 422
    r = user_client.post("/api/v1/keys", json={"name": "x", "permissions": []})
    assert r.status_code == 422


def test_allowed_endpoints_restriction(user_client):
    key = create_key(user_client, permissions=["read"], allowed_endpoints=["/api/v1/records/*"])
    c = make_client()
    assert c.get("/api/v1/records", headers=bearer(key["secret"])).status_code == 200
    r = c.get("/api/v1/example", headers=bearer(key["secret"]))
    assert r.status_code == 403


def test_ownership_protection(user_client):
    key = create_key(user_client)
    rec_key = create_key(user_client, permissions=["read", "write"])
    c = make_client()
    rec = c.post("/api/v1/records", headers=bearer(rec_key["secret"]), json={"data": {"secret": 1}}).json()["data"]

    mallory = make_client()
    register(mallory, "mallory")
    for method, path in (("get", f"/api/v1/keys/{key['id']}"), ("patch", f"/api/v1/keys/{key['id']}"),
                         ("post", f"/api/v1/keys/{key['id']}/revoke"), ("post", f"/api/v1/keys/{key['id']}/regenerate"),
                         ("delete", f"/api/v1/keys/{key['id']}"), ("get", f"/api/v1/records/{rec['id']}")):
        kwargs = {"json": {"name": "pwn"}} if method == "patch" else {}
        r = getattr(mallory, method)(path, **kwargs)
        assert r.status_code == 404, (method, path, r.text)
    assert mallory.get("/api/v1/keys").json()["data"] == []
    assert mallory.get("/api/v1/dashboard/recent-activity").json()["data"] == []
    # Owner still has the key
    assert user_client.get(f"/api/v1/keys/{key['id']}").status_code == 200


def test_list_filters_search_sort_pagination(user_client):
    for i in range(5):
        create_key(user_client, name=f"svc-{i}", environment="production" if i % 2 else "development")
    r = user_client.get("/api/v1/keys?environment=production").json()
    assert r["meta"]["total"] == 2
    assert user_client.get("/api/v1/keys?search=svc-3").json()["data"][0]["name"] == "svc-3"
    asc = user_client.get("/api/v1/keys?sort=created_asc").json()["data"]
    assert asc[0]["name"] == "svc-0"
    page = user_client.get("/api/v1/keys?per_page=2&page=3").json()
    assert len(page["data"]) == 1 and page["meta"]["total_pages"] == 3


def test_delete_key(user_client):
    key = create_key(user_client)
    assert user_client.delete(f"/api/v1/keys/{key['id']}").status_code == 200
    assert user_client.get(f"/api/v1/keys/{key['id']}").status_code == 404
    assert make_client().get("/api/v1/example", headers=bearer(key["secret"])).status_code == 401


def test_rename_key(user_client):
    key = create_key(user_client)
    r = user_client.patch(f"/api/v1/keys/{key['id']}", json={"name": "Renamed", "rate_limit": 120})
    assert r.json()["data"]["name"] == "Renamed" and r.json()["data"]["rate_limit"] == 120
