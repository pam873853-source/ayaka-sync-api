import time

from backend.services import rate_limiter
from tests.conftest import create_key, make_client


def test_requests_within_limit(user_client):
    key = create_key(user_client, rate_limit=5)
    c = make_client()
    remaining = []
    for _ in range(5):
        r = c.get("/api/v1/example", headers={"Authorization": f"Bearer {key['secret']}"})
        assert r.status_code == 200
        remaining.append(int(r.headers["X-RateLimit-Remaining"]))
    assert remaining == [4, 3, 2, 1, 0]


def test_limit_reached_returns_429_with_headers(user_client):
    key = create_key(user_client, rate_limit=3)
    c = make_client()
    for _ in range(3):
        c.get("/api/v1/example", headers={"Authorization": f"Bearer {key['secret']}"})
    r = c.get("/api/v1/example", headers={"Authorization": f"Bearer {key['secret']}"})
    assert r.status_code == 429
    assert r.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    for h in ("X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset", "Retry-After"):
        assert h in r.headers
    assert r.headers["X-RateLimit-Remaining"] == "0"
    # Rejected request is still recorded as usage (status 429)
    rows = user_client.get("/api/v1/dashboard/recent-activity?status=4xx").json()["data"]
    assert rows and rows[0]["status_code"] == 429


def test_counter_is_shared_and_resets_next_window():
    now = time.time()
    window_start = int(now // 60) * 60
    for _ in range(2):
        assert rate_limiter.hit("unit:test", 2, 60, now=window_start + 1).allowed
    assert not rate_limiter.hit("unit:test", 2, 60, now=window_start + 2).allowed
    # next window
    assert rate_limiter.hit("unit:test", 2, 60, now=window_start + 61).allowed


def test_limits_are_per_key(user_client):
    a = create_key(user_client, rate_limit=1, name="a")
    b = create_key(user_client, rate_limit=1, name="b")
    c = make_client()
    assert c.get("/api/v1/example", headers={"Authorization": f"Bearer {a['secret']}"}).status_code == 200
    assert c.get("/api/v1/example", headers={"Authorization": f"Bearer {a['secret']}"}).status_code == 429
    assert c.get("/api/v1/example", headers={"Authorization": f"Bearer {b['secret']}"}).status_code == 200
