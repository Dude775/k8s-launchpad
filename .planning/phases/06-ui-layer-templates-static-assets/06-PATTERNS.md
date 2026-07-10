# Phase 6: UI Layer — Templates + Static Assets - Pattern Map

**Mapped:** 2026-07-10
**Files analyzed:** 15 (7 new source files, 3 new test files, 2 vendored static assets, 2 modified source files, 1 modified test-adjacent registration file)
**Analogs found:** 13 / 15 (2 vendored static assets have no code analog — see "No Analog Found")

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `apps/launchpad/app/routes/pages.py` | route/controller | request-response | `apps/launchpad/app/routes/health.py` | role-match (same app, simpler GET-only shape) |
| `apps/launchpad/app/routes/partials.py` | route/controller | request-response (htmx fragment) | `apps/launchpad/app/routes/health.py` | role-match |
| `apps/launchpad/app/routes/__init__.py` | route (barrel/re-export) | — | itself (existing file, modified) | exact |
| `apps/launchpad/app/__init__.py` | config/app-factory | — | itself (existing file, modified) + `apps/field-guide-api/app/__init__.py` | exact (same file, already has the blueprint-registration slot) |
| `apps/launchpad/app/templates/base.html` | template (page shell) | request-response (SSR) | none in-repo (first Jinja template in monorepo) | no analog — use RESEARCH.md Pattern 2 verbatim |
| `apps/launchpad/app/templates/index.html` | template (page) | request-response (SSR) | `apps/launchpad/app/templates/base.html` (sibling, once created) | no analog — use RESEARCH.md Pattern 2/3 |
| `apps/launchpad/app/templates/catalog.html` | template (page) | request-response (SSR) | `apps/launchpad/app/templates/index.html` (sibling, once created) | no analog — thin extends-only stub |
| `apps/launchpad/app/templates/diagnostics.html` | template (page) | request-response (SSR) | `apps/launchpad/app/templates/index.html` (sibling) | no analog — thin extends-only stub |
| `apps/launchpad/app/templates/feed.html` | template (page) | request-response (SSR) | `apps/launchpad/app/templates/index.html` (sibling) | no analog — thin extends-only stub |
| `apps/launchpad/app/templates/partials/status_cards.html` | template (fragment, no layout) | request-response (SSR fragment) | none in-repo | no analog — use RESEARCH.md Pattern 3 verbatim |
| `apps/launchpad/app/static/style.css` | asset (companion stylesheet) | file-I/O (static serving) | none in-repo | no analog — use UI-SPEC.md Color/Typography tables |
| `apps/launchpad/app/static/vendor/htmx.min.js` | asset (vendored, binary-ish) | file-I/O (static serving) | none — vendored via direct download | no analog (not code) |
| `apps/launchpad/app/static/vendor/pico.min.css` | asset (vendored, binary-ish) | file-I/O (static serving) | none — vendored via direct download | no analog (not code) |
| `apps/launchpad/tests/test_pages.py` | test | request-response | `apps/field-guide-api/tests/test_routes.py` + `apps/launchpad/tests/test_health.py` | role-match (exact shape once combined) |
| `apps/launchpad/tests/test_partials.py` | test | request-response | `apps/launchpad/tests/test_health.py` | role-match |
| `apps/launchpad/tests/test_static_assets.py` | test | file-I/O + content-assertion | `apps/field-guide-api/tests/test_entries.py` (assertion style only, not file-I/O) | partial-match |

## Pattern Assignments

### `apps/launchpad/app/routes/pages.py` (route, request-response)

**Analog:** `apps/launchpad/app/routes/health.py` (exact same package, same Blueprint idiom)

**Imports pattern** (health.py lines 1-14, adapt `jsonify`→`render_template`):
```python
from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health():
    """Return a plain liveness signal."""
    return jsonify({"status": "ok"}), 200
```

**Core pattern to apply** (from RESEARCH.md Code Examples, already project-conformant):
```python
from flask import Blueprint, render_template

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@pages_bp.route("/catalog", methods=["GET"])
def catalog():
    return render_template("catalog.html")


@pages_bp.route("/diagnostics", methods=["GET"])
def diagnostics():
    return render_template("diagnostics.html")


@pages_bp.route("/feed", methods=["GET"])
def feed():
    return render_template("feed.html")
```

**Docstring convention** — `health.py` lines 1-10 establish the project convention of a
module-level docstring documenting the route contract and forward-looking phase notes
(e.g. "This route name stays stable across phases: Phase 7 evolves this in place").
`pages.py` should follow the same convention, noting `/catalog`, `/diagnostics`, `/feed`
render thin placeholder content in Phase 6 and are filled in by Phase 8 (diagnostics) and
Phase 9 (catalog, feed) — mirrors the "evolve route in place, don't rename" pattern
already established in Phase 5 for `/health`.

