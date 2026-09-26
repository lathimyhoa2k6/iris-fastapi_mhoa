"""Registration and login: bcrypt password hashes, JWT access tokens."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

import security
from db_api.db import get_conn, utc_now

router = APIRouter(prefix="/auth", tags=["Tài khoản"])


class Credentials(BaseModel):
    username: str = Field(..., min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_.-]+$", examples=["demo"])
    password: str = Field(..., min_length=6, max_length=72, examples=["demo123"])

    @field_validator("password")
    @classmethod
    def bcrypt_limit(cls, value: str) -> str:
        # bcrypt only hashes the first 72 bytes; refuse longer UTF-8 passwords.
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Mật khẩu tối đa 72 byte")
        return value


def _token_response(user_id: int, username: str) -> dict:
    token, lifetime = security.create_token(user_id, username)
    return {"access_token": token, "token_type": "bearer", "expires_in": lifetime,
            "user": {"id": user_id, "username": username}}


def create_user(conn, username: str, password: str) -> int:
    """Insert a user with a bcrypt hash; raises sqlite3.IntegrityError if the name is taken."""
    cur = conn.execute(
        "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
        (username, security.hash_password(password), utc_now()),
    )
    conn.commit()
    return cur.lastrowid


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(body: Credentials, conn=Depends(get_conn)):
    """Create an account (password hashed with bcrypt) and log it in."""
    try:
        user_id = create_user(conn, body.username, body.password)
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Tên đăng nhập đã tồn tại")
    return _token_response(user_id, body.username)


@router.post("/login")
def login(body: Credentials, conn=Depends(get_conn)):
    """Exchange username + password for a JWT."""
    user = conn.execute("SELECT * FROM users WHERE username = ?", (body.username,)).fetchone()
    if user is None or not security.verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Sai tên đăng nhập hoặc mật khẩu")
    return _token_response(user["id"], user["username"])


@router.get("/me")
def me(user: dict = Depends(security.current_user), conn=Depends(get_conn)):
    row = conn.execute("SELECT id, username, created_at FROM users WHERE id = ?", (user["id"],)).fetchone()
    if row is None:
        raise HTTPException(401, "Tài khoản không còn tồn tại")
    count = conn.execute("SELECT COUNT(*) FROM predictions WHERE user_id = ?", (user["id"],)).fetchone()[0]
    return {**dict(row), "n_predictions": count}
