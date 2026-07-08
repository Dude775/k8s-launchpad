"""
Application factory structural tests.

Behavior under test:
- create_app() is importable and callable, registers health_bp, wires metrics
- Config has no MONGO_* attrs (D-02 — Mongo deferred)
- Config.DEBUG defaults to False unless FLASK_DEBUG env is truthy
- _env_flag truthy/falsy parsing
- extensions.metrics is a PrometheusMetrics instance
"""


def test_create_app_is_importable():
    """create_app must be importable from the app package (import-only, no call)."""
    from app import create_app

    assert callable(create_app)


def test_create_app_returns_flask_app():
    """create_app() returns a configured Flask app with health_bp registered."""
    from flask import Flask

    from app import create_app

    app = create_app({"TESTING": True})

    assert isinstance(app, Flask)
    assert app.config["TESTING"] is True
    assert "health" in app.blueprints


def test_config_has_no_mongo_attrs():
    """Config must NOT expose MONGO_URI/MONGO_DBNAME — deferred to Phase 7/9 (D-02)."""
    from app.config import Config

    assert not hasattr(Config, "MONGO_URI")
    assert not hasattr(Config, "MONGO_DBNAME")


def test_config_debug_defaults_false(monkeypatch):
    """DEBUG must be falsy when FLASK_DEBUG is absent from the environment.

    Tests the parsing helper directly (no module reload, no global env
    mutation): reloading config re-runs load_dotenv(), which would re-read
    FLASK_DEBUG from a developer's local .env and make this test flaky.
    monkeypatch.delenv auto-restores the variable after the test.
    """
    from app.config import _env_flag

    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    assert _env_flag("FLASK_DEBUG") is False


def test_env_flag_zero_and_false_disable_debug(monkeypatch):
    """FLASK_DEBUG=0 / false / no / off must parse as False."""
    from app.config import _env_flag

    for value in ("0", "false", "False", "no", "off", ""):
        monkeypatch.setenv("FLASK_DEBUG", value)
        assert _env_flag("FLASK_DEBUG") is False, f"value={value!r}"


def test_env_flag_truthy_values_enable_debug(monkeypatch):
    """FLASK_DEBUG=1 / true / yes / on must parse as True."""
    from app.config import _env_flag

    for value in ("1", "true", "TRUE", "yes", "on", " 1 "):
        monkeypatch.setenv("FLASK_DEBUG", value)
        assert _env_flag("FLASK_DEBUG") is True, f"value={value!r}"


def test_extensions_metrics_singleton():
    """extensions.metrics must be a PrometheusMetrics instance."""
    from prometheus_flask_exporter import PrometheusMetrics

    from app.extensions import metrics

    assert isinstance(metrics, PrometheusMetrics)
