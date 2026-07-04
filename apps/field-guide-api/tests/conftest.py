"""
Test fixtures providing an isolated Flask test app with in-memory MongoDB.

No real MongoDB or network is used in any test. MongoDB is simulated via
mongomock, which is injected by monkeypatching the cx and db instance
attributes on the shared PyMongo singleton (Flask-PyMongo 3.x stores both
directly on the PyMongo instance, not in app.extensions).

Fixtures:
    app         — test app with mocked MongoDB (fresh collection per test)
    client      — Flask test client derived from app
    mongo_down  — client where /health returns 503 (ping raises)
"""

import mongomock
import pytest


@pytest.fixture
def app(monkeypatch):
    """Isolated Flask test app with in-memory MongoDB (no network).

    Flask-PyMongo 3.x init_app() sets self.cx and self.db directly on the
    PyMongo singleton. We replace both with mongomock equivalents after
    create_app() returns, so all subsequent DB access goes through the
    in-memory store. monkeypatch restores originals after each test.
    """
    from app import create_app
    from app.extensions import mongo

    # create_app sets mongo.cx = MongoClient(connect=False) — lazy, no socket yet.
    application = create_app(
        {
            "TESTING": True,
            "MONGO_URI": "mongodb://localhost:27017/test_db",
        }
    )

    mock_client = mongomock.MongoClient()
    mock_db = mock_client["test_db"]

    # Patch the singleton's instance attributes; monkeypatch auto-restores on teardown.
    monkeypatch.setattr(mongo, "cx", mock_client)
    monkeypatch.setattr(mongo, "db", mock_db)

    # Ensure clean slate for every test (order-independent execution).
    mock_db.entries.drop()

    yield application


@pytest.fixture
def client(app):
    """Flask test client using the mocked app."""
    return app.test_client()


@pytest.fixture
def mongo_down(client, monkeypatch):
    """Test client that simulates a MongoDB outage.

    Patches the mongo reference inside health.py so that
    mongo.cx.admin.command("ping") raises ConnectionFailure, causing
    GET /health to return 503.
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
