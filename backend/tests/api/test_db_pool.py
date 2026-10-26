"""A pooled connection the server has closed (Neon suspends idle computes) is replaced on checkout, not a 500."""

from api import db


def test_dead_pooled_connection_is_replaced(client):
    with db.pool().connection() as conn:
        dead = conn
    dead.pgconn.finish()          # the connection is back in the pool but its socket is gone
    for _ in range(db.pool().max_size + 1):
        assert db.one("SELECT 1 AS x") == {"x": 1}
    r = client.get("/health")
    assert r.status_code == 200
