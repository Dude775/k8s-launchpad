"""
Route blueprint structural tests.

Uses the shared conftest.py fixtures (mocked MongoDB via mongomock) — this
file deliberately defines NO local app/client fixtures so no test here can
ever touch a real database (previously local fixtures shadowed conftest's
mocked ones, leaving a trap for future DB-touching tests).

Behavior under test (unique to this file):
- entries_bp / health_bp are importable blueprints with the expected names
- create_app({'TESTING': True}) produces an app with DEBUG False

Endpoint behavior (POST /entries validation, malformed-id 404, /metrics)
is covered in test_entries.py and test_metrics.py — not duplicated here.
"""


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