**Error handling:** None needed — all four routes are static `render_template()` calls
with zero user input, zero DB/K8s calls, so there is no failure path to handle (matches
`health.py`'s Phase-5-era simplicity before Mongo/K8s wiring existed).

---

### `apps/launchpad/app/routes/partials.py` (route, request-response / htmx fragment)

**Analog:** `apps/launchpad/app/routes/health.py` (Blueprint shape) + RESEARCH.md Pattern 3 (exact target code)

**Core pattern** (RESEARCH.md Code Examples, verbatim — already matches project conventions):
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

**Docstring convention:** Follow `health.py`'s pattern of stating the stable contract
up front — additionally document (per RESEARCH.md Pitfall 3) that this route is
htmx-fragment-only by design and must NEVER grow an `HX-Request`-conditional branch
that wraps it in `base.html`; a new route should be added instead if direct-navigation
polish is ever wanted.

---

### `apps/launchpad/app/routes/__init__.py` (route barrel, modified)

**Analog:** itself (existing file)

**Current content** (full file, 6 lines):
```python
# Route blueprint package.
# Re-exports so callers can do: from app.routes import health_bp
from app.routes.health import health_bp

__all__ = ["health_bp"]
```

**Required edit — extend, do not restructure:**
```python
# Route blueprint package.
# Re-exports so callers can do: from app.routes import health_bp
from app.routes.health import health_bp
from app.routes.pages import pages_bp
from app.routes.partials import partials_bp

__all__ = ["health_bp", "pages_bp", "partials_bp"]
```

---

### `apps/launchpad/app/__init__.py` (app factory, modified)

**Analog:** itself (existing file) — also cross-checked against `apps/field-guide-api/app/__init__.py` which already shows the "register two blueprints" shape this phase needs.

**Current content** (full file, 55 lines) — the deferred-import block to extend is at
lines 48-54:
```python
    # 4. Register blueprints — DEFERRED import so this module is importable
    #    before the route files exist.
    from app.routes.health import health_bp  # noqa: PLC0415

    app.register_blueprint(health_bp)

    return app
```

**field-guide-api's two-blueprint precedent** (`app/__init__.py` lines 53-59, proves the
project's established multi-blueprint registration idiom):
```python
    from app.routes.entries import entries_bp  # noqa: PLC0415
    from app.routes.health import health_bp  # noqa: PLC0415

    app.register_blueprint(entries_bp)
    app.register_blueprint(health_bp)

    return app
```

**Required edit for launchpad** (RESEARCH.md Code Examples — exact target, matches both
precedents above):
```python
    from app.routes.health import health_bp        # noqa: PLC0415
    from app.routes.pages import pages_bp           # noqa: PLC0415  (NEW, Phase 6)
    from app.routes.partials import partials_bp     # noqa: PLC0415  (NEW, Phase 6)

    app.register_blueprint(health_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(partials_bp)

    return app
```
No other part of `create_app()` changes — `Flask(__name__)` already resolves
`app/templates/` and `app/static/` by default (RESEARCH.md Pattern 1), no factory-level
template/static configuration is needed.

---

### `apps/launchpad/app/templates/base.html` (template, SSR shell)

**Analog:** None in-repo — this is the first Jinja template in the monorepo. Use
RESEARCH.md Pattern 2 verbatim as the source of truth; UI-SPEC.md supplies the exact
copy strings and color/spacing tokens to slot in.

**Structure to build** (RESEARCH.md Pattern 2, full example — already project-vetted):
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Dashboard{% endblock %} - k8s-launchpad</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='vendor/pico.min.css') }}">
  <link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
  <script src="{{ url_for('static', filename='vendor/htmx.min.js') }}" defer></script>
</head>
<body>
  <div class="layout">
    <nav class="sidebar" aria-label="Primary">
      <ul>
        <li><a href="{{ url_for('pages.index') }}"
               {% if request.endpoint == 'pages.index' %}aria-current="page"{% endif %}>
               Dashboard</a></li>
        <li><a href="{{ url_for('pages.catalog') }}"
               {% if request.endpoint == 'pages.catalog' %}aria-current="page"{% endif %}>
               Catalog</a></li>
        <li><a href="{{ url_for('pages.diagnostics') }}"
               {% if request.endpoint == 'pages.diagnostics' %}aria-current="page"{% endif %}>
               Diagnostics</a></li>
        <li><a href="{{ url_for('pages.feed') }}"
               {% if request.endpoint == 'pages.feed' %}aria-current="page"{% endif %}>
               Activity Feed</a></li>
      </ul>
    </nav>
    <div class="main">
      <header class="topbar"><strong>k8s-launchpad</strong> — Internal Developer Platform</header>
      <main>{% block content %}{% endblock %}</main>
    </div>
  </div>
