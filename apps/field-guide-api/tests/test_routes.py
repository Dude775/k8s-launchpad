"""
Route blueprint tests.
Task 2 RED phase: entries.py and health.py do not exist yet.
All tests must fail before Task 2 implementation is created.

Behavior under test:
- GET /entries returns 200 with a JSON array
- GET /entries/<id> returns 404 for malformed id (no 500)
- POST /entries without title/content returns 400
- GET /health returns 200 with {status, mongo} fields
- GET /metrics returns 200 with Prometheus text content
- create_app({'TESTING': True}) runs end to end with DEBUG False
"""

import pytest


@pytest.fixture
def app():
    """Isolated Flask test app instance with TESTING=True."""
    from app import create_app

    return create_app(
        {
            "TESTING": True,
            "MONGO_URI": "mongodb://localhost:27017/fieldguide_test",
        }
    )


@pytest.fixture
def client(app):
    """Flask test client derived from the test app fixture."""
    return app.test_client()


# --------------------------------------------------------------------------- #
# Factory smoke-test (moved from Task 1 — requires route modules to exist)    #
# --------------------------------------------------------------------------- #


def test_create_app_debug_false(app):
    """create_app() must produce an app with DEBUG=False even under TESTING."""
    assert app.config["DEBUG"] is False


# --------------------------------------------------------------------------- #
# Blueprint existence                                                           #
# --------------------------------------------------------------------------- #


def test_entries_blueprint_importable():
    """entries_bp must be importable from app.routes.entries."""
    from app.routes.entries import entries_bp

    assert entries_bp is not None
    assert entries_bp.name == "entries"


def test_health_blueprint_importable():
    """health_bp must be importable from app.routes.health."""
    from app.routes.health import health_bp

    assert health_bp is not None
    assert health_bp.name == "health"


# --------------------------------------------------------------------------- #
# POST /entries validation                                                      #
# --------------------------------------------------------------------------- #


def test_post_entries_empty_body_returns_400(client):
    """POST /entries with empty JSON body must return 400."""
    resp = client.post("/entries", json={})
    assert resp.status_code == 400


def test_post_entries_missing_content_returns_400(client):
    """POST /entries without 'content' field must return 400."""
    resp = client.post("/entries", json={"title": "only title"})
    assert resp.status_code == 400


def test_post_entries_missing_title_returns_400(client):
    """POST /entries without 'title' field must return 400."""
    resp = client.post("/entries", json={"content": "only content"})
    assert resp.status_code == 400


def test_post_entries_error_body_is_json(client):
    """POST /entries 400 response must include JSON error body."""
    resp = client.post("/entries", json={})
    data = resp.get_json()
    assert data is not None
    assert "error" in data


# --------------------------------------------------------------------------- #
# GET /entries/<id> — invalid ObjectId must return 404 not 500                 #
# --------------------------------------------------------------------------- #


def test_get_entry_malformed_id_returns_404(client):
    """GET /entries/<malformed> must return 404, not 500."""
    resp = client.get("/entries/not-a-valid-objectid")
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# GET /metrics                                                                  #
# --------------------------------------------------------------------------- #


def test_metrics_endpoint_returns_200(client):
    """GET /metrics must return 200."""
    resp = client.get("/metrics")
    assert resp.status_code == 200


def test_metrics_endpoint_has_prometheus_content(client):
    """GET /metrics body must contain Prometheus text markers."""
    resp = client.get("/metrics")
    data = resp.data
    assert b"# HELP" in data or b"python_info" in data
