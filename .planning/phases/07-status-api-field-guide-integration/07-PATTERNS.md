# Phase 7: Status API + Field-Guide Integration - Pattern Map

**Mapped:** 2026-07-11
**Files analyzed:** 12 (5 new/modified app files, 1 modified template, 2 requirements files, 3-4 test files)
**Analogs found:** 12 / 12

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/launchpad/app/extensions.py` | config/utility (extension singleton) | CRUD (Mongo binding) | `apps/field-guide-api/app/extensions.py` | exact |
| `apps/launchpad/app/__init__.py` | config (app factory) | request-response | `apps/field-guide-api/app/__init__.py` | exact |
| `apps/launchpad/app/config.py` | config | — | `apps/field-guide-api/app/config.py` | exact |
| `apps/launchpad/app/routes/health.py` (MODIFIED) | route/controller | request-response | `apps/field-guide-api/app/routes/health.py` | exact |
| `apps/launchpad/app/status.py` (NEW) | utility/service (helper, no Blueprint) | request-response + event-driven (aggregation) | `apps/launchpad/app/k8s.py` (bare-helper shape) + `apps/field-guide-api/app/routes/health.py` (ping pattern) | role-match (synthesized — no direct analog exists) |
| `apps/launchpad/app/routes/status.py` (NEW) | route/controller | request-response | `apps/field-guide-api/app/routes/health.py` (thin Blueprint, own-DB check) | exact |
| `apps/launchpad/app/routes/partials.py` (MODIFIED) | route/controller | request-response (HX-Request branch) | itself (Phase 6 stub) — for the branch shape, `06-RESEARCH.md` Pattern 3 (no in-repo code yet) | role-match |
| `apps/launchpad/app/routes/__init__.py` (MODIFIED) | route (barrel export) | — | `apps/field-guide-api/app/routes/__init__.py` | exact |
| `apps/launchpad/app/templates/partials/status_cards.html` (MODIFIED) | component (Jinja template) | transform | itself (Phase 6 stub) + `apps/launchpad/app/templates/base.html` (extends pattern) | role-match |
| `apps/launchpad/requirements.txt` (MODIFIED) | config | — | `apps/field-guide-api/requirements.txt` | exact (copy pins verbatim) |
| `apps/launchpad/tests/test_health.py` (MODIFIED) | test | request-response | `apps/field-guide-api/tests/test_health.py` | exact |
| `apps/launchpad/tests/test_status.py` (NEW) | test | request-response | `apps/field-guide-api/tests/test_entries.py` (Blueprint JSON route tests) + `apps/field-guide-api/tests/conftest.py` (`mongo_down` fixture) | role-match |
| `apps/launchpad/tests/conftest.py` (MODIFIED) | test fixture | — | `apps/field-guide-api/tests/conftest.py` | exact |

## Pattern Assignments

### `apps/launchpad/app/extensions.py` (config, singleton binding)

**Analog:** `apps/field-guide-api/app/extensions.py` (full file, 19 lines — read in one pass)

**Full existing pattern** (lines 1-19):
```python
"""
Extension singletons.

Both objects are created unbound here; they are bound to a concrete Flask app
instance inside create_app() via .init_app(). This pattern supports the
application factory and makes testing with isolated app instances straightforward.
"""

from flask_pymongo import PyMongo
from prometheus_flask_exporter import PrometheusMetrics

# Unbound PyMongo singleton — bound to app in create_app() via mongo.init_app(app).
mongo: PyMongo = PyMongo()

# Unbound PrometheusMetrics singleton — bound in create_app() via metrics.init_app(app).
# Using .for_app_factory() defers /metrics route registration to init_app time,
# which is required when using the application factory pattern.
metrics: PrometheusMetrics = PrometheusMetrics.for_app_factory()
```

**Current launchpad state** (`apps/launchpad/app/extensions.py`, lines 1-16 — to be modified):
```python
from prometheus_flask_exporter import PrometheusMetrics

