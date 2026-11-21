import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from backend.database import get_engine, standalone_session
from backend.migrate import migrate, status
from backend.models import User, UserRecord
from backend.security import hash_password


def test_connection_and_health(client):
    r = client.get("/api/v1/health/database")
    assert r.status_code == 200 and r.json()["data"]["status"] == "ok"
    assert "0001_initial_schema.sql" in r.json()["data"]["migrations"]
    assert client.get("/api/v1/health").json()["data"]["status"] == "ok"


def test_migration_is_idempotent():
    assert migrate(verbose=False) == []
    s = status()
    assert s["pending"] == [] and s["modified"] == []


def test_crud_roundtrip():
    with standalone_session() as db:
        u = User(username="crud", email="crud@example.com", password_hash=hash_password("Passw0rd!"))
        db.add(u)
        db.flush()
        rec = UserRecord(user_id=u.id, collection="c", data={"v": 1})
        db.add(rec)
        db.flush()
        rid, uid = rec.id, u.id
    with standalone_session() as db:
        rec = db.get(UserRecord, rid)
        assert rec.data == {"v": 1}
        rec.data = {"v": 2}
    with standalone_session() as db:
        assert db.get(UserRecord, rid).data == {"v": 2}
        db.delete(db.get(User, uid))  # cascade
    with standalone_session() as db:
        assert db.get(UserRecord, rid) is None
        assert db.execute(select(User).where(User.id == uid)).first() is None


def test_constraints_enforced():
    with pytest.raises(IntegrityError):
        with standalone_session() as db:
            db.add(User(username="dup", email="d@example.com", password_hash="x"))
            db.add(User(username="DUP", email="e@example.com", password_hash="x"))
            db.flush()
    with pytest.raises(IntegrityError):
        with get_engine().begin() as conn:
            uid = conn.execute(text("INSERT INTO users (username,email,password_hash) VALUES "
                                    "('perm','p@example.com','x') RETURNING id")).scalar_one()
            conn.execute(text("INSERT INTO api_keys (user_id,name,key_prefix,key_hash,environment,permissions) "
                              "VALUES (:u,'k','ayk_test_x',repeat('a',64),'development',ARRAY['root'])"), {"u": uid})


def test_activity_logs_append_only(user_client):
    with pytest.raises(DBAPIError):
        with get_engine().begin() as conn:
            conn.execute(text("UPDATE activity_logs SET description = 'tampered'"))
