"""
Health endpoint tests.

GET /health pings ONLY launchpad's own MongoDB (STAT-03):
- 200 {"status": "ok", "mongo": "up"} when the ping succeeds (mongomock).
- 503 {"status": "unavailable", "mongo": "down"} when the ping raises
  (mongo_down fixture).

This route never touches field-guide-api — see app/status.py for the
cross-service reachability check.
"""


def test_health_ok(client):
    """GET /health returns 200 {"status": "ok", "mongo": "up"} when Mongo is up."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok", "mongo": "up"}


def test_health_unavailable_when_mongo_down(mongo_down):
    """GET /health returns 503 {"status": "unavailable", "mongo": "down"} when
    the Mongo ping raises."""
    resp = mongo_down.get("/health")
    assert resp.status_code == 503
    assert resp.get_json() == {"status": "unavailable", "mongo": "down"}
