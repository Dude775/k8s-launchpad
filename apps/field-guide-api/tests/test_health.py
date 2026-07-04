"""
Health endpoint tests.

Covers both readiness states:
    GET /health  200 {"status":"ok","mongo":"up"}   — MongoDB responds
    GET /health  503 {"status":"unavailable","mongo":"down"}  — MongoDB unreachable

The mongo_down fixture patches health.py's mongo reference so the ping
raises a ConnectionFailure, exercising the 503 branch without any real DB.
"""

import pytest


def test_health_up(client):
    """GET /health returns 200 with mongo='up' when MongoDB responds to ping."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["mongo"] == "up"


def test_health_down(mongo_down):
    """GET /health returns 503 with mongo='down' when MongoDB is unreachable."""
    resp = mongo_down.get("/health")
    assert resp.status_code == 503
    data = resp.get_json()
    assert data["mongo"] == "down"
