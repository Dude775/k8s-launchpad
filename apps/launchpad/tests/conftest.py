"""
Test fixtures providing an isolated Flask test app with a mocked K8s client
and in-memory MongoDB.

No real cluster, kubeconfig, or MongoDB/network is used in any test. The K8s
client is mocked by monkeypatching app.k8s.get_k8s_clients directly
(module-level function replacement). MongoDB is simulated via mongomock,
injected by monkeypatching the cx and db instance attributes on the shared
PyMongo singleton (Flask-PyMongo 3.x stores both directly on the PyMongo
instance, not in app.extensions) — mirrors apps/field-guide-api/tests/conftest.py.
"""

from unittest.mock import MagicMock

import mongomock
import pytest


@pytest.fixture
def app(monkeypatch):
    """Isolated Flask test app with in-memory MongoDB (no network).

    Flask-PyMongo 3.x init_app() sets self.cx and self.db directly on the
    PyMongo singleton. We replace both with mongomock equivalents after
    create_app() returns, so all subsequent DB access goes through the
    in-memory store. monkeypatch restores originals after each test.

    mongomock TTL limitation (RESEARCH Pitfall 1, D-10): mongomock accepts
    create_index("ts", expireAfterSeconds=...) and stores the option in its
    index metadata, but it has NO background expiry thread — documents never
    actually expire in tests. Tests therefore assert ONLY that the TTL index
    EXISTS with the right expireAfterSeconds value (via index_information());
    never that a document disappears. TTL expiry timing is verified live via
    smoke only (Phase 10). Do not write a test that sleeps then asserts an
    events count change.

    The platform_started once-per-process guard (D-12) is reset BEFORE
    create_app() so each isolated test app independently exercises the
    guard's first-call path — mirrors the k8s_disabled module-attribute
    idiom below.
    """
    import app.events as events_module

    from app import create_app
    from app.extensions import mongo

    events_module.reset_platform_started_guard_for_tests()

    application = create_app(
        {
            "TESTING": True,
            "MONGO_URI": "mongodb://localhost:27017/test_db",
            # create_app() now performs Mongo operations at startup
            # (ensure_indexes + emit_platform_started_once) against the real
            # (unreachable) localhost URI before mongomock is patched in
            # below. Those never-raise calls degrade silently; this short
            # server-selection timeout keeps that degradation fast so the
            # suite doesn't pay PyMongo's 2s default several times per test.
            "MONGO_SERVER_SELECTION_TIMEOUT_MS": 50,
        }
    )

    mock_client = mongomock.MongoClient()
    mock_db = mock_client["test_db"]

    # Patch the singleton's instance attributes; monkeypatch auto-restores on teardown.
    monkeypatch.setattr(mongo, "cx", mock_client)
    monkeypatch.setattr(mongo, "db", mock_db)

    yield application


@pytest.fixture
def client(app):
    """Flask test client using the isolated app."""
    return app.test_client()


@pytest.fixture
def k8s_disabled(monkeypatch):
    """Force app.k8s.get_k8s_clients() to return the disabled (None, None) state.

    This is the DEFAULT / expected state for local dev and CI (D-05, D-07) —
    it is a first-class tested path, not an error path.
    """
    import app.k8s as k8s_module

    monkeypatch.setattr(k8s_module, "get_k8s_clients", lambda: (None, None))
    return k8s_module


@pytest.fixture
def k8s_enabled(monkeypatch):
    """Force app.k8s.get_k8s_clients() to return mocked (CoreV1Api, AppsV1Api)
    instances, exercising the "cluster reachable" branch without a real cluster.
    """
    import app.k8s as k8s_module

    fake_core_v1 = MagicMock(name="CoreV1Api")
    fake_apps_v1 = MagicMock(name="AppsV1Api")
    monkeypatch.setattr(k8s_module, "get_k8s_clients", lambda: (fake_core_v1, fake_apps_v1))
    return fake_core_v1, fake_apps_v1


@pytest.fixture
def mongo_down(client, monkeypatch):
    """Test client that simulates a MongoDB outage.

    Patches the mongo reference inside health.py so that
    mongo.cx.admin.command("ping") raises ConnectionFailure, causing
    GET /health to return 503. Mirrors
    apps/field-guide-api/tests/conftest.py's mongo_down fixture.
    """
    import pymongo.errors
    import app.routes.health as health_module

    class _FakeCx:
        class admin:
            @staticmethod
            def command(*args, **kwargs):
                raise pymongo.errors.ConnectionFailure("MongoDB unreachable")

    class _FakeMongo:
        cx = _FakeCx()

    monkeypatch.setattr(health_module, "mongo", _FakeMongo())
    return client


@pytest.fixture
def mock_requests_get(monkeypatch):
    """Mock a successful `requests.get` call (field-guide-api reachable,
    STAT-02) — returns status_code=200."""
    import requests

    fake_response = MagicMock(status_code=200, json=lambda: {})
    monkeypatch.setattr(requests, "get", lambda *a, **kw: fake_response)
    return fake_response


@pytest.fixture
def mock_requests_get_unreachable(monkeypatch):
    """Mock a failing `requests.get` call (field-guide-api unreachable,
    STAT-02) — raises requests.exceptions.ConnectionError, exercising
    get_platform_status()'s degrade-gracefully branch."""
    import requests

    def _raise(*args, **kwargs):
        raise requests.exceptions.ConnectionError("connection refused")

    monkeypatch.setattr(requests, "get", _raise)
