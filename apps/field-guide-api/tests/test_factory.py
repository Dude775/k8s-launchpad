"""
Application factory structural tests.
Task 1 RED phase: these tests import from modules that do not exist yet.
They MUST fail before Task 1 implementation is created.

Behavior under test:
- create_app() is importable from the app package before route modules exist
- Config exposes MONGO_URI derived from environment (never hardcoded)
- Config.DEBUG defaults to False unless FLASK_DEBUG env is truthy
- extensions module exposes PyMongo() and PrometheusMetrics singletons
"""

import os
import pytest


def test_create_app_is_importable():
    """create_app must be importable from the app package (import-only, no call)."""
    from app import create_app

    assert callable(create_app)


def test_config_has_mongo_uri():
    """Config class must expose a MONGO_URI attribute derived from env."""
    from app.config import Config

    assert hasattr(Config, "MONGO_URI")
    assert Config.MONGO_URI.startswith("mongodb://")


def test_config_debug_defaults_false():
    """DEBUG must be falsy when FLASK_DEBUG is absent from the environment."""
    os.environ.pop("FLASK_DEBUG", None)
    # Re-import after env change so module-level eval picks it up
    import importlib
    import app.config as cfg_module

    importlib.reload(cfg_module)
    from app.config import Config

    assert not Config.DEBUG


def test_extensions_mongo_singleton():
    """extensions.mongo must be a PyMongo() instance (unbound)."""
    from flask_pymongo import PyMongo

    from app.extensions import mongo

    assert isinstance(mongo, PyMongo)


def test_extensions_metrics_singleton():
    """extensions.metrics must be a PrometheusMetrics singleton."""
    from app.extensions import metrics

    assert metrics is not None
