"""Minimal, safe SQL migration runner.

* Applies ``migrations/NNNN_*.sql`` files in order, each inside a transaction.
* Records applied versions + checksum in ``schema_migrations``.
* Refuses to run files containing destructive statements (DROP TABLE, DROP COLUMN,
  TRUNCATE, DELETE FROM) unless ``--allow-destructive`` is passed explicitly, and
  never allows that flag when APP_ENV=production.
* Uses a PostgreSQL advisory lock so concurrent deploys cannot apply twice.

Usage::

    python -m backend.migrate            # apply pending migrations
    python -m backend.migrate --status   # list applied / pending
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

from sqlalchemy import text

from .config import get_settings
from .database import get_engine

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
LOCK_ID = 727_115_001
DESTRUCTIVE = re.compile(r"\b(DROP\s+TABLE|DROP\s+COLUMN|TRUNCATE|DELETE\s+FROM|DROP\s+SCHEMA)\b", re.I)


def _files() -> list[Path]:
    return sorted(p for p in MIGRATIONS_DIR.glob("*.sql") if re.match(r"^\d{4}_", p.name))


def _strip_comments(sql: str) -> str:
    return "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))


def status() -> dict:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version VARCHAR(255) PRIMARY KEY, checksum CHAR(64) NOT NULL,"
            " applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        ))
        applied = {r[0]: r[1] for r in conn.execute(text("SELECT version, checksum FROM schema_migrations"))}
    files = _files()
    return {
        "applied": [f.name for f in files if f.name in applied],
        "pending": [f.name for f in files if f.name not in applied],
        "modified": [
            f.name for f in files
            if f.name in applied and applied[f.name] != hashlib.sha256(f.read_bytes()).hexdigest()
        ],
    }


def migrate(allow_destructive: bool = False, verbose: bool = True) -> list[str]:
    settings = get_settings()
    if allow_destructive and settings.is_production:
        raise SystemExit("Refusing destructive migrations with APP_ENV=production.")
    engine = get_engine()
    applied_now: list[str] = []
    # One transaction for the whole batch: either every pending migration applies or none.
    # pg_advisory_xact_lock serialises concurrent runners and is released on commit/rollback.
    with engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": LOCK_ID})
        conn.execute(text(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version VARCHAR(255) PRIMARY KEY, checksum CHAR(64) NOT NULL,"
            " applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        ))
        done = {r[0] for r in conn.execute(text("SELECT version FROM schema_migrations"))}
        for path in _files():
            if path.name in done:
                continue
            sql = path.read_text(encoding="utf-8")
            if DESTRUCTIVE.search(_strip_comments(sql)) and not allow_destructive:
                raise SystemExit(
                    f"{path.name} contains destructive statements; review it and rerun "
                    "with --allow-destructive outside production."
                )
            conn.exec_driver_sql(sql)
            conn.execute(
                text("INSERT INTO schema_migrations (version, checksum) VALUES (:v, :c)"),
                {"v": path.name, "c": hashlib.sha256(path.read_bytes()).hexdigest()},
            )
            applied_now.append(path.name)
            if verbose:
                print(f"applied {path.name}")
    if verbose and not applied_now:
        print("database is up to date")
    return applied_now


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ayaka Sync API migrations")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--allow-destructive", action="store_true")
    args = parser.parse_args(argv)
    if args.status:
        s = status()
        for key in ("applied", "pending", "modified"):
            print(f"{key}: {', '.join(s[key]) or '-'}")
        return 0
    migrate(allow_destructive=args.allow_destructive)
    return 0


if __name__ == "__main__":
    sys.exit(main())
