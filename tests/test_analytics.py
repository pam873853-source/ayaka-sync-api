from datetime import date, timedelta

from sqlalchemy import text

from backend.database import get_engine
from tests.conftest import create_key, make_client


def _seed(user_client):
    key = create_key(user_client, permissions=["read", "write"], rate_limit=1000)
    c = make_client()
    h = {"Authorization": f"Bearer {key['secret']}"}
    for _ in range(6):
        assert c.get("/api/v1/example", headers=h).status_code == 200
    for _ in range(2):
        assert c.get("/api/v1/records/not-a-uuid", headers=h).status_code == 404
    assert c.post("/api/v1/records", headers=h, json={"data": {}}).status_code == 201
    return key


def test_totals_success_and_error_rate(user_client):
    _seed(user_client)
    d = user_client.get("/api/v1/analytics/overview?range=24h").json()["data"]
    assert d["total"] == 9 and d["success"] == 7 and d["failed"] == 2
    assert d["success_rate"] == round(7 / 9 * 100, 2)
    assert d["error_rate"] == round(2 / 9 * 100, 2)
    assert d["calendar"]["today"] == 9
    dash = user_client.get("/api/v1/dashboard/overview").json()["data"]
    assert dash["total_requests"]["value"] == 9 and dash["failed_requests"]["value"] == 2
    assert dash["active_keys"]["value"] == 1


def test_empty_state_is_honest(user_client):
    d = user_client.get("/api/v1/analytics/overview?range=7d").json()["data"]
    assert d["total"] == 0 and d["success_rate"] is None and d["peak"] is None
    series = user_client.get("/api/v1/analytics/requests?range=7d").json()["data"]["series"]
    assert all(b["total"] == 0 for b in series) and len(series) >= 7


def test_period_filter(user_client):
    _seed(user_client)
    with get_engine().begin() as conn:
        conn.execute(text("UPDATE api_usage SET created_at = now() - interval '10 days' "
                          "WHERE id IN (SELECT id FROM api_usage ORDER BY id LIMIT 4)"))
    assert user_client.get("/api/v1/analytics/overview?range=24h").json()["data"]["total"] == 5
    assert user_client.get("/api/v1/analytics/overview?range=7d").json()["data"]["total"] == 5
    assert user_client.get("/api/v1/analytics/overview?range=30d").json()["data"]["total"] == 9
    today = date.today()
    start = (today - timedelta(days=11)).isoformat()
    end = (today - timedelta(days=9)).isoformat()
    r = user_client.get(f"/api/v1/analytics/overview?range=custom&start={start}&end={end}").json()
    assert r["data"]["total"] == 4
    assert user_client.get("/api/v1/analytics/overview?range=custom").status_code == 422


def test_breakdowns(user_client):
    key = _seed(user_client)
    eps = user_client.get("/api/v1/analytics/endpoints?range=24h").json()["data"]
    assert eps[0]["endpoint"] == "/api/v1/example" and eps[0]["total"] == 6
    keys = user_client.get("/api/v1/analytics/keys?range=24h").json()["data"]
    assert keys[0]["api_key_id"] == key["id"] and keys[0]["total"] == 9
    rt = user_client.get("/api/v1/analytics/response-times?range=24h").json()["data"]
    assert rt["avg_response_time_ms"] >= 0 and len(rt["series"]) >= 24
    rtm = user_client.get("/api/v1/analytics/realtime").json()["data"]
    assert rtm["requests_last_hour"] == 9 and len(rtm["per_minute"]) == 60
    assert rtm["top_endpoint"]["endpoint"] == "/api/v1/example"
