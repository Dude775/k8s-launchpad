"""
app.events never-raise events helper tests (FEED-02, FEED-03, D-10, D-12).

Covers the event writer, the TTL index (existence + expireAfterSeconds value
only — mongomock cannot verify expiry timing, see conftest.py), and the
platform_started once-per-process guard's first-call / second-call /
after-reset / write-failed paths.
"""

from datetime import datetime, timedelta, timezone

import pytest

from app import events


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
    """Replace app.events' mongo singleton with one whose collections raise
    on every operation, exercising the never-raise degradation paths."""
    import app.events as events_module

    monkeypatch.setattr(events_module, "mongo", _FakeMongo())


# --- record_event ------------------------------------------------------------


def test_record_event_inserts_document_and_returns_true(app):
    from app.extensions import mongo

    with app.app_context():
        ok = events.record_event("service_registered", "my-service")

    assert ok is True
    stored = mongo.db.events.find_one({"type": "service_registered"})
    assert stored is not None
    assert stored["service_name"] == "my-service"
    assert isinstance(stored["ts"], datetime)


def test_record_event_returns_false_on_failure(app, broken_mongo):
    with app.app_context():
        assert events.record_event("service_registered", "my-service") is False


# --- list_recent_events --------------------------------------------------------


def _seed_events(mongo, count=3):
    base = datetime.now(timezone.utc)
    for offset in range(count):
        mongo.db.events.insert_one(
            {
                "type": "service_registered",
                "service_name": f"svc-{offset}",
                "ts": base + timedelta(minutes=offset),
            }
        )


def test_list_recent_events_newest_first(app):
    from app.extensions import mongo

    _seed_events(mongo, 3)
    with app.app_context():
        recent = events.list_recent_events()

    assert [e["service_name"] for e in recent] == ["svc-2", "svc-1", "svc-0"]


def test_list_recent_events_caps_at_limit(app):
    from app.extensions import mongo

    _seed_events(mongo, 5)
    with app.app_context():
        recent = events.list_recent_events(limit=2)

    assert len(recent) == 2
    assert [e["service_name"] for e in recent] == ["svc-4", "svc-3"]


def test_list_recent_events_empty_returns_empty_list(app):
    with app.app_context():
        assert events.list_recent_events() == []


def test_list_recent_events_db_error_returns_empty_list(app, broken_mongo):
    with app.app_context():
        assert events.list_recent_events() == []


# --- get_events_for_service -----------------------------------------------------


def test_get_events_for_service_filters_and_sorts_newest_first(app):
    from app.extensions import mongo

    base = datetime.now(timezone.utc)
    mongo.db.events.insert_one(
        {"type": "service_registered", "service_name": "svc-a", "ts": base}
    )
    mongo.db.events.insert_one(
        {
            "type": "service_deregistered",
            "service_name": "svc-a",
            "ts": base + timedelta(minutes=1),
        }
    )
    mongo.db.events.insert_one(
        {"type": "service_registered", "service_name": "svc-b", "ts": base}
    )

    with app.app_context():
        for_a = events.get_events_for_service("svc-a")

    assert [e["type"] for e in for_a] == ["service_deregistered", "service_registered"]
    assert all(e["service_name"] == "svc-a" for e in for_a)


def test_get_events_for_service_db_error_returns_empty_list(app, broken_mongo):
    with app.app_context():
        assert events.get_events_for_service("svc-a") == []


# --- ensure_indexes (TTL) --------------------------------------------------------


def test_ensure_indexes_ttl_expire_after_seconds_default(app):
    """TTL index on ts exists with expireAfterSeconds == 604800 (7-day
    default, D-10). Index EXISTENCE only — never expiry timing (see
    conftest.py mongomock TTL note)."""
    from app.extensions import mongo

    with app.app_context():
        events.ensure_indexes()
        events.ensure_indexes()  # idempotent — second call must not raise

    info = mongo.db.events.index_information()
    assert "ts_1" in info
    assert info["ts_1"].get("expireAfterSeconds") == 604800


def test_ensure_indexes_never_raises_on_db_failure(app, broken_mongo):
    with app.app_context():
        events.ensure_indexes()  # must not raise


# --- platform_started guard (D-12) -------------------------------------------------


def test_emit_platform_started_once_fires_exactly_once_then_again_after_reset(app):
    import app.events as events_module

    from app.extensions import mongo

    with app.app_context():
        events_module.reset_platform_started_guard_for_tests()
        events_module.emit_platform_started_once()
        first_count = mongo.db.events.count_documents({"type": "platform_started"})

        events_module.emit_platform_started_once()
        second_count = mongo.db.events.count_documents({"type": "platform_started"})

        events_module.reset_platform_started_guard_for_tests()
        events_module.emit_platform_started_once()
        after_reset_count = mongo.db.events.count_documents({"type": "platform_started"})

    assert first_count == 1
    assert second_count == 1  # second call in same process writes nothing
    assert after_reset_count == 2


def test_emit_platform_started_guard_not_set_when_write_fails(app, monkeypatch):
    """If record_event returns False (Mongo unreachable), the guard flag must
    NOT be set — a later readiness can still fire the event (D-12)."""
    import app.events as events_module

    from app.extensions import mongo

    with app.app_context():
        events_module.reset_platform_started_guard_for_tests()

        original_record_event = events_module.record_event
        monkeypatch.setattr(events_module, "record_event", lambda *a, **k: False)
        events_module.emit_platform_started_once()

        assert events_module._platform_started_emitted is False
        assert mongo.db.events.count_documents({"type": "platform_started"}) == 0

        monkeypatch.setattr(events_module, "record_event", original_record_event)
        events_module.emit_platform_started_once()

        assert events_module._platform_started_emitted is True
        assert mongo.db.events.count_documents({"type": "platform_started"}) == 1


# --- _relative_time ------------------------------------------------------------------


def test_relative_time_none_returns_unknown():
    assert events._relative_time(None) == "unknown"


def test_relative_time_garbage_returns_unknown():
    assert events._relative_time("not-a-timestamp") == "unknown"


def test_relative_time_recent_returns_just_now():
    ts = datetime.now(timezone.utc) - timedelta(seconds=5)
    assert events._relative_time(ts) == "just now"


def test_relative_time_future_clamps_to_just_now():
    ts = datetime.now(timezone.utc) + timedelta(minutes=5)
    assert events._relative_time(ts) == "just now"


def test_relative_time_singular_minute():
    ts = datetime.now(timezone.utc) - timedelta(minutes=1, seconds=10)
    assert events._relative_time(ts) == "1 minute ago"


def test_relative_time_plural_minutes():
    ts = datetime.now(timezone.utc) - timedelta(minutes=2, seconds=10)
    assert events._relative_time(ts) == "2 minutes ago"


def test_relative_time_hours():
    ts = datetime.now(timezone.utc) - timedelta(hours=3, minutes=5)
    assert events._relative_time(ts) == "3 hours ago"


def test_relative_time_days():
    ts = datetime.now(timezone.utc) - timedelta(days=2, hours=1)
    assert events._relative_time(ts) == "2 days ago"
