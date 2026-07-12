# Phase 9: Service Catalog + Events / MongoDB CRUD - Pattern Map

**Mapped:** 2026-07-12
**Files analyzed:** 22 (11 new, 5 modified, 4 new chart manifests, 2 modified chart files)
**Analogs found:** 22 / 22

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `apps/launchpad/app/catalog.py` | service (never-raise repo helper) | CRUD | `apps/launchpad/app/status.py` (shape) + `apps/launchpad/app/cluster_state.py` (module-attribute import discipline) | role-match |
| `apps/launchpad/app/events.py` | service (never-raise repo helper) | CRUD + event-driven | `apps/launchpad/app/status.py` | role-match |
| `apps/launchpad/app/forms.py` | model (WTForms validation schema) | request-response | none in-repo — RESEARCH.md Pattern 1 is authoritative | no analog |
| `apps/launchpad/app/extensions.py` | config (extension singleton) | — | itself, extend in place | exact |
| `apps/launchpad/app/__init__.py` | config (app factory) | — | itself, extend in place | exact |
| `apps/launchpad/app/config.py` | config | — | itself, extend in place | exact |
| `apps/launchpad/app/routes/pages.py` | route/controller | request-response | itself, extend in place (stub routes already exist) | exact |
| `apps/launchpad/app/routes/partials.py` | route/controller | request-response (htmx fragment/full-page) | itself, extend in place (`status_cards`/`cluster_state` routes) | exact |
| `apps/launchpad/app/templates/catalog.html` | component (Jinja2 template) | request-response | `apps/launchpad/app/templates/cluster_state_full_page.html` (table) + `diagnostics.html` (empty-state pattern) | role-match |
| `apps/launchpad/app/templates/onboard_form.html` | component (form template) | request-response | none in-repo — RESEARCH.md Pattern 1 example is authoritative; layout follows UI-SPEC Form Contract | no analog |
| `apps/launchpad/app/templates/detail.html` | component | request-response | `apps/launchpad/app/templates/cluster_state_full_page.html` (section layout) | partial-match |
| `apps/launchpad/app/templates/confirm_delete.html` | component | request-response | `apps/launchpad/app/templates/catalog.html` stub (extends base.html, minimal content) | partial-match |
| `apps/launchpad/app/templates/feed.html` | component | request-response + polling | `apps/launchpad/app/templates/diagnostics.html` (htmx polling shell) | exact |
| `apps/launchpad/app/templates/partials/event_row.html` | component (shared partial) | request-response | `apps/launchpad/app/templates/partials/status_cards.html` (bare fragment, no wrapper) | role-match |
| `apps/launchpad/app/templates/partials/feed_events.html` | component (fragment) | request-response | `apps/launchpad/app/templates/partials/cluster_state.html` (fragment with conditional branches) | exact |
| `apps/launchpad/app/templates/feed_full_page.html` | component (full-page wrapper) | request-response | `apps/launchpad/app/templates/cluster_state_full_page.html` | exact |
| `apps/launchpad/tests/conftest.py` | test fixture | — | itself, extend in place | exact |
| `apps/launchpad/tests/test_catalog.py` | test | CRUD | `apps/launchpad/tests/test_status.py` (never-raise helper test shape) | role-match |
| `apps/launchpad/tests/test_events.py` | test | event-driven | `apps/launchpad/tests/test_status.py` | role-match |
| `apps/launchpad/tests/test_pages.py` | test | request-response | itself, extend in place | exact |
| `apps/launchpad/tests/test_partials.py` | test | request-response | itself, extend in place | exact |
| `apps/launchpad/requirements.txt` | config | — | itself, extend in place | exact |
| `charts/launchpad/templates/mongodb/deployment.yaml` | migration/manifest | CRUD (infra) | `charts/field-guide-api/templates/mongodb/deployment.yaml` | exact |
| `charts/launchpad/templates/mongodb/pvc.yaml` | migration/manifest | file-I/O (infra) | `charts/field-guide-api/templates/mongodb/pvc.yaml` | exact |
| `charts/launchpad/templates/mongodb/secret.yaml` | migration/manifest | — | `charts/field-guide-api/templates/mongodb/secret.yaml` | exact |
| `charts/launchpad/templates/mongodb/service.yaml` | migration/manifest | — | `charts/field-guide-api/templates/mongodb/service.yaml` | exact |
| `charts/launchpad/templates/_helpers.tpl` | config (Helm helper) | — | `charts/field-guide-api/templates/_helpers.tpl` (mongodb.fullname / mongodb.selectorLabels helpers) | exact |
| `charts/launchpad/templates/secret.yaml` | config (Helm manifest) | — | itself, extend with SECRET_KEY | exact |
| `charts/launchpad/templates/configmap.yaml` | config (Helm manifest) | — | itself, extend with eventsTtlSeconds | exact |
| `charts/launchpad/templates/deployment.yaml` | config (Helm manifest) | — | itself, extend env with SECRET_KEY/EVENTS_TTL_SECONDS | exact |
| `charts/launchpad/values.yaml` | config | — | `charts/field-guide-api/values.yaml` (mongodb block shape) | exact |

