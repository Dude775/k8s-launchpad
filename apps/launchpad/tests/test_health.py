"""
Health endpoint tests.

GET /health returns a plain 200 {"status": "ok"} with no Mongo check (D-04).
"""


def test_health_ok(client):
    """GET /health returns 200 {"status": "ok"}."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}
