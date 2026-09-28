"""Password hashing (bcrypt) and JWT helpers.

The database API issues tokens; the model API only verifies them (same
JWT_SECRET) to protect POST /regression/train, without touching the database.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import settings

_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("ascii"))
    except ValueError:
        return False


def create_token(user_id: int, username: str) -> tuple[str, int]:
    """Return (token, lifetime in seconds)."""
    lifetime = settings.JWT_EXPIRE_MINUTES * 60
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": now,
        "exp": now + timedelta(seconds=lifetime),
    }
    return jwt.encode(payload, settings.jwt_secret(), algorithm=settings.JWT_ALGORITHM), lifetime


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret(), algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Phiên đăng nhập đã hết hạn, hãy đăng nhập lại")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token không hợp lệ")
    return {"id": int(payload["sub"]), "username": payload.get("username", "")}


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    """FastAPI dependency: the user carried by the `Authorization: Bearer` header."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Cần đăng nhập",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_token(credentials.credentials)