</body>
</html>
```
Note: added a second `<link>` for `static/style.css` (not in the raw RESEARCH.md excerpt
but required by UI-SPEC.md's Color section — the companion stylesheet overriding Pico's
CSS custom properties must load AFTER `pico.min.css` to win the cascade).

**Copy strings (UI-SPEC.md Copywriting Contract, exact):**
- Nav labels: "Dashboard", "Catalog", "Diagnostics", "Activity Feed" — sentence case, no
  trailing punctuation.
- Topbar/brand label: "k8s-launchpad — Internal Developer Platform".

---

### `apps/launchpad/app/templates/index.html` (template, SSR page)

**Analog:** `base.html` (once created, in the same directory) via `{% extends %}` —
no other in-repo analog exists.

**Core pattern** (RESEARCH.md Pattern 3, index.html excerpt — the htmx polling contract):
```html
{% extends "base.html" %}
{% block content %}
<h1>k8s-launchpad</h1>
<section id="status-cards"
         hx-get="{{ url_for('partials.status_cards') }}"
         hx-trigger="load, every 15s [document.visibilityState === 'visible'], visibilitychange[document.visibilityState === 'visible'] from:document"
         hx-swap="innerHTML">
  <!-- Server-rendered fallback for the very first paint before htmx's `load`
       trigger fires (also what a no-JS browser sees) -->
  <article class="status-card status-card--unknown">
    <p>Loading platform status…</p>
  </article>
</section>
{% endblock %}
```
Loading-state copy is pinned verbatim by UI-SPEC.md: "Loading platform status…"
(ellipsis character, not three periods).

**Contract values pinned by UI-SPEC.md Interaction Contract table (do not deviate):**

| Property | Value |
|----------|-------|
| Poll route | `GET /partials/status-cards` |
| Poll interval | `every 15s` |
| Visibility guard | `[document.visibilityState === 'visible']` bracket filter + `visibilitychange[...] from:document` |
| Swap mode | `hx-swap="innerHTML"` |

---

### `apps/launchpad/app/templates/catalog.html`, `diagnostics.html`, `feed.html` (templates, SSR pages)

**Analog:** `index.html` (sibling, once created) — these three are structurally
identical thin stubs; only the heading text and `{% block title %}` differ.

**Pattern (per RESEARCH.md project structure comment: "placeholder content, filled in
by later phases"):**
```html
{% extends "base.html" %}
{% block title %}Catalog{% endblock %}
{% block content %}
<h2>Catalog</h2>
<p>Service catalog coming soon.</p>
{% endblock %}
```
Apply the same shape for `diagnostics.html` ("Diagnostics" — Phase 8 fills in) and
`feed.html` ("Activity Feed" — Phase 9 fills in). Heading text is `<h2>` per UI-SPEC.md
Typography table (Heading role, 20px/600/1.2), matching "page titles… 'Catalog',
'Diagnostics', 'Activity Feed'" exactly as listed.

---

### `apps/launchpad/app/templates/partials/status_cards.html` (template, SSR fragment)

**Analog:** None — must NOT `{% extends "base.html" %}` (RESEARCH.md Anti-Patterns:
"Reusing base.html for the status-cards partial" is explicitly listed as a mistake to
avoid, since this fragment is swapped into an existing DOM node).

**Core pattern** (RESEARCH.md Pattern 3, verbatim):
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
Copy strings corrected to match UI-SPEC.md Copywriting Contract exactly (the RESEARCH.md
draft used slightly different wording — UI-SPEC.md is the authoritative copy source):
- Empty-state heading: "Status unavailable"
- Empty-state body: "The platform status API is not connected yet. This will populate
  automatically once available."

---

### `apps/launchpad/app/static/style.css` (asset, companion stylesheet)

**Analog:** None in-repo — new file. Source of truth is UI-SPEC.md Color/Typography
sections (Pico's documented zero-build CSS-custom-property override path).

**Required overrides (UI-SPEC.md Color table, exact values):**
```css
:root {
  --pico-primary: #2563eb;
  --pico-del-color: #dc2626;
}
@media (prefers-color-scheme: dark) {
  :root {
    --pico-primary: #3b82f6;
  }
}

