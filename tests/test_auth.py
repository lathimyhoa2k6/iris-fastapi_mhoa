"""R3.1: registration, bcrypt hashing, JWT login and protected routes."""

import sqlite3

import settings


def test_register_returns_token(client):
    res = client.post("/db/auth/register", json={"username": "alice", "password": "wonder1"})
    assert res.status_code == 201
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["username"] == "alice"
    assert body["access_token"].count(".") == 2  # header.payload.signature


def test_password_is_stored_as_bcrypt_hash(client):
    client.post("/db/auth/register", json={"username": "bob", "password": "builder1"})
    with sqlite3.connect(settings.db_path()) as conn:
        stored = conn.execute("SELECT password_hash FROM users WHERE username = 'bob'").fetchone()[0]
    assert stored != "builder1"
    assert stored.startswith("$2b$")


def test_duplicate_username_is_rejected(client):
    client.post("/db/auth/register", json={"username": "carol", "password": "secret1"})
    res = client.post("/db/auth/register", json={"username": "CAROL", "password": "secret1"})
    assert res.status_code == 409


def test_login_and_me(client):
    client.post("/db/auth/register", json={"username": "dave", "password": "secret1"})
    res = client.post("/db/auth/login", json={"username": "dave", "password": "secret1"})
    assert res.status_code == 200
    token = res.json()["access_token"]
    me = client.get("/db/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "dave"


def test_wrong_password_is_401(client):
    client.post("/db/auth/register", json={"username": "erin", "password": "secret1"})
    res = client.post("/db/auth/login", json={"username": "erin", "password": "wrong-pass"})
    assert res.status_code == 401


def test_protected_routes_need_a_valid_token(client):
    assert client.get("/db/auth/me").status_code == 401
    assert client.get("/db/predictions").status_code == 401
    bad = {"Authorization": "Bearer not-a-jwt"}
    assert client.get("/db/predictions", headers=bad).status_code == 401


def test_weak_input_is_422(client):
    assert client.post("/db/auth/register", json={"username": "ab", "password": "secret1"}).status_code == 422
    assert client.post("/db/auth/register", json={"username": "frank", "password": "123"}).status_code == 422
