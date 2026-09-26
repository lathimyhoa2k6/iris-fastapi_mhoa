"""SQLite access for the database API, with numbered SQL migrations.

Each file in migrations/ runs once, in name order, and is recorded in the
schema_migrations table. Schema changes go into a new numbered file; existing
files are never edited, so existing data is never dropped.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import settings

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
_migrated: set[str] = set()
_lock = threading.Lock()


UTC_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime(UTC_FORMAT)


def local_tz() -> timezone:
    """Timezone used for date filters and Excel timestamps (Vietnam, UTC+7, by default)."""
    return timezone(timedelta(hours=float(settings.get("APP_TZ_OFFSET_HOURS", "7"))))


def date_bounds(date_from: date | None, date_to: date | None) -> tuple[str | None, str | None]:
    """Local calendar days -> UTC ISO bounds [start, end) for created_at comparisons."""

    def utc(d: date) -> str:
        return datetime.combine(d, time.min, local_tz()).astimezone(timezone.utc).strftime(UTC_FORMAT)

    return (utc(date_from) if date_from else None, utc(date_to + timedelta(days=1)) if date_to else None)


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Apply pending migrations and return the versions that were applied."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    done = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    applied = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = path.stem
        if version in done:
            continue
        conn.executescript(path.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)", (version, utc_now()))
        conn.commit()
        applied.append(version)
    return applied


def connect() -> sqlite3.Connection:
    """Open a connection to DB_PATH, creating and migrating the file on first use."""
    path = settings.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    key = str(path.resolve())
    if key not in _migrated:
        with _lock:
            if key not in _migrated:
                applied = migrate(conn)
                if applied:
                    print(f"[db] Applied migrations {applied} to {path}")
                _migrated.add(key)
    return conn


def get_conn():
    """FastAPI dependency: one connection per request."""
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()