## Pattern Assignments

### `apps/launchpad/app/catalog.py` (service, CRUD)

**Analog:** `apps/launchpad/app/status.py` (never-raise shape) — no CRUD-shaped helper exists yet in this codebase, so this is the closest role-match (bare helper module, no Blueprint, exception-isolated).

**Module docstring / never-raise contract pattern** (`apps/launchpad/app/status.py` lines 1-16):
```python
"""
Platform status aggregation helper.
...
This module is a bare helper (NO Blueprint) — mirrors app/k8s.py's shape: a
single exported function that never raises, degrading to safe sentinel
values on any sub-check failure.
"""

from app.extensions import mongo
```

**Never-raise DB access pattern** (`apps/launchpad/app/status.py` lines 66-72, 82-89):
```python
mongo_status = "down"
try:
    mongo.cx.admin.command("ping")
    mongo_status = "up"
except Exception:
    pass
...
service_count = 0
try:
    service_count = mongo.db.services.count_documents({})
except Exception:
    service_count = 0
```

**Exact insert/unique-index pattern to use for `register_service`/`ensure_indexes`/`deregister_service`:** RESEARCH.md Pattern 4 (already codebase-aligned, no existing analog to copy verbatim since no prior insert_one exists in-repo):
```python
from pymongo.errors import DuplicateKeyError
from app.extensions import mongo

def ensure_indexes() -> None:
    """Idempotent — safe to call on every create_app(). Never raises."""
    try:
        mongo.db.services.create_index("name", unique=True)
    except Exception:
        pass

def register_service(data: dict) -> tuple[bool, str | None]:
    try:
        mongo.db.services.insert_one(data)
        return True, None
    except DuplicateKeyError:
        return False, "This name is already registered — choose another."
```

**Error-message discipline (T-08-06 / T-07-07):** never `str(exception)` in any return value — fixed generic strings only, per `status.py` lines 63-66 docstring ("Exception detail is always discarded").

---

### `apps/launchpad/app/events.py` (service, CRUD + event-driven)

**Analog:** `apps/launchpad/app/status.py` for the never-raise shape; `apps/launchpad/app/cluster_state.py` for the **module-attribute import discipline** (critical — this is the Phase 8 lesson explicitly carried forward).

**Module-attribute import lesson** (`apps/launchpad/app/cluster_state.py` lines 9-18, verbatim):
```python
"""
CRITICAL (plan-check BLOCKER 3): this module imports `app.k8s` as a MODULE
and calls the accessor via that module attribute — it does NOT import the
accessor function by name directly into this namespace. tests/conftest.py's
k8s_disabled and k8s_enabled fixtures monkeypatch app.k8s.get_k8s_clients
directly; a direct-name import would bind the original function into this
module's namespace at import time (during create_app), so the later
monkeypatch would never reach it and the mocked-branch tests would fail
deterministically. This mirrors status.py's `import requests` ->
`requests.get(...)` idiom.
"""

import os
from datetime import datetime, timezone

import urllib3
from kubernetes.client.exceptions import ApiException

from app import k8s   # <-- module import, NOT `from app.k8s import get_k8s_clients`
...
core_v1, apps_v1 = k8s.get_k8s_clients()   # <-- called via module attribute
```

**Apply identically to any Phase 9 module that calls into `events.py` or `catalog.py` from routes** — `apps/launchpad/app/routes/pages.py` and `apps/launchpad/app/routes/partials.py` MUST do `from app import events` / `from app import catalog` then `events.record_event(...)` / `catalog.register_service(...)`, never `from app.events import record_event`. This exact rule is also called out explicitly in RESEARCH.md's "Don't Hand-Roll" / Anti-Patterns section — treat it as load-bearing, not optional style.

**Never-raise event writer** (RESEARCH.md Code Examples, mirrors `status.py` shape exactly):
```python
from datetime import datetime, timezone
from app.extensions import mongo

def record_event(event_type: str, service_name: str | None) -> bool:
    """Write one event document. Never raises — returns False on any failure."""
    try:
        mongo.db.events.insert_one(
            {"type": event_type, "service_name": service_name, "ts": datetime.now(timezone.utc)}
        )
        return True
    except Exception:
        return False
```

**Module-level once-per-process guard pattern** — no direct analog exists in-repo (this is a genuinely new shape), but it follows the same "module-level state, reset hook for tests" discipline as `tests/conftest.py`'s `k8s_disabled`/`k8s_enabled` fixtures that monkeypatch module attributes. Use RESEARCH.md Pattern 3 verbatim (`_platform_started_emitted` module flag + `reset_platform_started_guard_for_tests()` hook called from the `app` fixture in `conftest.py`).

