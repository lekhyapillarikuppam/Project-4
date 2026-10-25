"""Passwords (bcrypt) and sessions (JWT HS256, api.jwt_days expiry) — API-FR-01, API-FR-02, NFR-003.

Passwords and tokens are never logged.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from api import db, settings
from api.errors import ApiError
from tripwise import config

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_bearer = HTTPBearer(auto_error=False)


def normalise_email(email: str) -> str:
    return email.strip().lower()


def check_credentials(email: str, password: str) -> dict:
    """Field errors for a sign-up email and password."""
    lo, hi = config.default().api["password_len"]
    errs = {}
    if not EMAIL.match(email):
        errs["email"] = "Enter a valid email address."
    if not lo <= len(password) <= hi:
        errs["password"] = f"Password must be {lo}–{hi} characters."
    return errs


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("ascii"))
    except ValueError:
        return False


def make_token(user_id: str) -> str:
    now = datetime.now(timezone.utc)
    claims = {"sub": str(user_id), "iat": now, "exp": now + timedelta(days=config.default().api["jwt_days"])}
    return jwt.encode(claims, settings.get().jwt_secret, algorithm="HS256")


def current_user(cred: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    if cred is None or cred.scheme.lower() != "bearer":
        raise ApiError(401, "Please log in.")
    try:
        claims = jwt.decode(cred.credentials, settings.get().jwt_secret, algorithms=["HS256"], options={"require": ["exp", "sub"]})
    except jwt.ExpiredSignatureError:
        raise ApiError(401, "Your session has expired. Please log in again.", "session_expired")
    except jwt.InvalidTokenError:
        raise ApiError(401, "Please log in.")
    user = db.one("SELECT id, email, created_at FROM {s}.users WHERE id::text = %s", claims["sub"])
    if user is None:
        raise ApiError(401, "Please log in.")
    return user
