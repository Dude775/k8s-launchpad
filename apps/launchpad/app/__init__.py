"""
Flask application factory.

Usage:
    from app import create_app
    app = create_app()                               # production / gunicorn
    app = create_app({"TESTING": True, ...})         # test overrides

Blueprint imports are deferred INSIDE create_app() so that:
  1. `from app import create_app` succeeds without the route modules on disk.
  2. Each test can create an isolated app instance without global state leaking.

No app.k8s call here — get_k8s_clients() is lazy and only ever invoked
per-request by a future diagnostics route (D-05).
"""

from flask import Flask

from app.config import Config
from app.extensions import metrics, mongo


def create_app(config_overrides: dict | None = None) -> Flask:
    """Create and configure the Flask application.

    Args:
        config_overrides: Optional dict of config values that override the
            environment-based Config class. Typically used in tests to supply
            TESTING=True.

    Returns:
        A fully configured Flask app instance with extensions initialized
        and all blueprints registered.
    """
    app = Flask(__name__)

    # 1. Load base config from environment (via Config class).
    app.config.from_object(Config)

    # 2. Apply caller-supplied overrides (e.g. TESTING=True from tests).
    if config_overrides:
        app.config.update(config_overrides)

    # 3. Initialize extensions against this app instance.
    #    Server selection is bounded so /health fails fast (503 in ~2s) instead
    #    of blocking the sole gunicorn worker for PyMongo's default 30s when
    #    MongoDB is unreachable (readiness must fail by 503, not probe timeout).
    app.config.setdefault("MONGO_SERVER_SELECTION_TIMEOUT_MS", 2000)
    mongo.init_app(
        app,
        serverSelectionTimeoutMS=app.config["MONGO_SERVER_SELECTION_TIMEOUT_MS"],
    )
    metrics.init_app(app)  # also auto-registers the /metrics endpoint

    # 4. Register blueprints — DEFERRED import so this module is importable
    #    before the route files exist.
    from app.routes.health import health_bp  # noqa: PLC0415
    from app.routes.pages import pages_bp  # noqa: PLC0415
    from app.routes.partials import partials_bp  # noqa: PLC0415
    from app.routes.status import status_bp  # noqa: PLC0415

    app.register_blueprint(health_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(partials_bp)
    app.register_blueprint(status_bp)

    return app