metrics: PrometheusMetrics = PrometheusMetrics.for_app_factory()
```

**Action:** Add the `mongo: PyMongo = PyMongo()` singleton line + `from flask_pymongo import PyMongo` import above the existing `metrics` singleton, using field-guide-api's exact comment style. Remove the Phase-5 docstring line "No PyMongo singleton in Phase 5 — MongoDB wiring is deferred to Phase 7/9 (D-02)" since that is now stale.

---

### `apps/launchpad/app/__init__.py` (app factory)

**Analog:** `apps/field-guide-api/app/__init__.py` (full file, 62 lines)

**Mongo-binding pattern to copy verbatim** (field-guide-api lines 42-51):
```python
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
```

**Blueprint registration pattern** (field-guide-api lines 53-59, deferred imports):
```python
    from app.routes.entries import entries_bp  # noqa: PLC0415
    from app.routes.health import health_bp  # noqa: PLC0415

    app.register_blueprint(entries_bp)
    app.register_blueprint(health_bp)
```

**Current launchpad state** (`apps/launchpad/app/__init__.py`, lines 18-58 — full file read):
```python
from flask import Flask

from app.config import Config
from app.extensions import metrics


def create_app(config_overrides: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)

    # 3. Initialize extensions against this app instance.
    metrics.init_app(app)  # also auto-registers the /metrics endpoint

    # 4. Register blueprints — DEFERRED import so this module is importable
    #    before the route files exist.
    from app.routes.health import health_bp  # noqa: PLC0415
    from app.routes.pages import pages_bp  # noqa: PLC0415
    from app.routes.partials import partials_bp  # noqa: PLC0415

    app.register_blueprint(health_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(partials_bp)

    return app
```

**Action:** Insert the `MONGO_SERVER_SELECTION_TIMEOUT_MS`/`mongo.init_app()` block (copied verbatim from field-guide-api, using launchpad's own `MONGO_URI`) immediately before `metrics.init_app(app)`. Update `from app.extensions import metrics` to `from app.extensions import metrics, mongo`. Add `from app.routes.status import status_bp` to the deferred-import block and `app.register_blueprint(status_bp)`. Remove the now-stale module docstring lines referencing "No mongo.init_app() call here."

---

### `apps/launchpad/app/config.py` (config)

**Analog:** `apps/field-guide-api/app/config.py` (full file, 41 lines)

**MONGO_URI env-var pattern** (field-guide-api lines 27-33):
```python
class Config:
    # MongoDB connection string — must be env-supplied; local default for dev only.
    # Never embed a real URI or password here.
    MONGO_URI: str = os.environ.get(
        "MONGO_URI", "mongodb://localhost:27017/fieldguide"
    )
    MONGO_DBNAME: str = os.environ.get("MONGO_DBNAME", "fieldguide")
```

**Action:** Add to launchpad's `Config` class (current file has only `DEBUG`/`TESTING`):
```python
MONGO_URI: str = os.environ.get("MONGO_URI", "mongodb://localhost:27017/launchpad")
FIELD_GUIDE_BASE_URL: str = os.environ.get("FIELD_GUIDE_BASE_URL", "http://field-guide-api")
APP_VERSION: str = os.environ.get("APP_VERSION", "dev")
```
Note launchpad uses db name `launchpad` (its own DB), not `fieldguide` — do not copy field-guide-api's DB name literal, only the pattern shape. `apps/launchpad/.env.example` (currently `FLASK_DEBUG=` only, 5 lines) must gain `MONGO_URI=`, `FIELD_GUIDE_BASE_URL=`, `APP_VERSION=` keys mirroring field-guide-api's `.env.example` comment style (which documents `MONGO_URI=mongodb://localhost:27017/fieldguide` with a "supplied via a Kubernetes Secret in-cluster" comment).

**Also update `test_factory.py`'s stale assertion** — `apps/launchpad/tests/test_factory.py` lines 33-38 currently assert `Config` has NO `MONGO_URI`/`MONGO_DBNAME` attrs ("D-02 — Mongo deferred"); this test must be rewritten/removed since Phase 7 adds `MONGO_URI` (launchpad has no `MONGO_DBNAME` key at all — Flask-PyMongo derives the DB name from the URI path).

---

### `apps/launchpad/app/routes/health.py` (route, request-response) — MODIFIED IN PLACE

**Analog:** `apps/field-guide-api/app/routes/health.py` (full file, 34 lines — the direct 1:1 source)

**Full pattern to adapt verbatim** (lines 19-33):
```python
from flask import Blueprint, jsonify

from app.extensions import mongo

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health():
    """Return MongoDB readiness status."""
    try:
        mongo.cx.admin.command("ping")
        return jsonify({"status": "ok", "mongo": "up"}), 200
    except Exception:
        return jsonify({"status": "unavailable", "mongo": "down"}), 503
```

**Current launchpad stub** (`apps/launchpad/app/routes/health.py`, full file, 21 lines):
```python
from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health():
    """Return a plain liveness signal."""
    return jsonify({"status": "ok"}), 200
```

**Action:** Replace the stub body with field-guide-api's ping/try-except pattern verbatim, importing `mongo` from `app.extensions`. Update the module docstring (currently references "D-04, no Mongo check") to match field-guide-api's docstring style. **Critical constraint (Pitfall 1, RESEARCH.md):** this file must NEVER import `requests` or reference `FIELD_GUIDE_BASE_URL` — it imports ONLY `app.extensions.mongo`.

---

### `apps/launchpad/app/status.py` (NEW — internal helper, no Blueprint)

**No direct analog exists in the codebase** — this is a synthesized pattern per RESEARCH.md Pattern 2, combining:
1. The bare-helper-module shape of `apps/launchpad/app/k8s.py` (single exported function, no Blueprint, lazy per-call invocation, never raises past its boundary)
2. The Mongo ping try/except shape from `apps/field-guide-api/app/routes/health.py`

**Bare-helper module shape to mirror** (`apps/launchpad/app/k8s.py`, lines 24-49):
```python
def get_k8s_clients():
    """Return (CoreV1Api, AppsV1Api) if a cluster is reachable, else (None, None).
    ...
    No caching (D-06) — a plain function is enough for the Phase 5 skeleton.
    """
    try:
        config.load_incluster_config()
    except ConfigException:
        pass
    else:
        return client.CoreV1Api(), client.AppsV1Api()
    ...
    return None, None
```
This establishes the project's precedent: a bare-function helper module (not a class, not a Blueprint) that degrades to a safe sentinel value rather than raising.

**Full target implementation** (from RESEARCH.md Pattern 2, ready to use as-is):
```python
import os

import requests

from app.extensions import mongo

FIELD_GUIDE_TIMEOUT_SECONDS = 2


def get_platform_status() -> dict:
    """Aggregate platform status for /api/status and the status-cards fragment.

    Every sub-check is independently exception-isolated — this function
    NEVER raises. Contrast with /health (app/routes/health.py), which checks
    ONLY launchpad's own MongoDB and is the Kubernetes readinessProbe target;
    this function additionally reaches across the cluster network to
    field-guide-api and must degrade gracefully when it is unreachable.
    """
    mongo_status = "down"
    try:
        mongo.cx.admin.command("ping")
        mongo_status = "up"
    except Exception:
        pass

    field_guide_reachable = False
    base_url = os.environ.get("FIELD_GUIDE_BASE_URL", "http://field-guide-api")
    try:
        resp = requests.get(f"{base_url}/health", timeout=FIELD_GUIDE_TIMEOUT_SECONDS)
        field_guide_reachable = resp.status_code == 200
    except requests.exceptions.RequestException:
        field_guide_reachable = False

    return {
        "api_health": "ok" if mongo_status == "up" else "degraded",
        "mongo_status": mongo_status,
        "app_version": os.environ.get("APP_VERSION", "dev"),
        "service_count": 0,  # Phase 9 wires a real mongo.db.services.count_documents({})
        "field_guide_reachable": field_guide_reachable,
    }
```
**Note:** prefer reading `app_version`/`FIELD_GUIDE_BASE_URL` via `flask.current_app.config` instead of `os.environ.get` directly if the planner wants config-override testability consistent with `Config` class usage elsewhere — RESEARCH.md's example uses `os.environ.get` directly; either is acceptable but `current_app.config["FIELD_GUIDE_BASE_URL"]` is more consistent with this project's `Config`-class-as-source-of-truth pattern seen in `config.py`. Flag this as a planner discretion point.

---

### `apps/launchpad/app/routes/status.py` (NEW — Blueprint route)

**Analog:** `apps/field-guide-api/app/routes/health.py` (thin-Blueprint idiom) — structurally closest existing route (single GET, own-DB-derived JSON, no request body)

**Thin-Blueprint shape to mirror** (field-guide-api lines 19-33, same import/Blueprint/route-decorator structure):
```python
from flask import Blueprint, jsonify

from app.extensions import mongo

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health():
    ...
```

**Full target implementation** (from RESEARCH.md Pattern 3):
```python
from flask import Blueprint, jsonify

from app.status import get_platform_status

status_bp = Blueprint("status", __name__)


@status_bp.route("/api/status", methods=["GET"])
def api_status():
    """Return real platform status as JSON (STAT-01, STAT-02).

    Shares get_platform_status() with the /partials/status-cards fragment —
    the JSON payload and the dashboard's rendered cards can never diverge.
    """
    return jsonify(get_platform_status()), 200
```

**Barrel export update — analog:** `apps/field-guide-api/app/routes/__init__.py` (full file, 7 lines):
```python
from app.routes.entries import entries_bp
from app.routes.health import health_bp

__all__ = ["entries_bp", "health_bp"]
```
**Action for `apps/launchpad/app/routes/__init__.py`** (current file, 8 lines):
```python
from app.routes.health import health_bp
from app.routes.pages import pages_bp
from app.routes.partials import partials_bp

__all__ = ["health_bp", "pages_bp", "partials_bp"]
```
Add `from app.routes.status import status_bp` and `"status_bp"` to `__all__`, matching field-guide-api's alphabetical-ish grouping.

---

### `apps/launchpad/app/routes/partials.py` (MODIFIED IN PLACE — HX-Request branch)

**Analog:** itself — the Phase 6 stub already establishes the route path/Blueprint/template-name contract; no in-repo file yet demonstrates an `HX-Request` conditional branch (06-RESEARCH.md Pattern 3 is referenced but not yet materialized as code in this repo).

**Current full file** (`apps/launchpad/app/routes/partials.py`, 35 lines):
```python
from flask import Blueprint, render_template

partials_bp = Blueprint("partials", __name__, url_prefix="/partials")


@partials_bp.route("/status-cards", methods=["GET"])
def status_cards():
    """Phase 6: always-degraded stub. Phase 7 replaces the stub data with
    real /api/status internals — route path, template name, and the
    htmx hx-get target in index.html all stay the same."""
    return render_template(
        "partials/status_cards.html",
        status="unknown",
        cards=[],
    )
```

**Target implementation** (RESEARCH.md Pattern 5, HX-Request-aware):
```python
from flask import Blueprint, render_template, request

from app.status import get_platform_status

partials_bp = Blueprint("partials", __name__, url_prefix="/partials")


@partials_bp.route("/status-cards", methods=["GET"])
def status_cards():
    status = get_platform_status()
    if request.headers.get("HX-Request") == "true":
        return render_template("partials/status_cards.html", status=status)
    return render_template("status_full_page.html", status=status)
```

**Critical constraint:** this is a *documented, deliberate* evolution of Phase 6's own docstring warning ("must NEVER grow an HX-Request-conditional branch... add a NEW route instead"). Phase 7's own success criterion 4 explicitly requires the branch — update the module docstring to reflect the new contract rather than silently contradicting the old comment.

**New template needed:** `apps/launchpad/app/templates/status_full_page.html` — mirror `base.html`'s `{% extends "base.html" %}` + `{% block content %}` pattern (see `base.html` excerpt below) and `{% include "partials/status_cards.html" %}` inside the content block, per RESEARCH.md Pattern 5.

**`base.html` extends contract** (`apps/launchpad/app/templates/base.html`, lines 1-11, 29-31):
```html
<!doctype html>
<html lang="en">
<head>
  ...
  <title>{% block title %}Dashboard{% endblock %} - k8s-launchpad</title>
  ...
</head>
<body>
  <div class="layout">
    ...
    <div class="main">
      <header class="topbar">...</header>
      <main>{% block content %}{% endblock %}</main>
    </div>
  </div>
</body>
</html>
```
Existing page templates (`index.html`, `catalog.html`, etc.) already follow `{% extends "base.html" %}` + `{% block content %}` — apply the same shape for `status_full_page.html`.

---

### `apps/launchpad/app/templates/partials/status_cards.html` (MODIFIED — real cards)

**Analog:** itself (Phase 6 stub, full file, 9 lines):
```html
{% if status == "unknown" %}
  <article aria-busy="false" class="status-card status-card--unknown">
    <header>Status unavailable</header>
    <p>The platform status API is not connected yet. This will populate automatically once available.</p>
  </article>
{% else %}
  {# Phase 7 fills in real per-metric cards here #}
{% endif %}
```

**Action:** Replace the `{% if status == "unknown" %}` sentinel branch (must be fully replaced, not extended — `status` is now always a populated dict per RESEARCH.md Pattern 4) with per-field cards, e.g.:
```html
<article class="status-card status-card--{{ 'ok' if status.mongo_status == 'up' else 'degraded' }}">
  <header>MongoDB</header>
  <p>{{ status.mongo_status }}</p>
</article>
<article class="status-card status-card--{{ 'ok' if status.field_guide_reachable else 'degraded' }}">
  <header>Field Guide API</header>
  <p>{{ 'reachable' if status.field_guide_reachable else 'unreachable' }}</p>
</article>
<article class="status-card">
  <header>Version</header>
  <p>{{ status.app_version }}</p>
</article>
<article class="status-card">
  <header>Registered Services</header>
  <p>{{ status.service_count }}</p>
</article>
```
Keep the `status-card` CSS class naming convention from the Phase 6 stub (`status-card status-card--<modifier>`).

---

## Shared Patterns

### App-factory extension wiring (Mongo + Metrics)
**Source:** `apps/field-guide-api/app/__init__.py` lines 42-51 + `apps/field-guide-api/app/extensions.py` (full file)
**Apply to:** `apps/launchpad/app/__init__.py`, `apps/launchpad/app/extensions.py`
```python
app.config.setdefault("MONGO_SERVER_SELECTION_TIMEOUT_MS", 2000)
mongo.init_app(
    app,
    serverSelectionTimeoutMS=app.config["MONGO_SERVER_SELECTION_TIMEOUT_MS"],
)
metrics.init_app(app)  # also auto-registers the /metrics endpoint
```
This is the single most load-bearing shared pattern this phase: the exact 2000ms `serverSelectionTimeoutMS` override, copied verbatim from the sibling app, prevents `/health` from ever blocking the sole gunicorn worker for PyMongo's 30s default.

### Bare `except Exception` for readiness/degradation checks
**Source:** `apps/field-guide-api/app/routes/health.py` lines 29-33
**Apply to:** `apps/launchpad/app/routes/health.py`, `apps/launchpad/app/status.py`
```python
try:
    mongo.cx.admin.command("ping")
    ...
except Exception:
    ...
```
Project precedent: broad `except Exception` (not a narrow PyMongo exception subclass) is intentional — a readinessProbe/status-aggregation target must never itself raise a 500, regardless of failure cause (network, auth, timeout, or unexpected driver exception).

### Deferred Blueprint imports inside `create_app()`
**Source:** `apps/field-guide-api/app/__init__.py` lines 53-59 (`# noqa: PLC0415` deferred imports), mirrored already in `apps/launchpad/app/__init__.py` lines 50-52
**Apply to:** `apps/launchpad/app/__init__.py` (add `from app.routes.status import status_bp  # noqa: PLC0415`)
Keeps `app/__init__.py` importable before every route module exists on disk, and keeps blueprint registration test-isolated per app instance.

### Test fixture: mocked Mongo ping via monkeypatch
**Source:** `apps/field-guide-api/tests/conftest.py` lines 58-79 (`mongo_down` fixture)
**Apply to:** `apps/launchpad/tests/conftest.py` (new `mongo_down` fixture), `apps/launchpad/tests/test_health.py`, `apps/launchpad/tests/test_status.py`
```python
@pytest.fixture
def mongo_down(client, monkeypatch):
    """Test client that simulates a MongoDB outage."""
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
```
**Important divergence for launchpad:** field-guide-api's `app` fixture (conftest.py lines 19-49) uses **mongomock** (`mongomock.MongoClient()`) patched onto `mongo.cx`/`mongo.db`, not a hand-rolled fake, for the general `app`/`client` fixtures — only the narrow `mongo_down` fixture uses a hand-rolled fake class. **field-guide-api's `requirements-dev.txt` already pins `mongomock==4.3.0`** — this directly resolves RESEARCH.md's Open Question 1: the established in-repo precedent is mongomock for the base fixture + a lightweight hand-rolled fake for the down/failure branch. Launchpad's `requirements-dev.txt` should add `mongomock==4.3.0` to match, and `apps/launchpad/tests/conftest.py`'s `app` fixture should follow field-guide-api's exact mongomock-injection shape (lines 19-49 of `apps/field-guide-api/tests/conftest.py`).

### Test fixture: mocked `requests.get` (already scaffolded)
**Source:** `apps/launchpad/tests/conftest.py` lines 56-67 (`mock_requests_get` fixture placeholder, already exists, built specifically for this phase)
```python
@pytest.fixture
def mock_requests_get(monkeypatch):
    """Placeholder pattern for mocking `requests.get` ahead of Phase 7's
    field-guide-api reachability check (STAT-02)."""
    import requests

    fake_response = MagicMock(status_code=200, json=lambda: {})
    monkeypatch.setattr(requests, "get", lambda *a, **kw: fake_response)
    return fake_response
```
**Apply to:** `apps/launchpad/tests/test_status.py` (new). This fixture already exists and covers the success path (`status_code=200`); a sibling fixture or inline `monkeypatch.setattr(requests, "get", _raise)` is needed for the failure/unreachable branch, per RESEARCH.md's mocking example (lines 663-705 of 07-RESEARCH.md) — reproduced there as `test_status_field_guide_unreachable_degrades_gracefully`.

### Blueprint barrel-export re-exports
**Source:** `apps/field-guide-api/app/routes/__init__.py` (full file)
**Apply to:** `apps/launchpad/app/routes/__init__.py`
```python
from app.routes.entries import entries_bp
from app.routes.health import health_bp

__all__ = ["entries_bp", "health_bp"]
```

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `apps/launchpad/app/status.py` | utility (aggregation helper) | request-response + event-driven | No existing file in either app combines an own-DB check with a cross-service HTTP call into a single degrade-gracefully dict; synthesized from `app/k8s.py`'s bare-helper shape + `health.py`'s ping/try-except shape (see Pattern Assignments above; RESEARCH.md Pattern 2 supplies the exact target implementation, so this is a low-risk synthesis, not a blind guess) |
| `apps/launchpad/app/templates/status_full_page.html` | component (template) | transform | No existing "full page wrapping a partial via `{% include %}`" template exists yet in either app; `base.html`'s `{% extends %}`/`{% block content %}` contract (read above) is the closest structural analog to build from |

## Metadata

**Analog search scope:** `apps/launchpad/app/`, `apps/launchpad/tests/`, `apps/field-guide-api/app/`, `apps/field-guide-api/tests/`, `apps/launchpad/app/templates/`
**Files scanned:** 27 (14 `.py` app files, 6 `.py` test files, 6 `.html` templates, 2 `requirements*.txt` pairs read in full)
**Pattern extraction date:** 2026-07-11
