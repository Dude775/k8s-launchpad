"""
Test fixtures providing an isolated Flask test app with in-memory MongoDB.

No real MongoDB or network is used in any test. MongoDB is simulated via
mongomock, which is injected by replacing Flask-PyMongo's extension state
in app.extensions["pymongo"].

Fixtures:
    app         — test app with mocked MongoDB (fresh collection per test)
    client      — Flask test client derived from app
    mongo_down  — client where /health returns 503 (ping raises)
"""

import mongomock
import pytest


class _PyMongoState:
    """Flask-PyMongo extension state replacement.

    Supports both attribute access (state.cx) and dict-style access
    (state["cx"]) so it is compatible with any Flask-PyMongo 3.x
    internal access pattern.
    """

    def __init__(self, cx, db):
        self.cx = cx
        self.db = db

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, val):
        setattr(self, key, val)


@pytest.fixture
def app():
    """Isolated Flask test app with in-memory MongoDB.

    Steps:
    1. Create the real app (TESTING=True) — Flask-PyMongo registers a
       real MongoClient, but PyMongo connections are lazy so no network
       call happens in the constructor.
    2. Replace app.extensions["pymongo"] with mongomock equivalents.
    3. Drop the entries collection so each test starts clean.
    """
    from app import create_app

    application = create_app(
        {
            "TESTING": True,
            "MONGO_URI": "mongodb://localhost:27017/test_db",
        }
    )

    mock_client = mongomock.MongoClient()
    mock_db = mock_client["test_db"]

    # Replace Flask-PyMongo's stored state. The mongo.cx and mongo.db
    # properties read from current_app.extensions["pymongo"], so swapping
    # this dict makes all subsequent DB access go through mongomock.
    application.extensions["pymongo"] = _PyMongoState(mock_client, mock_db)

    # Ensure a clean slate for every test (order-independent tests).
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
    mongo.cx.admin.command("ping") raises a connection error, causing
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