/* Resolves RESEARCH.md Open Question 1 / UI-SPEC.md fallback: ensure active
   sidebar nav link is visually distinct even if Pico's shipped nav CSS only
   styles aria-current for horizontal/breadcrumb nav, not sidebar <ul><li>. */
.sidebar a[aria-current="page"] {
  font-weight: 600;
  color: var(--pico-primary);
}

/* Heading weight override — UI-SPEC.md Typography: Pico default is 700,
   this phase pins headings to 600 for a flatter platform-engineering look. */
h1, h2, h3 {
  font-weight: 600;
}

/* Sidebar nav link minimum touch target — UI-SPEC.md Spacing Scale exception
   (44px, not a multiple of 4, WCAG 2.5.5). */
.sidebar a {
  display: block;
  min-height: 44px;
}
```
Loaded in `base.html` after `pico.min.css` (cascade order matters — see base.html
pattern above).

---

### `apps/launchpad/tests/test_pages.py` (test, request-response)

**Analog:** `apps/launchpad/tests/test_health.py` (fixture usage: bare `client` fixture,
no mocking needed) combined with `apps/field-guide-api/tests/test_routes.py`
(multi-route-in-one-file organization with section-comment banners).

**Fixture usage pattern** (`test_health.py`, full file — the exact fixture shape to reuse):
```python
def test_health_ok(client):
    """GET /health returns 200 {"status": "ok"}."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}
```
No new conftest fixtures are required — `apps/launchpad/tests/conftest.py` already
provides `app`/`client` (isolated `create_app({"TESTING": True})` instance), which is
sufficient for template-rendering routes with zero DB/K8s dependency.

**Section-banner organization pattern** (`apps/field-guide-api/tests/test_routes.py`
lines 16-20, adapt per-route):
```python
# --------------------------------------------------------------------------- #
# Blueprint existence                                                           #
# --------------------------------------------------------------------------- #
```

**Content-assertion style to reuse for UI-01/UI-02/UI-03/UI-04**
(`apps/field-guide-api/tests/test_entries.py` lines 19-25, adapt `.get_json()` →
`.get_data(as_text=True)` substring assertions since these are HTML, not JSON):
```python
def test_list_empty(client):
    """GET /entries returns 200 and an empty JSON list on a fresh collection."""
    resp = client.get("/entries")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data, list)
    assert data == []
```
Translated shape for `test_pages.py` (illustrative, not copy-paste — planner should
write concrete assertions per UI-01..04 in RESEARCH.md's Requirements → Test Map):
```python
def test_index_200_and_content(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "k8s-launchpad" in body
    assert "Internal Developer Platform" in body


def test_active_nav_per_route(client):
    resp = client.get("/catalog")
    body = resp.get_data(as_text=True)
    assert 'aria-current="page"' in body  # exactly one active link


def test_status_cards_not_hardcoded(client):
    body = client.get("/").get_data(as_text=True)
    assert 'hx-get="/partials/status-cards"' in body


def test_polling_attribute_contract(client):
    body = client.get("/").get_data(as_text=True)
    assert "every 15s" in body
    assert "visibilityState" in body
```

---

### `apps/launchpad/tests/test_partials.py` (test, request-response)

**Analog:** `apps/launchpad/tests/test_health.py` (identical bare-`client`-fixture
shape; no mocking needed since the Phase 6 stub route has no external dependency).

**Pattern:**
```python
def test_status_cards_degraded_when_no_data(client):
    """GET /partials/status-cards always returns 200 with the unknown/degraded
    empty-state fragment in Phase 6 — no data source exists yet (never 500)."""
    resp = client.get("/partials/status-cards")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Status unavailable" in body
    assert "<html" not in body  # fragment only, never a full page (RESEARCH Pitfall 3)
```

---

### `apps/launchpad/tests/test_static_assets.py` (test, file-I/O + content-assertion)

**Analog:** No direct file-I/O test analog exists in-repo (no prior phase tests
filesystem presence of static assets). Assertion-style borrowed from
`apps/field-guide-api/tests/test_entries.py`'s "never 500 / contract" assertions
(pattern: assert an absence, not just a presence).

**Pattern to build (per RESEARCH.md Validation Architecture UI-05 row):**
```python
from pathlib import Path


def test_vendored_assets_exist_on_disk():
    static_dir = Path(__file__).parent.parent / "app" / "static" / "vendor"
    assert (static_dir / "htmx.min.js").is_file()
    assert (static_dir / "pico.min.css").is_file()


def test_no_cdn_references(client):
    """UI-05: rendered HTML must reference only local /static/vendor/ assets,
    never a CDN URL — enforced across the shell + all four page routes."""
    for path in ("/", "/catalog", "/diagnostics", "/feed"):
        body = client.get(path).get_data(as_text=True)
        assert "https://unpkg.com" not in body
        assert "https://cdn." not in body
        assert 'src="http://' not in body and 'href="http://' not in body
```

---

## Shared Patterns

### App-factory blueprint registration
**Source:** `apps/launchpad/app/__init__.py` lines 48-54 (existing), precedent confirmed
by `apps/field-guide-api/app/__init__.py` lines 53-59
**Apply to:** `pages_bp` and `partials_bp` registration — deferred import inside
`create_app()`, `# noqa: PLC0415` comment on each import line, registered after
`health_bp` in the same block. Do not add module-level imports at the top of
`app/__init__.py` — the deferred-import discipline is load-bearing (documented in the
module docstring: "importable before route files exist").

### Blueprint module shape (docstring + Blueprint() + route function)
**Source:** `apps/launchpad/app/routes/health.py` (full file, 21 lines)
**Apply to:** `pages.py`, `partials.py` — every route module in this project opens with
a module docstring stating the exact route contract (method, path, status codes,
forward-looking phase notes), followed by `bp_name = Blueprint("name", __name__)`,
followed by one `@bp.route(...)` decorated function per endpoint with a one-line
docstring.

### Flask static/template resolution — zero config
**Source:** RESEARCH.md Pattern 1, confirmed against `apps/launchpad/app/__init__.py`'s
existing `Flask(__name__)` call (line 36, unmodified)
**Apply to:** All templates and static assets — `app/templates/` and `app/static/` are
auto-resolved; no `Flask()` constructor argument changes needed. The existing Dockerfile
`COPY app/ ./app/` line (both `apps/launchpad/Dockerfile` and
`apps/field-guide-api/Dockerfile` share this exact allowlist pattern) already captures
both new directories with no Dockerfile edit.

### Test fixture reuse — no new conftest needed
**Source:** `apps/launchpad/tests/conftest.py` (existing, `app`/`client` fixtures)
**Apply to:** `test_pages.py`, `test_partials.py`, `test_static_assets.py` — all three
new test files consume the existing bare `client` fixture; none require `k8s_disabled`,
`k8s_enabled`, or `mock_requests_get` since no route touches K8s or Mongo in this phase.

### 100%-coverage pytest gate
**Source:** `apps/launchpad/pytest.ini` (existing, unmodified)
```ini
[pytest]
testpaths = tests
addopts = --cov=app --cov-report=term-missing --cov-fail-under=100
pythonpath = .
```
**Apply to:** All new route code in `pages.py`/`partials.py` must be fully exercised —
every one of the four page routes needs at least one test hit, and the partial route's
single branch needs a test hit, or `make test-launchpad` fails the build.

### Docstring "route contract stays stable across phases" convention
**Source:** `apps/launchpad/app/routes/health.py` lines 6-9 ("This route name stays
stable across phases: Phase 7 evolves this same /health in place…")
**Apply to:** `partials.py`'s `status_cards()` docstring (RESEARCH.md Pattern 3 already
includes this framing) and `pages.py`'s module docstring (note `/catalog`,
`/diagnostics`, `/feed` are placeholder-content routes filled in by Phase 8/9, not
renamed or restructured).

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `apps/launchpad/app/static/vendor/htmx.min.js` | asset | file-I/O | Vendored via direct `curl` download from unpkg.com, not authored code — no codebase analog applies; RESEARCH.md Installation section gives the exact download command and version pin (2.0.10) |
| `apps/launchpad/app/static/vendor/pico.min.css` | asset | file-I/O | Same as above — vendored via direct download, version pin 2.1.1; RESEARCH.md flags both files for a `checkpoint:human-verify` size/hash sanity check before commit (~50KB / ~90KB respectively) |

All template files (`base.html`, `index.html`, `catalog.html`, `diagnostics.html`,
`feed.html`, `partials/status_cards.html`) and `static/style.css` also have no in-repo
code analog (first Jinja/CSS authored files in the monorepo), but each has a fully
worked, project-vetted example in RESEARCH.md Architecture Patterns / Code Examples and
exact copy/color/spacing values in UI-SPEC.md — these are treated as the authoritative
"analog" source for this phase rather than a codebase file, and are captured in full
above under Pattern Assignments.

## Metadata

**Analog search scope:** `apps/launchpad/` (full tree), `apps/field-guide-api/` (full
tree) — no other app directories exist in the monorepo yet (Phase 9's catalog/feed
backend and Phase 8's diagnostics backend are future phases, not yet scaffolded)
**Files scanned:** 26 (all non-cache, non-venv files under both app directories)
**Pattern extraction date:** 2026-07-10
