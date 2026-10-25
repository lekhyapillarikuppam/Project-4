"""Sign up, log in, current user (API-FR-01). Log out is client-side: the token is discarded."""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api import auth, db
from api.errors import ApiError

router = APIRouter(prefix="/auth", tags=["auth"])


class Credentials(BaseModel):
    email: str
    password: str


def _user(row: dict) -> dict:
    return {"id": str(row["id"]), "email": row["email"]}


@router.post("/signup", status_code=201)
def signup(body: Credentials) -> dict:
    email = auth.normalise_email(body.email)
    errs = auth.check_credentials(email, body.password)
    if errs:
        raise ApiError(422, "Some fields are not valid.", "invalid", errs)
    try:
        row = db.one("INSERT INTO {s}.users (email, password_hash) VALUES (%s, %s) RETURNING id, email",
                     email, auth.hash_password(body.password))
    except psycopg.errors.UniqueViolation:
        raise ApiError(409, "An account with this email already exists.", "email_taken", {"email": "Already registered."})
    return {"token": auth.make_token(row["id"]), "user": _user(row)}


@router.post("/login")
def login(body: Credentials) -> dict:
    row = db.one("SELECT id, email, password_hash FROM {s}.users WHERE email = %s", auth.normalise_email(body.email))
    if row is None or not auth.verify_password(body.password, row["password_hash"]):
        raise ApiError(401, "Wrong email or password.", "bad_credentials")
    return {"token": auth.make_token(row["id"]), "user": _user(row)}


@router.get("/me")
def me(user: dict = Depends(auth.current_user)) -> dict:
    return _user(user)
