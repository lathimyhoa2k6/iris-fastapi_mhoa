"""Shared fixtures: the single-service app on a throw-away SQLite database."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Must be set before app / settings are imported.
_TMP = Path(tempfile.mkdtemp(prefix="iris-tests-"))
os.environ["DB_PATH"] = str(_TMP / "test.db")
os.environ["JWT_SECRET"] = "test-secret-key-that-is-long-enough-for-hs256"
os.environ["SERVICE_MODE"] = "single"

from fastapi.testclient import TestClient  # noqa: E402

import app as app_module  # noqa: E402

SETOSA = {"sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4, "petal_width": 0.2}
REG_INPUT = {"sepal_length": 5.8, "sepal_width": 3.0, "petal_length": 4.35, "species": "versicolor"}


@pytest.fixture(scope="session")
def client():
    with TestClient(app_module.app) as c:
        yield c


_counter = {"n": 0}


def _new_user(client, prefix: str = "user") -> dict:
    _counter["n"] += 1
    username = f"{prefix}{_counter['n']}"
    res = client.post("/db/auth/register", json={"username": username, "password": "secret123"})
    assert res.status_code == 201, res.text
    body = res.json()
    return {"username": username, "token": body["access_token"],
            "headers": {"Authorization": f"Bearer {body['access_token']}"}}


@pytest.fixture
def user(client):
    return _new_user(client)


@pytest.fixture
def other_user(client):
    return _new_user(client, "other")
