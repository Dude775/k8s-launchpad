"""
get_platform_status() + GET /api/status tests (STAT-01, STAT-02).

Covers every branch of the aggregation helper: own-Mongo up/down,
field-guide-api reachable/unreachable, and the metrics-registry read
succeeding/failing — none of these may ever raise past get_platform_status(),
and GET /api/status must always return 200 JSON regardless of downstream
state.
"""

import pymongo.errors
import pytest

from app.status import get_platform_status


def test_status_mongo_up_field_guide_reachable(app, mock_requests_get):
    """mongo up + requests.get 200 -> mongo_status up, api_health ok,
    field_guide_reachable True."""
    with app.app_context():
        result = get_platform_status()

    assert result["mongo_status"] == "up"
    assert result["api_health"] == "ok"
    assert result["field_guide_reachable"] is True


def test_status_field_guide_unreachable_degrades_gracefully(app, mock_requests_get_unreachable):
    """mongo up + requests.get raising ConnectionError -> field_guide_reachable
    False, never raises."""
    with app.app_context():
        result = get_platform_status()

    assert result["field_guide_reachable"] is False
    assert result["mongo_status"] == "up"


def test_status_mongo_down_yields_degraded(app, monkeypatch, mock_requests_get):
    """mongo ping raising -> mongo_status down, api_health degraded."""
    import app.status as status_module

    class _FakeCx:
        class admin:
            @staticmethod
            def command(*args, **kwargs):
                raise pymongo.errors.ConnectionFailure("MongoDB unreachable")

    class _FakeMongo:
        cx = _FakeCx()
        db = None

    monkeypatch.setattr(status_module, "mongo", _FakeMongo())

    with app.app_context():
        result = get_platform_status()

    assert result["mongo_status"] == "down"
    assert result["api_health"] == "degraded"


def test_status_returns_exactly_six_keys(app, mock_requests_get):
    with app.app_context():
        result = get_platform_status()

    assert set(result.keys()) == {
        "api_health",
        "mongo_status",
        "app_version",
        "service_count",
        "field_guide_reachable",
        "metrics_preview",
    }


def test_status_metrics_preview_increments_after_request(app, mock_requests_get):
    """metrics_preview is a dict with an int http_requests_total key; after a
    request is recorded against the flask_http_request counter backing
    /metrics, the summed value strictly increases.

    Increments the counter directly (rather than via a fresh test-client
    request) because prometheus-flask-exporter's export_defaults() guards
    against re-registering its default metrics on the shared global
    REGISTRY (ValueError on duplicate registration) — once one app in this
    test process has registered them, later create_app() calls in other
    tests' `app` fixtures silently skip re-wiring the before/after-request
    instrumentation hooks for their own app instance. Driving the counter
    directly exercises get_platform_status()'s read/summation logic without
    depending on that per-process instrumentation ordering.
    """
    import prometheus_client

    with app.app_context():
        before = get_platform_status()["metrics_preview"]["http_requests_total"]

    counter = None
    for collector in list(prometheus_client.REGISTRY._collector_to_names):
        if getattr(collector, "_name", None) == "flask_http_request":
            counter = collector
            break
    assert counter is not None, "flask_http_request counter not registered"

    counter.labels(method="GET", status="200").inc()

    with app.app_context():
        after = get_platform_status()["metrics_preview"]["http_requests_total"]

    assert isinstance(after, int)
    assert after >= before + 1


def test_status_metrics_registry_failure_falls_back_to_zero(app, monkeypatch, mock_requests_get):
    """If REGISTRY.collect() raises, metrics_preview falls back to
    {"http_requests_total": 0} and get_platform_status() does not raise."""
    import app.status as status_module

    def _raise_collect(*args, **kwargs):
        raise RuntimeError("registry read failed")

    monkeypatch.setattr(status_module.REGISTRY, "collect", _raise_collect)

    with app.app_context():
        result = get_platform_status()

    assert result["metrics_preview"] == {"http_requests_total": 0}


def test_api_status_returns_200_with_all_six_fields_when_unreachable(client, mock_requests_get_unreachable):
    """GET /api/status returns 200 with a JSON body containing all six fields
    regardless of downstream state (never 500)."""
    resp = client.get("/api/status")

    assert resp.status_code == 200
    body = resp.get_json()
    assert set(body.keys()) == {
        "api_health",
        "mongo_status",
        "app_version",
        "service_count",
        "field_guide_reachable",
        "metrics_preview",
    }
    assert body["field_guide_reachable"] is False


def test_status_no_requests_get_call_missing_timeout():
    """Grep gate companion: every requests.get call in status.py passes a
    timeout= keyword (ignores comment lines)."""
    import inspect

    import app.status as status_module

    source = inspect.getsource(status_module)
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "requests.get(" in stripped:
            assert "timeout=" in stripped
