"""API-AT-01 (accounts) and API-AT-07 (passwords and tokens never stored or logged in clear)."""

import logging
from datetime import datetime, timedelta, timezone

import jwt

from api import db, settings
from tests.api.conftest import new_user


def test_api_at_01_signup_login_me(client):
    u = new_user(client)
    r = client.post("/auth/login", json={"email": u["email"].upper(), "password": u["password"]})
    assert r.status_code == 200 and r.json()["user"]["email"] == u["email"]
    me = client.get("/auth/me", headers={"Authorization": f"Bearer {r.json()['token']}"})
    assert me.status_code == 200 and me.json()["id"] == u["id"]
    assert client.post("/auth/login", json={"email": u["email"], "password": "wrong password"}).status_code == 401
    dup = client.post("/auth/signup", json={"email": u["email"], "password": "another pass 2"})
    assert dup.status_code == 409 and dup.json()["error"] == "email_taken"
    expired = jwt.encode({"sub": u["id"], "iat": datetime.now(timezone.utc) - timedelta(days=8),
                          "exp": datetime.now(timezone.utc) - timedelta(days=1)}, settings.get().jwt_secret, algorithm="HS256")
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert r.status_code == 401 and r.json()["error"] == "session_expired"
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_signup_field_errors(client):
    r = client.post("/auth/signup", json={"email": "not-an-email", "password": "short"})
    assert r.status_code == 422 and set(r.json()["fields"]) == {"email", "password"}


def test_token_lifetime_is_seven_days(client):
    u = new_user(client)
    claims = jwt.decode(u["token"], settings.get().jwt_secret, algorithms=["HS256"])
    assert claims["exp"] - claims["iat"] == 7 * 24 * 3600


def test_api_at_07_no_clear_passwords_or_tokens(client, caplog):
    caplog.set_level(logging.DEBUG)
    pw = "s3cret-Passw0rd-x"
    u = new_user(client, password=pw)
    r = client.post("/auth/login", json={"email": u["email"], "password": pw})
    token = r.json()["token"]
    row = db.one("SELECT password_hash FROM {s}.users WHERE email = %s", u["email"])
    assert row["password_hash"].startswith("$2b$") and pw not in row["password_hash"]
    text = "\n".join(rec.getMessage() for rec in caplog.records)
    assert pw not in text and token not in text and u["token"] not in text
