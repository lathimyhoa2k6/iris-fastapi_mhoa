"""Configuration shared by the three modules, read from the environment.

A `.env` file next to this module is loaded first (see .env.example); real
environment variables win over it. No secret has a default value.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv(path: Path = BASE_DIR / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def get(name: str, default: str | None = None) -> str | None:
    return os.environ.get(name, default)


def csv_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in (get(name, default) or "").split(",") if item.strip()]


def jwt_secret() -> str:
    """JWT signing key. Without JWT_SECRET a random per-process key is used, which
    only works when a single process both issues and verifies tokens."""
    secret = get("JWT_SECRET")
    if not secret:
        secret = secrets.token_urlsafe(48)
        os.environ["JWT_SECRET"] = secret
        print("[settings] WARNING: JWT_SECRET is not set; using a temporary random key.")
    return secret


# "single": app.py also mounts the database API and the web module (Render, one process).
# "split":  three separate processes on three ports (run.sh / run.ps1).
SERVICE_MODE = get("SERVICE_MODE", "single")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(get("JWT_EXPIRE_MINUTES", "720"))


def db_path() -> Path:
    """SQLite file of the database API (read at call time so tests can override it).

    A relative DB_PATH is taken relative to the project folder, not the shell's cwd.
    """
    path = Path(get("DB_PATH") or "data/app.db")
    return path if path.is_absolute() else BASE_DIR / path
