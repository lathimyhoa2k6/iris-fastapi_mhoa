"""Registration and login: bcrypt password hashes, JWT access tokens."""

from __future__ import annotations

import pyodbc

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

import security
from db_api.db import get_conn, utc_now

router = APIRouter(prefix="/auth", tags=["Tài khoản"])


class Credentials(BaseModel):
    username: str = Field(
        ...,
        min_length=3,
        max_length=32,
        pattern=r"^[A-Za-z0-9_.-]+$",
        examples=["demo"],
    )
    password: str = Field(
        ...,
        min_length=6,
        max_length=72,
        examples=["demo123"],
    )

    @field_validator("password")
    @classmethod
    def bcrypt_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Mật khẩu tối đa 72 byte")
        return value


def _token_response(user_id: int, username: str) -> dict:
    token, lifetime = security.create_token(user_id, username)

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": lifetime,
        "user": {
            "id": user_id,
            "username": username,
        },
    }


def create_user(conn, username: str, password: str) -> int:
    """Insert a user with a bcrypt password hash."""

    password_hash = security.hash_password(password)

    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO users (username, password_hash, created_at)
        OUTPUT INSERTED.id
        VALUES (?, ?, ?)
        """,
        username,
        password_hash,
        utc_now(),
    )

    row = cursor.fetchone()

    if row is None:
        raise RuntimeError("Không lấy được ID tài khoản vừa tạo")

    user_id = int(row[0])

    conn.commit()

    return user_id


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    body: Credentials,
    conn=Depends(get_conn),
):
    """Create an account and log it in."""

    try:
        user_id = create_user(
            conn,
            body.username,
            body.password,
        )

    except pyodbc.IntegrityError:
        raise HTTPException(
            409,
            "Tên đăng nhập đã tồn tại",
        )

    return _token_response(
        user_id,
        body.username,
    )


@router.post("/login")
def login(
    body: Credentials,
    conn=Depends(get_conn),
):
    """Exchange username + password for a JWT."""

    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, username, password_hash
        FROM users
        WHERE username = ?
        """,
        body.username,
    )

    row = cursor.fetchone()

    if row is None:
        raise HTTPException(
            401,
            "Sai tên đăng nhập hoặc mật khẩu",
        )

    user_id = row[0]
    username = row[1]
    password_hash = row[2]

    if not security.verify_password(
        body.password,
        password_hash,
    ):
        raise HTTPException(
            401,
            "Sai tên đăng nhập hoặc mật khẩu",
        )

    return _token_response(
        user_id,
        username,
    )


@router.get("/me")
def me(
    user: dict = Depends(security.current_user),
    conn=Depends(get_conn),
):
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, username, created_at
        FROM users
        WHERE id = ?
        """,
        user["id"],
    )

    row = cursor.fetchone()

    if row is None:
        raise HTTPException(
            401,
            "Tài khoản không còn tồn tại",
        )

    cursor.execute(
        """
        SELECT COUNT(*)
        FROM predictions
        WHERE user_id = ?
        """,
        user["id"],
    )

    count = cursor.fetchone()[0]

    return {
        "id": row[0],
        "username": row[1],
        "created_at": row[2],
        "n_predictions": count,
    }