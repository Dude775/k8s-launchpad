"""
app.catalog never-raise repo helper tests (CAT-02, CAT-03 data layer).

Mirrors test_status.py's shape: call the helper inside `with
app.app_context():`, assert on the returned tuple/list/dict. Every failure
path must degrade to a safe sentinel — no function in app.catalog may ever
raise past its own boundary.
"""

import pytest

from app import catalog


class _Boom:
    """Any attribute access raises — simulates a dead MongoDB collection."""

    def __getattr__(self, item):
        raise RuntimeError("mongo unavailable")


class _FakeDB:
    services = _Boom()
    events = _Boom()


class _FakeMongo:
    db = _FakeDB()


@pytest.fixture
def broken_mongo(monkeypatch):
    """Replace app.catalog's mongo singleton with one whose collections raise
    on every operation, exercising the never-raise degradation paths."""
    import app.catalog as catalog_module

    monkeypatch.setattr(catalog_module, "mongo", _FakeMongo())


def _service(name="my-service", **overrides):
    doc = {
        "name": name,
        "repo_url": "https://github.com/org/repo",
        "owner": "team-platform",
        "description": "",
        "environment": "dev",
    }
    doc.update(overrides)
    return doc


# --- register_service ------------------------------------------------------


def test_register_service_persists_and_returns_true(app):
    with app.app_context():
        catalog.ensure_indexes()
        ok, error = catalog.register_service(_service())

    assert ok is True
    assert error is None

    from app.extensions import mongo

    stored = mongo.db.services.find_one({"name": "my-service"})
    assert stored is not None
    assert stored["owner"] == "team-platform"
    # register_service stamps registered_at so list_services' sort key
    # always exists.
    assert "registered_at" in stored


def test_register_service_duplicate_name_returns_locked_error(app):
    """Second insert with the same name returns (False, locked copy) and
    writes no second document — DuplicateKeyError never escapes."""
    from app.extensions import mongo

    with app.app_context():
        catalog.ensure_indexes()
        first_ok, _ = catalog.register_service(_service())
        second_ok, error = catalog.register_service(_service())

    assert first_ok is True
    assert second_ok is False
    assert error == "This name is already registered — choose another."
    assert mongo.db.services.count_documents({}) == 1


def test_register_service_generic_failure_returns_false(app, broken_mongo):
    with app.app_context():
        ok, error = catalog.register_service(_service())

    assert ok is False
    assert error == "Could not save this service. Check the fields below and try again."


# --- list_services ----------------------------------------------------------


def test_list_services_sorted_by_registered_at_descending(app):
    with app.app_context():
        catalog.ensure_indexes()
        catalog.register_service(_service("svc-oldest"))
        catalog.register_service(_service("svc-middle"))
        catalog.register_service(_service("svc-newest"))
        # Make the sort deterministic even at equal-clock resolution.
        from datetime import datetime, timedelta, timezone

        from app.extensions import mongo

        base = datetime.now(timezone.utc)
        for offset, name in enumerate(["svc-oldest", "svc-middle", "svc-newest"]):
            mongo.db.services.update_one(
                {"name": name},
                {"$set": {"registered_at": base + timedelta(minutes=offset)}},
            )

        services = catalog.list_services()

    assert [s["name"] for s in services] == ["svc-newest", "svc-middle", "svc-oldest"]


def test_list_services_empty_collection_returns_empty_list(app):
    with app.app_context():
        assert catalog.list_services() == []


def test_list_services_db_error_returns_empty_list(app, broken_mongo):
    with app.app_context():
        assert catalog.list_services() == []


# --- get_service -------------------------------------------------------------


def test_get_service_returns_matching_document(app):
    with app.app_context():
        catalog.ensure_indexes()
        catalog.register_service(_service())
        found = catalog.get_service("my-service")

    assert found is not None
    assert found["name"] == "my-service"


def test_get_service_absent_name_returns_none(app):
    with app.app_context():
        assert catalog.get_service("no-such-service") is None


def test_get_service_db_error_returns_none(app, broken_mongo):
    with app.app_context():
        assert catalog.get_service("my-service") is None


# --- deregister_service -------------------------------------------------------


def test_deregister_service_true_when_document_removed(app):
    from app.extensions import mongo

    with app.app_context():
        catalog.ensure_indexes()
        catalog.register_service(_service())
        removed = catalog.deregister_service("my-service")

    assert removed is True
    assert mongo.db.services.count_documents({}) == 0


def test_deregister_service_false_when_name_absent(app):
    with app.app_context():
        assert catalog.deregister_service("no-such-service") is False


def test_deregister_service_false_on_db_error(app, broken_mongo):
    with app.app_context():
        assert catalog.deregister_service("my-service") is False


# --- ensure_indexes ------------------------------------------------------------


def test_ensure_indexes_creates_unique_name_index_idempotently(app):
    """Calling ensure_indexes twice never raises; the unique index on name
    exists afterwards."""
    from app.extensions import mongo

    with app.app_context():
        catalog.ensure_indexes()
        catalog.ensure_indexes()

    info = mongo.db.services.index_information()
    assert "name_1" in info
    assert info["name_1"].get("unique") is True


def test_ensure_indexes_never_raises_on_db_failure(app, broken_mongo):
    with app.app_context():
        catalog.ensure_indexes()  # must not raise
