"""API test fixtures: schema app_test in the Neon database, dropped and recreated per session."""

import os
import uuid

os.environ["DB_SCHEMA"] = "app_test"     # before api.settings is first read

import pytest  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from api.settings import ROOT  # noqa: E402

load_dotenv(ROOT / ".env")
if not os.environ.get("DATABASE_URL") or not os.environ.get("JWT_SECRET"):
    pytest.skip("DATABASE_URL / JWT_SECRET not set", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402

from api import db  # noqa: E402
from api.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    db.drop_schema("app_test")
    db.create_schema("app_test")
    with TestClient(app) as c:
        yield c
    db.close()


def new_user(client, password="correct horse 1"):
    email = f"user-{uuid.uuid4().hex[:10]}@Example.com"
    r = client.post("/auth/signup", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    token = r.json()["token"]
    return {"email": email.lower(), "password": password, "token": token, "id": r.json()["user"]["id"],
            "h": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
def user(client):
    return new_user(client)