**Age/relative-time helper precedent** — mirror `_pod_age()` in `apps/launchpad/app/cluster_state.py` lines 34-56 for the feed's relative-timestamp rendering (small pure-Python `datetime` diff helper, never-raise, "unknown" fallback):
```python
def _pod_age(creation_timestamp) -> str:
    if creation_timestamp is None:
        return "unknown"
    try:
        delta = datetime.now(timezone.utc) - creation_timestamp
        seconds = int(delta.total_seconds())
        ...
    except Exception:
        return "unknown"
```

---

### `apps/launchpad/app/forms.py` (model, request-response)

**No in-repo analog** — this is the first WTForms usage in the codebase. Use RESEARCH.md Pattern 1 verbatim (already vetted against UI-SPEC's Form Contract: `name`→`StringField`+`Regexp`, `repo_url`→`URLField`+`URL(require_tld=True)`+scheme-restricting validator per Pitfall 5, `owner`→`StringField`+`Length(max=100)`, `description`→`TextAreaField` optional, `environment`→`SelectField` with dev/staging/prod choices, default "dev").

**Convention alignment:** field error copy must match UI-SPEC.md's Copywriting Contract exactly (e.g. `"This field is required."`, `"Use lowercase letters, numbers, and hyphens only (2–40 characters)."`, `"Enter a valid http:// or https:// URL."`, `"Owner is required."`) — these are locked strings, not placeholders.

---

### `apps/launchpad/app/extensions.py` (config, extend in place)

**Analog:** itself — exact unbound-singleton-then-`init_app()` shape already established.

**Current pattern** (`apps/launchpad/app/extensions.py` lines 1-19, full file):
```python
"""
Extension singletons.

Created unbound here; bound to a concrete Flask app instance inside
create_app() via .init_app(). This pattern supports the application factory
and makes testing with isolated app instances straightforward.
"""

from flask_pymongo import PyMongo
from prometheus_flask_exporter import PrometheusMetrics

mongo: PyMongo = PyMongo()
metrics: PrometheusMetrics = PrometheusMetrics.for_app_factory()
```

**Add** (per RESEARCH.md Pattern 2, same shape):
```python
from flask_wtf import CSRFProtect

csrf: CSRFProtect = CSRFProtect()
```

---

### `apps/launchpad/app/__init__.py` (config, extend in place)

**Analog:** itself — the numbered-step app-factory structure (1. load config, 2. overrides, 3. init extensions, 4. deferred blueprint imports) is exact and must be preserved.

**Current pattern** (`apps/launchpad/app/__init__.py` lines 44-67):
```python
app.config.setdefault("MONGO_SERVER_SELECTION_TIMEOUT_MS", 2000)
mongo.init_app(app, serverSelectionTimeoutMS=app.config["MONGO_SERVER_SELECTION_TIMEOUT_MS"])
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
```

**Extend with** (RESEARCH.md Pattern 2 + Pattern 3, same "step 3" init-extensions block, before `return app`):
```python
from app.extensions import csrf, metrics, mongo  # add csrf to this import line

app.config.setdefault("WTF_CSRF_TIME_LIMIT", None)
csrf.init_app(app)

from app import catalog, events  # noqa: PLC0415 — deferred, mirrors blueprint imports
catalog.ensure_indexes()
events.ensure_indexes()
events.emit_platform_started_once()
```
Order matters: `mongo.init_app()` → `csrf.init_app()` → blueprint registration → `ensure_indexes()` calls → `emit_platform_started_once()` last (per RESEARCH.md architecture diagram).

---

### `apps/launchpad/app/config.py` (config, extend in place)

**Analog:** itself — env-sourced class attribute pattern with inline comment justifying every default.

**Current pattern** (`apps/launchpad/app/config.py` lines 27-51, representative slice):
```python
class Config:
    MONGO_URI: str = os.environ.get("MONGO_URI", "mongodb://localhost:27017/launchpad")
    FIELD_GUIDE_BASE_URL: str = os.environ.get("FIELD_GUIDE_BASE_URL", "http://field-guide-api")
    APP_VERSION: str = os.environ.get("APP_VERSION", "dev")
    DEBUG: bool = _env_flag("FLASK_DEBUG")
    TESTING: bool = False
```

**Add**, same style:
```python
SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-secret-key-not-for-production")
EVENTS_TTL_SECONDS: int = int(os.environ.get("EVENTS_TTL_SECONDS", "604800"))  # 7 days
```

---

### `apps/launchpad/app/routes/pages.py` (route/controller, request-response — extend in place)

**Analog:** itself. The existing stub routes for `/catalog` and `/feed` must keep their route paths and function names ("Phase 9 fills in real content" per the file's own docstring at lines 8-14) — do not rename.

**Current stub pattern** (`apps/launchpad/app/routes/pages.py` lines 17-43, full file):
```python
from flask import Blueprint, render_template

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@pages_bp.route("/catalog", methods=["GET"])
def catalog():
    """Render the service catalog page (Phase 9 fills in real content)."""
    return render_template("catalog.html")


@pages_bp.route("/diagnostics", methods=["GET"])
def diagnostics():
    return render_template("diagnostics.html")


@pages_bp.route("/feed", methods=["GET"])
def feed():
    """Render the activity feed page (Phase 9 fills in real content)."""
    return render_template("feed.html")
```

**New routes to add in this file** (per RESEARCH.md architecture diagram): `catalog()` becomes real (list_services + empty-state), plus new `GET/POST /catalog/new`, `GET /catalog/<name>`, `GET/POST /catalog/<name>/delete`. All must import via module attribute: `from app import catalog, events` then `catalog.list_services()`, `catalog.register_service(...)`, `events.record_event(...)` — never direct-name imports (see events.py section above).

**Full-page re-render on invalid form (D-06)** — no in-repo analog for form re-render exists; follow the official Flask WTForms pattern from RESEARCH.md (`flask.palletsprojects.com/en/stable/patterns/wtforms/`): on `form.validate_on_submit()` failure, re-render the SAME template with the SAME form object (preserves entered values + errors automatically) — never redirect on a validation failure, only on success.

---

### `apps/launchpad/app/routes/partials.py` (route/controller, request-response — extend in place)

**Analog:** itself — the HX-Request fragment/full-page branch is the exact pattern to copy for `/partials/feed`.

**Full existing pattern to copy** (`apps/launchpad/app/routes/partials.py` lines 32-57, full file):
```python
from flask import Blueprint, render_template, request

from app.cluster_state import get_cluster_state
from app.status import get_platform_status

partials_bp = Blueprint("partials", __name__, url_prefix="/partials")


@partials_bp.route("/status-cards", methods=["GET"])
def status_cards():
    status = get_platform_status()
    if request.headers.get("HX-Request") == "true":
        return render_template("partials/status_cards.html", status=status)
    return render_template("status_full_page.html", status=status)


@partials_bp.route("/cluster-state", methods=["GET"])
def cluster_state():
    state = get_cluster_state()
    if request.headers.get("HX-Request") == "true":
        return render_template("partials/cluster_state.html", state=state)
    return render_template("cluster_state_full_page.html", state=state)
```

**New route to add, same shape:**
```python
from app import events  # module-attribute import, not `from app.events import list_recent_events`

@partials_bp.route("/feed", methods=["GET"])
def feed():
    recent_events = events.list_recent_events()
    if request.headers.get("HX-Request") == "true":
        return render_template("partials/feed_events.html", events=recent_events)
    return render_template("feed_full_page.html", events=recent_events)
```
Note: `apps/launchpad/app/status.py`/`cluster_state.py` are imported by function name in `partials.py` today (`from app.cluster_state import get_cluster_state`) — this is SAFE for status/cluster_state because their tests monkeypatch deeper (e.g. `app.k8s.get_k8s_clients`, `requests.get`), not the top-level function itself. `events.py`/`catalog.py` are different: RESEARCH.md explicitly flags that tests WILL monkeypatch `record_event`/`list_recent_events` directly, so `partials.py` and `pages.py` must import `events`/`catalog` as modules, not import the functions by name.

---

### `apps/launchpad/app/templates/catalog.html` (component, request-response)

**Analog:** `apps/launchpad/app/templates/cluster_state_full_page.html` for table structure + `apps/launchpad/app/templates/partials/cluster_state.html` for the `<table><thead><tr><th scope="col">` markup shape (D-07 explicitly requires matching this exact markup).

**Table markup pattern to copy** (`apps/launchpad/app/templates/partials/cluster_state.html` lines 17-39):
```html
<table>
  <thead>
    <tr>
      <th scope="col">Name</th>
      <th scope="col">Phase</th>
      ...
    </tr>
  </thead>
  <tbody>
    {% for pod in state.pods %}
    <tr>
      <td>{{ pod.name }}</td>
      ...
    </tr>
    {% endfor %}
  </tbody>
</table>
```
Apply the SAME structure for the catalog table: columns Name (link) → Environment → Owner → Registered At, per UI-SPEC Table Contract.

**Current stub to replace** (`apps/launchpad/app/templates/catalog.html`, full file, 7 lines):
```html
{% extends "base.html" %}
{% block title %}Catalog{% endblock %}
{% block content %}
<h2>Catalog</h2>
<p>Service catalog coming soon.</p>
{% endblock %}
```
Keep `{% extends "base.html" %}` and the `{% block title %}`/`{% block content %}` structure — only the content block body changes.

**Empty-state CTA precedent:** no existing empty-state template in-repo; follow UI-SPEC.md's Copywriting Contract exactly ("No services registered yet" heading + "Register your first service to see it here..." body + "Onboard your first service" button to `/catalog/new`).

---

### `apps/launchpad/app/templates/onboard_form.html` (component, request-response)

**No in-repo analog** (first form in the codebase). Structure per UI-SPEC.md Form Contract: single-column stacked `<label>`-above-`<input>` fields, `{{ form.hidden_tag() }}` for CSRF (Flask-WTF convention), inline errors below each field inside the label block, `autofocus` on first errored field. Base template extension pattern is identical to `catalog.html`'s `{% extends "base.html" %}` / `{% block content %}` shape shown above — reuse verbatim.

---

### `apps/launchpad/app/templates/detail.html` and `confirm_delete.html` (component, request-response)

**Analog:** `apps/launchpad/app/templates/cluster_state_full_page.html` for the two-section pattern (heading + `{% include %}`-style content block):
```html
{% extends "base.html" %}
{% block title %}Cluster State{% endblock %}
{% block content %}
<h1>Cluster State</h1>
<section id="cluster-state">
  {% include "partials/cluster_state.html" %}
</section>
{% endblock %}
```
`detail.html` follows this shape for its two sections ("Registration" + "Related Events", the latter including `partials/event_row.html` in a loop per D-09's "reuse the same event-row partial" instruction). `confirm_delete.html` follows the same minimal `{% extends %}` / `{% block content %}` shape as the `catalog.html` stub, with a `<form method="post">` embedding `{{ form.hidden_tag() }}` (or a bare CSRF token) per the Confirm-Page Contract in UI-SPEC.md.

---

### `apps/launchpad/app/templates/feed.html` (component, request-response + polling — extend stub)

**Analog:** `apps/launchpad/app/templates/diagnostics.html` — this is an EXACT match for the htmx polling shell pattern, including the visibility-guard syntax UI-SPEC.md explicitly requires be copied verbatim.

**Polling shell pattern to copy** (`apps/launchpad/app/templates/diagnostics.html` lines 6-14):
```html
<section id="status-cards"
         hx-get="{{ url_for('partials.status_cards') }}"
         hx-trigger="load, every 15s [document.visibilityState === 'visible'], visibilitychange[document.visibilityState === 'visible'] from:document"
         hx-swap="innerHTML">
  <article class="status-card status-card--unknown">
    <p>Loading platform status…</p>
  </article>
</section>
```

**Apply for `/feed`:**
```html
<section id="activity-feed"
         hx-get="{{ url_for('partials.feed') }}"
         hx-trigger="load, every 15s [document.visibilityState === 'visible'], visibilitychange[document.visibilityState === 'visible'] from:document"
         hx-swap="innerHTML">
  <p>Loading activity…</p>
</section>
```
Note: `diagnostics.html`'s second `#cluster-state` section polls at `every 10s` — do NOT copy that interval; FEED uses `every 15s` per D-11 (matches the first `#status-cards` section's interval, not the second).

**Current stub to replace** (`apps/launchpad/app/templates/feed.html`, full file):
```html
{% extends "base.html" %}
{% block title %}Activity Feed{% endblock %}
{% block content %}
<h2>Activity Feed</h2>
<p>Activity feed coming soon.</p>
{% endblock %}
```

---

### `apps/launchpad/app/templates/partials/event_row.html`, `feed_events.html`, `feed_full_page.html`

**Analog:** `apps/launchpad/app/templates/partials/status_cards.html` for "bare fragment, no wrapper element" style (event_row.html is analogous to ONE card in that file); `apps/launchpad/app/templates/partials/cluster_state.html` for "loop + conditional empty/error states" (feed_events.html); `apps/launchpad/app/templates/cluster_state_full_page.html` for the full-page wrapper (feed_full_page.html).

**Bare-fragment-per-item pattern** (`apps/launchpad/app/templates/partials/status_cards.html`, representative single card, lines 1-4):
```html
<article class="status-card status-card--{{ 'ok' if status.mongo_status == 'up' else 'degraded' }}">
  <header>MongoDB</header>
  <p>{{ status.mongo_status }}</p>
</article>
```
`event_row.html` follows this same one-fragment-per-datum shape (no `{% extends %}`, called via `{% include %}` or a `{% for %}` loop from `feed_events.html`), per the Event-Row Anatomy contract in UI-SPEC.md (icon glyph + type label + optional service-name link + relative time).

**List-with-conditional-states pattern** (`apps/launchpad/app/templates/partials/cluster_state.html` lines 1-16, the `{% if %}`/`{% elif %}`/`{% else %}` branching for degraded states):
```html
{% if state.available == False %}
<article class="status-card status-card--unknown">
  <header>Cluster State</header>
  <p>Not running in a cluster — Kubernetes view disabled</p>
</article>
{% elif state.error == "forbidden" %}
...
{% else %}
<table>...</table>
{% endif %}
```
`feed_events.html` follows the same shape but branches on empty-vs-populated (UI-SPEC's "No activity yet" empty state) rather than error states, then loops `{% for event in events %}{% include "partials/event_row.html" %}{% endfor %}`.

**Full-page wrapper pattern** — copy `cluster_state_full_page.html` verbatim structure (shown in detail.html section above) for `feed_full_page.html`.

---

### `apps/launchpad/tests/conftest.py` (test fixture, extend in place)

**Analog:** itself. The `app`/`client` fixtures already provide mongomock-backed `mongo.db`/`mongo.cx` with NO additional fixture plumbing needed for the new `services`/`events` collections (RESEARCH.md Pitfall 4 confirms this explicitly — same mocked `db` object, just new collection names).

**Existing mongomock injection pattern** (`apps/launchpad/tests/conftest.py` lines 19-46, full `app` fixture):
```python
@pytest.fixture
def app(monkeypatch):
    from app import create_app
    from app.extensions import mongo

    application = create_app({"TESTING": True, "MONGO_URI": "mongodb://localhost:27017/test_db"})

    mock_client = mongomock.MongoClient()
    mock_db = mock_client["test_db"]

    monkeypatch.setattr(mongo, "cx", mock_client)
    monkeypatch.setattr(mongo, "db", mock_db)

    yield application
```
**Add to this fixture** (per RESEARCH.md Pattern 3's "conftest.py implication"): after yield-setup, call `events.reset_platform_started_guard_for_tests()` (module-attribute call, `import app.events as events_module` style, mirroring the `k8s_disabled` fixture's `import app.k8s as k8s_module` idiom below) so each isolated test app independently exercises the once-per-process guard.

**Module-attribute monkeypatch fixture pattern to mirror** (`apps/launchpad/tests/conftest.py` lines 54-64, `k8s_disabled` fixture — this is the exact shape any new `events`/`catalog` test fixture should follow):
```python
@pytest.fixture
def k8s_disabled(monkeypatch):
    import app.k8s as k8s_module
    monkeypatch.setattr(k8s_module, "get_k8s_clients", lambda: (None, None))
    return k8s_module
```

**Document the TTL mongomock limitation** as a code comment in this file per RESEARCH.md Pitfall 1 — mirrors the existing docstring discipline (module docstring lines 1-11 already explains the mongomock/monkeypatch rationale in this exact style).

**Add:** a `csrf_enabled_client` fixture (or equivalent) per RESEARCH.md Pitfall 3 / Code Examples — the one dedicated CSRF-proving test, following the "GET first, scrape token, POST it back" pattern shown in RESEARCH.md's Code Examples section.

---

### `apps/launchpad/tests/test_catalog.py`, `test_events.py` (test, CRUD / event-driven)

**Analog:** `apps/launchpad/tests/test_status.py` — same shape: import the module under test, call inside `with app.app_context():`, assert on the returned dict/tuple, plus a dedicated "never raises past this function" style test and a "no missing timeout" grep-gate companion test (see `test_status_no_requests_get_call_missing_timeout` at lines 145-158 for the grep-gate pattern; adapt equivalently if catalog/events introduce any timeout-bearing calls).

**Representative test shape to copy** (`apps/launchpad/tests/test_status.py` lines 17-25):
```python
def test_status_mongo_up_field_guide_reachable(app, mock_requests_get):
    with app.app_context():
        result = get_platform_status()

    assert result["mongo_status"] == "up"
    assert result["api_health"] == "ok"
```

---

### `apps/launchpad/tests/test_pages.py`, `test_partials.py` (test, request-response — extend in place)

**Analog:** themselves. `test_partials.py`'s fragment-vs-full-page assertion pattern (lines 15-32) is the exact template for `/partials/feed` tests:
```python
def test_status_cards_fragment_when_hx_request_present(client, mock_requests_get):
    resp = client.get("/partials/status-cards", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "<html" not in body
    assert "<!doctype" not in body.lower()
```
`test_pages.py`'s `test_all_pages_render` (lines 64-68) must be extended to cover the new routes (`/catalog/new`, `/catalog/<name>`, `/catalog/<name>/delete`) — this is a maintained single source of truth for "every page route returns 200," do not create a parallel duplicate test.

---

### `apps/launchpad/requirements.txt` (config, extend in place)

**Analog:** itself — flat pinned-version list, one package per line, header comment citing verification source.

**Current pattern** (full file, 10 lines):
```
# Runtime dependencies — pinned to exact versions for reproducible builds.
# Versions verified against official PyPI and CLAUDE.md technology stack (Jul 2026).
Flask==3.1.3
Flask-PyMongo==3.0.1
pymongo==4.13.2
kubernetes==36.0.2
prometheus-flask-exporter==0.23.2
python-dotenv==1.2.2
requests==2.34.2
gunicorn==26.0.0
```
**Add:** `Flask-WTF==1.3.0` (do not pin WTForms separately, per RESEARCH.md Standard Stack recommendation).

---

### `charts/launchpad/templates/mongodb/{deployment,pvc,secret,service}.yaml` (migration/manifest — new directory)

**Analog:** `charts/field-guide-api/templates/mongodb/` — this is a MECHANICAL MIRROR per CONTEXT.md's explicit instruction; every file, field, and probe strategy is a copy with `field-guide-api` → `launchpad` naming substitutions and database name changed to `launchpad`.

**deployment.yaml full analog** (`charts/field-guide-api/templates/mongodb/deployment.yaml`, full file, 68 lines) — copy verbatim, substituting `field-guide-api.mongodb.fullname`/`field-guide-api.labels`/`field-guide-api.mongodb.selectorLabels` helper calls with `launchpad.mongodb.fullname`/`launchpad.labels`/`launchpad.mongodb.selectorLabels` (helpers must be added to `_helpers.tpl` first — see below). Key details to preserve: `strategy.type: Recreate` (NOT RollingUpdate — corruption hazard comment at lines 19-23), `mongosh --eval "db.adminCommand('ping')"` readinessProbe (NOT authenticated), `MONGO_INITDB_ROOT_USERNAME`/`PASSWORD` via `secretKeyRef`.

**pvc.yaml full analog** (`charts/field-guide-api/templates/mongodb/pvc.yaml`, full file, 25 lines) — copy verbatim with name substitution; `ReadWriteOnce`, `storage: {{ .Values.mongodb.persistence.size }}`, optional `storageClassName`.

**secret.yaml full analog** (`charts/field-guide-api/templates/mongodb/secret.yaml`, full file, 18 lines) — copy verbatim; `stringData` with `MONGO_INITDB_ROOT_USERNAME`/`PASSWORD` sourced from `.Values.mongodb.auth.*`.

**service.yaml full analog** (`charts/field-guide-api/templates/mongodb/service.yaml`, full file, 22 lines) — copy verbatim; `ClusterIP`, port 27017, selector via `launchpad.mongodb.selectorLabels`.

All four files must keep the `{{- if .Values.mongodb.enabled }}` / `{{- end }}` guard wrapper exactly as field-guide-api does.

---

### `charts/launchpad/templates/_helpers.tpl` (config, extend in place)

**Analog:** `charts/field-guide-api/templates/_helpers.tpl` lines 35-44 and 74-87 — add the two mongodb-specific helpers that are currently ABSENT from launchpad's `_helpers.tpl` (which explicitly notes at line 5: "No mongodb subchart in this chart (deferred to Phase 9, DEP-03) — no mongodb helpers here" — this comment must be removed/updated when the helpers are added).

**Helpers to add** (`charts/field-guide-api/templates/_helpers.tpl` lines 36-44, 74-87):
```
{{/*
Fully qualified name for MongoDB resources.
SINGLE SOURCE OF TRUTH — used by BOTH templates/mongodb/service.yaml (metadata.name)
and templates/secret.yaml (MONGO_URI hostname). Never write the mongodb hostname elsewhere.
*/}}
{{- define "launchpad.mongodb.fullname" -}}
{{- printf "%s-mongodb" (include "launchpad.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
MongoDB selector labels — DISTINCT identity from the app selectorLabels
(prevents the app Service from routing traffic to mongod).
*/}}
{{- define "launchpad.mongodb.selectorLabels" -}}
app.kubernetes.io/name: {{ include "launchpad.name" . }}-mongodb
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
```

---

### `charts/launchpad/templates/secret.yaml`, `configmap.yaml`, `deployment.yaml`, `values.yaml` (config, extend in place)

**Analog:** themselves + `charts/field-guide-api/values.yaml` lines 47-58 for the `mongodb:` values block shape.

**secret.yaml current** (full file, 17 lines) — extend `stringData` with `SECRET_KEY` alongside existing `MONGO_URI`:
```yaml
stringData:
  MONGO_URI: {{ .Values.mongoUri | quote }}
  SECRET_KEY: {{ .Values.secretKey | quote }}
```

**values.yaml mongodb block to add** (mirror `charts/field-guide-api/values.yaml` lines 47-58, substituting db name):
```yaml
mongodb:
  enabled: true
  image: mongo:7
  auth:
    username: root
    password: launchpad-dev-password   # local kind only; never a real credential
    database: launchpad
  persistence:
    enabled: true
    size: 1Gi
```
Also update `mongoUri` (currently `mongodb://localhost:27017/launchpad?serverSelectionTimeoutMS=2000` placeholder at line 46) to point at the new in-cluster `launchpad.mongodb.fullname` Service hostname, and add `secretKey` + `config.eventsTtlSeconds: "604800"` placeholders.

**configmap.yaml current** (full file, 16 lines) — extend `data` with `EVENTS_TTL_SECONDS`:
```yaml
data:
  FIELD_GUIDE_BASE_URL: {{ .Values.config.fieldGuideBaseUrl | quote }}
  APP_VERSION: {{ .Values.config.appVersion | quote }}
  FLASK_DEBUG: {{ .Values.config.flaskDebug | quote }}
  EVENTS_TTL_SECONDS: {{ .Values.config.eventsTtlSeconds | quote }}
```

**deployment.yaml env block** (`charts/launchpad/templates/deployment.yaml` lines 52-76) — extend with `SECRET_KEY` (secretKeyRef) and `EVENTS_TTL_SECONDS` (configMapKeyRef), same pattern as the existing `MONGO_URI`/`FIELD_GUIDE_BASE_URL` entries shown there. **D-08 resolution note:** once the in-cluster Mongo Service is the real `MONGO_URI` target, the `readinessProbe` docstring comment at lines 6-8 ("pod is expected to show READY 0/1... until then") becomes stale and should be updated/removed since the pod now flips to Ready.

## Shared Patterns

### Never-raise helper discipline (applies to `catalog.py`, `events.py`)
**Source:** `apps/launchpad/app/status.py` (whole file), `apps/launchpad/app/cluster_state.py` (whole file)
**Apply to:** `app/catalog.py`, `app/events.py`
Every exported function catches `Exception` broadly at each sub-operation, discards exception detail entirely (never `str(exception)`), and returns a safe sentinel (empty list, `False`, `(False, message)`, or a bounded dict) instead of propagating. No function in these modules may ever raise past its own boundary.

### Module-attribute import for monkeypatchable seams
**Source:** `apps/launchpad/app/cluster_state.py` lines 9-18, 26, 99 (`from app import k8s` → `k8s.get_k8s_clients()`)
**Apply to:** `app/routes/pages.py`, `app/routes/partials.py` — any call site into `app.events` or `app.catalog` from a route module. Import the module (`from app import events`), call via attribute (`events.record_event(...)`). Never `from app.events import record_event`.

### HX-Request fragment/full-page branching
**Source:** `apps/launchpad/app/routes/partials.py` lines 40-57 (both existing routes)
**Apply to:** new `GET /partials/feed` route
```python
if request.headers.get("HX-Request") == "true":
    return render_template("partials/feed_events.html", events=recent_events)
return render_template("feed_full_page.html", events=recent_events)
```

### Visibility-guarded htmx polling trigger
**Source:** `apps/launchpad/app/templates/diagnostics.html` line 9 (verbatim syntax, copy exactly, only the interval/target differ)
**Apply to:** `app/templates/feed.html`
```
hx-trigger="load, every 15s [document.visibilityState === 'visible'], visibilitychange[document.visibilityState === 'visible'] from:document"
```

### Fixed generic error strings (T-08-06 discipline)
**Source:** `apps/launchpad/app/status.py` lines 63-66 docstring; UI-SPEC.md Copywriting Contract error rows
**Apply to:** all new route/form error paths — e.g. `"Could not save this service. Check the fields below and try again."` — never interpolate `str(exception)` into any HTML response.

### App-factory extension wiring (unbound singleton → `init_app()`)
**Source:** `apps/launchpad/app/extensions.py` (whole file) + `apps/launchpad/app/__init__.py` lines 44-53
**Apply to:** `csrf = CSRFProtect()` in `extensions.py`, `csrf.init_app(app)` in `create_app()`, same two-step shape as `mongo`/`metrics`.

### Chart mongodb mirroring (Helm)
**Source:** `charts/field-guide-api/templates/mongodb/*.yaml` + `charts/field-guide-api/templates/_helpers.tpl` lines 36-44, 74-87 + `charts/field-guide-api/values.yaml` lines 47-58
**Apply to:** `charts/launchpad/templates/mongodb/*.yaml`, `charts/launchpad/templates/_helpers.tpl`, `charts/launchpad/values.yaml` — pure mechanical mirror, `field-guide-api` → `launchpad` name substitution, database name `fieldguide` → `launchpad`.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `apps/launchpad/app/forms.py` | model | request-response | First WTForms usage in the codebase — no prior form/validation module exists. Use RESEARCH.md Pattern 1 (already vetted, includes UI-SPEC-aligned field/validator/copy mapping) as the authoritative source instead of a codebase analog. |
| `apps/launchpad/app/templates/onboard_form.html` | component | request-response | First `<form>` template in the codebase. Follow UI-SPEC.md's Form Contract section directly (field order, label placement, error placement, button hierarchy) — no existing template has this shape to copy from; `base.html`'s extends/block structure is still reused (see catalog.html analog above). |
| `apps/launchpad/app/templates/confirm_delete.html` | component | request-response | First "destructive confirmation page" template. Structural shell reuses `catalog.html`'s minimal stub shape; content follows UI-SPEC.md's Confirm-Page Contract verbatim (no prior confirm-flow template exists). |

## Metadata

**Analog search scope:** `apps/launchpad/app/` (all modules, routes, templates, static), `apps/launchpad/tests/` (all test files + conftest.py), `charts/field-guide-api/` (mongodb manifests + helpers + values.yaml — read-only reference chart), `charts/launchpad/` (all chart files — target for edits)
**Files scanned:** 30 (11 Python app modules, 10 templates, 10 test files, 9 chart files across 2 charts, requirements.txt, style.css)
**Pattern extraction date:** 2026-07-12
