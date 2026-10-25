"""Test helper for UI-AT-05: copy a user's trip as a past trip in schema app_e2e_test (the API cannot create one).

    python make_past_trip.py <email>
"""
import os
import sys
from datetime import date, timedelta

os.environ["DB_SCHEMA"] = "app_e2e_test"
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

from api import db  # noqa: E402

row = db.one("SELECT t.* FROM {s}.trips t JOIN {s}.users u ON u.id = t.user_id WHERE u.email = %s ORDER BY t.created_at LIMIT 1",
             sys.argv[1].lower())
start = date.today() - timedelta(days=40)
req = dict(row["request"]) | {"start_date": start.isoformat(), "end_date": (start + timedelta(days=2)).isoformat()}
db.run("INSERT INTO {s}.trips (user_id, name, request, result, start_date) VALUES (%s, %s, %s, %s, %s)",
       row["user_id"], "Last month in Agra", db.jsonb(req), db.jsonb(row["result"]), start)
print("ok")
