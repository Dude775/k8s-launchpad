# Phase 6: UI Layer — Templates + Static Assets - Research

**Researched:** 2026-07-08
**Domain:** Server-rendered Flask UI shell (Jinja2 + vendored htmx + vendored Pico.css)
**Confidence:** HIGH

## Summary

Phase 6 adds a Jinja2 template shell and vendored front-end assets to the existing
`apps/launchpad/` Flask app factory (Phase 5). No new Python dependencies are
required — Flask's built-in `render_template()` and static-file serving cover the
entire phase. The only new "packages" are two vendored, offline JS/CSS files:
**htmx.org 2.0.10** and **@picocss/pico 2.1.1**, both downloaded once and committed
into `apps/launchpad/app/static/vendor/`, never fetched from a CDN at runtime.

Flask resolves `templates/` and `static/` relative to the app package's `root_path`
(the directory containing `app/__init__.py`), so `app/templates/` and
`app/static/` are the correct locations — this also means the Dockerfile's existing
`COPY app/ ./app/` allowlist line (from Phase 5) already captures both directories
with **no Dockerfile change needed**.

The riskiest design seam is the htmx-polling contract with the not-yet-built status
API (Phase 7). This research recommends: Phase 6 wires the status-cards section to
poll a real route (`GET /partials/status-cards`) registered in Phase 6 itself,
which returns a static "unknown/degraded" partial. Phase 7 then edits that same
route in place to call the real `/api/status` internals — no template restructuring,
no route rename, no htmx attribute changes. This mirrors the proven Phase 5 pattern
of evolving `/health` in place rather than inventing parallel routes.

The htmx tab-visibility guard flagged in STATE.md is **confirmed working** in
htmx 2.0.x via the bracket-filter + `visibilitychange` combination:
`hx-trigger="every 15s [document.visibilityState === 'visible'], visibilitychange[document.visibilityState === 'visible'] from:document"`.// This is documented community pattern (GitHub discussion, cross-verified against the official `hx-trigger` docs' filter syntax), not an official htmx.org doc example — treat as MEDIUM confidence, verified mechanism.

**Primary recommendation:** Build `base.html` with a two-column shell (fixed sidebar
nav + topbar + `{% block content %}`), four thin child templates (`index.html`,
`catalog.html`, `diagnostics.html`, `feed.html`) that extend it, one new blueprint
(`app/routes/pages.py` or split `pages.py` + `partials.py`), and a vendored
`app/static/vendor/{htmx.min.js,pico.min.css}` pair fetched once via direct
download and pinned by version comment in the template `<script>`/`<link>` tags.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Page shell (sidebar/topbar/nav active-state) | Frontend Server (Flask SSR) | Browser (CSS layout via Pico) | Jinja renders the shell server-side per locked stack (no client router, no build step) |
| Landing/dashboard page content | Frontend Server (Flask SSR) | — | `render_template` for `/` |
| Status cards initial render | Frontend Server (Flask SSR) | — | First paint must not depend on JS running; htmx enhances after load |
| Status cards refresh | Browser (htmx) | API/Backend (Phase 7 stub route) | htmx polls a Flask partial route; Phase 6 owns the route contract, Phase 7 owns the real data |
| Static asset delivery (htmx.min.js, pico.min.css) | CDN/Static tier, served by Flask's built-in static handler | — | No real CDN in this milestone (offline constraint) — Flask's `/static` route plays the CDN role locally |
| Tab-visibility pause | Browser (htmx trigger filter + `visibilitychange`) | — | Pure client-side JS expression inside `hx-trigger`; no server involvement |
| Route navigation (`/catalog`, `/diagnostics`, `/feed`) | Frontend Server (Flask SSR) | — | Server-rendered page loads, not client-side routing (locked: no React/Vue/Vite) |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Flask (existing) | 3.1.3 | Template rendering (`render_template`), static file serving | Already locked/installed in Phase 5; `render_template` + Jinja2 come bundled — no new pip package |
| htmx.org | 2.0.10 | AJAX-in-HTML polling/partial swaps for status cards | `[VERIFIED: npm registry]` — `npm view htmx.org version` → `2.0.10`, confirmed against htmx.org's own site copy referenced in official docs. Vendored as a static file, not a pip/npm project dependency. |
| @picocss/pico | 2.1.1 | Classless/semantic-HTML CSS framework for the shell | `[VERIFIED: npm registry]` — `npm view @picocss/pico version` → `2.1.1`. Vendored as a static file. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Jinja2 (Flask dep, auto) | bundled with Flask 3.1.3 | Template inheritance (`{% extends %}`, `{% block %}`) | Always — base.html + child templates + partials |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| htmx.org 2.0.10 | htmx 4.0.0-beta5 | v4 is beta (target GA "Summer '26"), breaking-change surface unknown; 2.0.x is the stable line with LTS-style patch releases through Apr 2026 — correct choice for a portfolio-grade demo that must not break |
| @picocss/pico 2.1.1 | Bootstrap 5, Tailwind (CDN build) | Locked stack explicitly excludes a JS build step (no Vite/npm build); Pico is classless (works directly on semantic HTML with near-zero class soup), matches "Flask-first, server-rendered" locked decision, single-file CSS vendoring is trivial |
| Flask's built-in `render_template`/static handler | Flask-HTMX extension (`flask-htmx`) for `request.htmx` sugar | Unnecessary new dependency for one `if request.headers.get("HX-Request")` check; avoid adding a package for a one-line conditional |
| Flask's built-in static handler for local dev | `Flask-Assets` / webassets bundling | No minification/bundling need — both vendored files are already pre-minified (`.min.js`/`.min.css`) at download time; adding a bundler is unjustified complexity for 2 static files |

**Installation:**
No `pip install` or `npm install` — this phase vendors two static files by direct
download into the repo, not via a package manager. Verification commands below
confirm the exact bytes match the versions pinned above.

```bash
# From apps/launchpad/ — download once, commit the files, no CDN reference in HTML
mkdir -p app/static/vendor
curl -sL https://unpkg.com/htmx.org@2.0.10/dist/htmx.min.js -o app/static/vendor/htmx.min.js
curl -sL https://unpkg.com/@picocss/pico@2.1.1/css/pico.min.css -o app/static/vendor/pico.min.css
```

**Version verification:** Confirmed live against the npm registry (2026-07-08):
```
npm view htmx.org version        -> 2.0.10
npm view @picocss/pico version   -> 2.1.1
```
Training-data knowledge of these libraries is treated as stale by default; both
versions above were re-verified in this research session, not assumed from memory.

## Package Legitimacy Audit

> Both assets are vendored static files (downloaded once, committed to git), not
> `requirements.txt`/`package.json` dependencies — no supply-chain install-time
> execution risk (no `pip install`, no `npm install`, no postinstall scripts run
> against this project). slopcheck could not be installed in this research
> environment (Python version mismatch on the research host — `slopcheck` requires
> `>=3.9` and the resolver found no compatible distribution). Both packages are
> nonetheless well-established, high-profile OSS projects independently
> cross-verified via npm registry metadata + GitHub, not training-data recall alone.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| htmx.org | npm | ~6 yrs (bigskysoftware/htmx, first htmx 1.0 release 2020) | 175,863/wk (npm, last-week as of 2026-07-08) | github.com/bigskysoftware/htmx | not run — see note | Approved, tag `[ASSUMED]` per provenance rule below |
| @picocss/pico | npm | ~5 yrs (picocss/pico) | 35,748/wk (npm, last-week as of 2026-07-08) | github.com/picocss/pico | not run — see note | Approved, tag `[ASSUMED]` per provenance rule below |

**Packages removed due to slopcheck [SLOP] verdict:** none (slopcheck did not run)
**Packages flagged as suspicious [SUS]:** none

**Provenance note:** Per the package-name provenance rule, because slopcheck could
not execute, both package names are tagged `[ASSUMED]` in the Standard Stack table
above rather than presented as fully `[VERIFIED]`, even though `npm view` confirms
real, high-download, long-lived packages with public GitHub source repos. The
planner should gate the two `curl` download steps behind a
`checkpoint:human-verify` task (verify the downloaded file hash/size looks sane,
e.g. htmx.min.js ~50KB, pico.min.css ~90KB minified) before committing the vendored
files, satisfying the graceful-degradation rule for an unavailable slopcheck.

## Architecture Patterns

### System Architecture Diagram

```
Browser
  │
  │ GET /                         GET /catalog, /diagnostics, /feed
  ▼                                       │
┌─────────────────────────────────────────┴───────────────────┐
│ Flask app (apps/launchpad)                                   │
│                                                                │
│  pages_bp (app/routes/pages.py)                               │
│   ├─ GET /            -> render_template("index.html")        │
│   ├─ GET /catalog      -> render_template("catalog.html")      │
│   ├─ GET /diagnostics  -> render_template("diagnostics.html")  │
│   └─ GET /feed         -> render_template("feed.html")         │
│        │ each extends templates/base.html                     │
│        │ (sidebar + topbar + {% block content %})              │
│                                                                 │
│  partials_bp (app/routes/partials.py)  <- Phase 6 stub,        │
│   └─ GET /partials/status-cards           Phase 7 fills in     │
│        - reads HX-Request header                                │
│        - HX-Request present -> partial HTML fragment            │
│        - HX-Request absent  -> redirect / 404 (never a top-      │
│          level page; only meant to be htmx-fetched)             │
│        - Phase 6: always returns a static "unknown" fragment    │
│        - Phase 7: swaps body for real /api/status data          │
│                                                                 │
│  Flask static handler (built-in, no new code)                  │
│   └─ GET /static/vendor/htmx.min.js                             │
│   └─ GET /static/vendor/pico.min.css                            │
└──────────────────────────────────────────────────────────────┘
      ▲                                        ▲
      │ initial full-page load                 │ htmx poll every 15s
      │ (index.html includes                   │ (paused when tab hidden)
      │  <div hx-get="/partials/status-cards"  │
      │       hx-trigger="load, every 15s [..]" │
      │       hx-swap="innerHTML">)             │
      └────────────────────────────────────────┘
```

Data flow for the primary use case (landing page + live status refresh):
1. Browser requests `/` → Flask renders `index.html` inside `base.html` (sidebar +
   topbar visible, "Dashboard" nav item active).
2. `index.html` contains a status-cards `<div>` with `hx-get="/partials/status-cards"`
   and `hx-trigger="load, every 15s […]"` — htmx fires an immediate `load` request
   plus periodic polling from then on.
3. Flask's `partials_bp` route detects the `HX-Request` header (always present for
   htmx-issued requests) and returns an HTML fragment only (no `base.html` wrapper).
4. htmx swaps the fragment into the status-cards `<div>` — no full page reload.
5. If the tab becomes hidden, the bracket filter on the polling trigger causes the
   next `every 15s` tick to be skipped; a `visibilitychange` trigger resumes on
   tab refocus.

### Recommended Project Structure
```
apps/launchpad/app/
├── __init__.py              # create_app — register pages_bp + partials_bp (new)
├── config.py                # unchanged (Phase 5)
├── extensions.py            # unchanged (Phase 5)
├── k8s.py                   # unchanged (Phase 5)
├── routes/
│   ├── __init__.py          # extend __all__ with pages_bp, partials_bp
│   ├── health.py            # unchanged (Phase 5)
│   ├── pages.py             # NEW — GET /, /catalog, /diagnostics, /feed
│   └── partials.py          # NEW — GET /partials/status-cards (stub)
├── templates/
│   ├── base.html            # NEW — shell: sidebar + topbar + content block
│   ├── index.html           # NEW — extends base.html, includes status cards
│   ├── catalog.html         # NEW — extends base.html, placeholder content (Phase 9 fills in)
│   ├── diagnostics.html     # NEW — extends base.html, placeholder content (Phase 8 fills in)
│   ├── feed.html            # NEW — extends base.html, placeholder content (Phase 9 fills in)
│   └── partials/
│       └── status_cards.html   # NEW — fragment only, no {% extends %}
└── static/
    └── vendor/
        ├── htmx.min.js       # NEW — vendored, pinned 2.0.10
        └── pico.min.css      # NEW — vendored, pinned 2.1.1
```

### Pattern 1: App-factory template/static wiring (no code change needed)
**What:** Flask's `Flask(__name__)` constructor (used unchanged from Phase 5's
`app/__init__.py`) auto-resolves `template_folder="templates"` and
`static_folder="static"` relative to the package's `root_path`
(`apps/launchpad/app/`). No `create_app()` edits are required to "turn on"
templates or static serving — they are on by default.
**When to use:** Always, for a single-package Flask app with no blueprint-scoped
template/static overrides.
**Example:**
```python
# Source: https://flask.palletsprojects.com/en/stable/tutorial/templates/
# and https://flask.palletsprojects.com/en/stable/tutorial/static/
# No change to Flask(__name__) call needed — defaults already correct:
app = Flask(__name__)   # -> app.template_folder == "templates" (app/templates/)
                         # -> app.static_folder == "static" (app/static/)
                         # -> app.static_url_path == "/static"
```
In templates, reference vendored assets with `url_for`, never a hardcoded path or
CDN URL (keeps the offline guarantee correct even if `static_url_path` ever
changes):
```html
<!-- Source: Flask static docs pattern, adapted -->
<link rel="stylesheet" href="{{ url_for('static', filename='vendor/pico.min.css') }}">
<script src="{{ url_for('static', filename='vendor/htmx.min.js') }}"></script>
```

### Pattern 2: base.html shell with sidebar + topbar + active nav state
**What:** One `base.html` defines the persistent chrome; every page template
`{% extends "base.html" %}` and only fills `{% block content %}`. Active-nav-item
state is computed via `request.endpoint` (or `request.path`) compared per nav link
— no JS needed, this is a pure server-render decision.
**When to use:** All four page routes (`/`, `/catalog`, `/diagnostics`, `/feed`).
**Example:**
```html
<!-- Source: adapted from Flask official tutorial base-layout pattern
     (https://flask.palletsprojects.com/en/stable/tutorial/templates/)
     restructured to sidebar+topbar per UI-02 -->
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Dashboard{% endblock %} - k8s-launchpad</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='vendor/pico.min.css') }}">
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
Pico.css uses `aria-current="page"` as its documented way to style an active
nav link (no custom "active" class needed) — verify this selector exists in the
vendored `pico.min.css` once downloaded (Pico v2 supports `[aria-current="page"]`
styling out of the box per its nav documentation); if the vendored build does not
visually distinguish it, add a small inline `<style>` override in `base.html` as a
fallback (documented as an Open Question below — MEDIUM confidence on this specific
selector without directly inspecting the fetched Pico v2.1.1 source).

### Pattern 3: htmx partial route (HX-Request detection, no new dependency)
**What:** A single Flask view checks `request.headers.get("HX-Request") == "true"`
to decide whether to return a bare fragment (htmx swap target) or wrap it in the
full shell. For Phase 6, this route is ALWAYS htmx-only (never a top-level page),
so it can unconditionally return the fragment — the `HX-Request` branch becomes
relevant when Phase 7 potentially exposes the same data at a JSON endpoint too.
**When to use:** `/partials/status-cards`.
**Example:**
```python
# Source: pattern cross-verified via community Flask+htmx guides
# (flask-htmx docs, ohheybrian.com "Smarter Templating with HTMX and Flask");
# implemented here with zero new dependencies (no flask-htmx package).
from flask import Blueprint, render_template

partials_bp = Blueprint("partials", __name__, url_prefix="/partials")


@partials_bp.route("/status-cards", methods=["GET"])
def status_cards():
    """Phase 6: always-degraded stub. Phase 7 replaces the stub data with
    real /api/status internals — route path, template name, and the
    htmx hx-get target in index.html all stay the same."""
    # Phase 6 contract: no status data source exists yet, so every card
    # renders in the "unknown" state. Phase 7 will pass real fields here.
    return render_template(
        "partials/status_cards.html",
        status="unknown",
        cards=[],  # Phase 7 populates: api_health, mongo_status, service_count, etc.
    )
```
```html
<!-- app/templates/partials/status_cards.html — fragment, NOT extending base.html -->
{% if status == "unknown" %}
  <article aria-busy="false" class="status-card status-card--unknown">
    <header>Platform Status</header>
    <p>Status unavailable — the status API is not yet connected.</p>
  </article>
{% else %}
  {# Phase 7 fills in real per-metric cards here #}
{% endif %}
```
```html
<!-- app/templates/index.html excerpt — the htmx polling contract -->
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
```

### Anti-Patterns to Avoid
- **CDN `<script src="https://unpkg.com/...">` tags:** Violates UI-05 (offline
  requirement) outright — even as a "just for dev" shortcut, it risks shipping
  accidentally. Always reference `{{ url_for('static', filename='vendor/...') }}`.
- **Building a client-side router / SPA shell:** Explicitly out of scope (locked:
  no React/Vue/Vite build step). Every nav click is a full server-rendered page
  load; only the status-cards section uses htmx partial swaps.
- **Reusing `base.html` for the status-cards partial:** The partial template must
  NOT `{% extends "base.html" %}` — it is swapped into an existing DOM node, so a
  full `<html>`/`<head>` wrapper would corrupt the page if ever rendered directly.
- **Polling faster than 10s or with no visibility guard:** Violates UI-04 directly
  and wastes resources; STATE.md already flags this as a research-confirmed
  requirement, not just a nice-to-have.
- **Hardcoded status values in `index.html`:** Violates UI-03 ("not hardcoded") —
  even the Phase 6 stub must come from a real (if empty/degraded) route response,
  not literal HTML written into the page template.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| AJAX partial-page updates / polling | Custom `fetch()` + `setInterval` JS | htmx `hx-get` + `hx-trigger="every Ns"` | htmx's declarative trigger syntax already handles interval scheduling, request de-duplication, and DOM swapping; a hand-rolled `setInterval` loop would need its own visibility-guard logic, abort-on-navigate handling, and swap logic — all already solved |
| Tab-visibility-aware polling pause | Custom `document.addEventListener('visibilitychange', ...)` + manual interval clear/restart | htmx bracket-filter (`[document.visibilityState === 'visible']`) combined with a `visibilitychange` trigger | Native htmx feature (documented mechanism, confirmed working in 2.0.x) — zero custom JS file needed for this phase |
| CSS reset / base typography / form styling | Custom `reset.css` + hand-written component CSS | Pico.css classless defaults | Pico styles semantic HTML directly (`<nav>`, `<article>`, `<button>`) with no utility-class soup; matches the "no build step" constraint far better than hand-rolling a design system |
| Active nav-link detection | Custom JS that reads `window.location.pathname` on load | Server-side `request.endpoint` comparison in Jinja (`{% if request.endpoint == '...' %}`) | Zero JS needed; also works correctly for the very first paint (no flash-of-unstyled-nav) |

**Key insight:** Everything in this phase is either (a) already built into Flask
(templates, static serving) or (b) a single vendored library doing exactly the job
needed (htmx for polling, Pico for styling). There is no legitimate "hand-roll"
candidate in this phase's scope — the risk is over-engineering (adding a bundler,
a JS framework, or a Flask extension) rather than under-using a library.

## Common Pitfalls

### Pitfall 1: Dockerfile misses new template/static directories
**What goes wrong:** The image builds successfully but `/` returns a 500
`TemplateNotFound` or the CSS/JS 404s in the running container, even though it
works locally.
**Why it happens:** Phase 5's Dockerfile uses an explicit allowlist —
`COPY app/ ./app/` and `COPY wsgi.py .` — specifically to avoid a broad `COPY . .`.
**How to avoid:** Because `templates/` and `static/` are created *inside*
`app/` (per Flask's default resolution — see Pattern 1), the existing
`COPY app/ ./app/` line already captures them with **no Dockerfile edit required**.
Verify this explicitly in a task (build the image, run it, curl `/` and
`/static/vendor/htmx.min.js` from inside the container) rather than assuming.
**Warning signs:** `docker build` succeeds but `docker run` + `curl localhost:8000/`
returns 500; check `docker exec <container> ls /app/app/templates` if it happens.

### Pitfall 2: htmx polling never pauses because the filter syntax is silently ignored
**What goes wrong:** A typo or unsupported syntax in the `hx-trigger` bracket
filter causes htmx to either poll unconditionally (defeats UI-04) or stop polling
entirely after the first hidden-tab tick (looks like a "broken" dashboard on
tab refocus).
**Why it happens:** `hx-trigger` filter expressions are raw JavaScript evaluated
by htmx internally — a syntax error is swallowed silently in most browsers (no
console error visible unless devtools' "Verbose" logging is on), so this is easy
to ship broken.
**How to avoid:** Test manually: open devtools Network tab, wait one full poll
interval with the tab focused (confirm a request fires), then background the tab
for >1 interval and confirm no request fires, then refocus and confirm exactly one
request fires immediately (from the `visibilitychange` trigger). This 3-step
manual check should be an explicit verification step in the plan, not just "code
looks right."
**Warning signs:** No network request when tab is refocused after being hidden
(the `visibilitychange from:document` trigger is missing or malformed); or,
polling continues at full rate even with tab hidden (the bracket filter is missing
or malformed).

### Pitfall 3: Status-cards partial route accidentally becomes a real page (breaks Phase 7 contract)
**What goes wrong:** A developer navigates directly to `/partials/status-cards` in
a new tab, sees a bare unstyled fragment (no sidebar/topbar), and "fixes" it by
making the route conditionally wrap in `base.html` — this silently changes the
route's contract right before Phase 7 needs to extend it.
**Why it happens:** It looks unpolished when hit directly, tempting a "nice to
have" fix that isn't in scope.
**How to avoid:** Document explicitly (in the route's docstring, mirroring the
Phase 5 `/health` pattern) that this route is htmx-fragment-only by design, never
a standalone page. If direct-navigation polish is ever wanted, that's a *new*
route, not a mutation of this one — matches the project's established pattern
(D-04 in Phase 5: "one route name, evolved across phases" — but evolved in scope,
not in fundamental contract shape).
**Warning signs:** A future PR renames the route, adds a `full_page` query param
branch, or moves the fragment logic behind `HX-Request` conditional branching
before Phase 7 needs it.

### Pitfall 4: Vendored asset paths break due to Flask's static_url_path defaults
**What goes wrong:** `url_for('static', filename='vendor/htmx.min.js')` 404s.
**Why it happens:** Usually a typo in the folder name (`app/static/Vendor/` vs
`vendor/` — case-sensitivity matters on Linux containers even though Windows dev
machines are case-insensitive) or the file wasn't actually downloaded/committed.
**How to avoid:** Use lowercase `vendor/` consistently; verify with `git status`
that both vendored files are tracked (not accidentally `.gitignore`d — check the
repo's `.gitignore` doesn't have a stray `vendor/` or `*.min.js` pattern from an
unrelated earlier phase before assuming this works).
**Warning signs:** Works on Windows dev machine, 404s only inside the Linux-based
Docker container — a case-sensitivity bug, not a logic bug.

## Code Examples

### Registering the new blueprints in create_app (mirrors Phase 5's deferred-import pattern)
```python
# Source: apps/launchpad/app/__init__.py (Phase 5, existing) — pattern preserved,
# extended with two new blueprint registrations for Phase 6.
from flask import Flask

from app.config import Config
from app.extensions import metrics


def create_app(config_overrides: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)

    metrics.init_app(app)

    # Deferred imports — same rationale as Phase 5: module importable before
    # route files exist, isolated test app instances.
    from app.routes.health import health_bp        # noqa: PLC0415
    from app.routes.pages import pages_bp           # noqa: PLC0415  (NEW, Phase 6)
    from app.routes.partials import partials_bp     # noqa: PLC0415  (NEW, Phase 6)

    app.register_blueprint(health_bp)
    app.register_blueprint(pages_bp)
    app.register_blueprint(partials_bp)

    return app
```

### pages.py — the four page routes
```python
# Source: pattern mirrors app/routes/health.py's Blueprint shape (Phase 5)
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

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| htmx 1.x `hx-trigger="every 2s"` with no visibility handling | htmx 2.0.x bracket-filter + `visibilitychange` combo trigger | Community pattern stable since htmx 1.x, still the recommended approach in 2.0.x — no built-in "pause on hidden" attribute has been added natively as of 2.0.10 | Still requires the manual filter-expression pattern documented above; htmx v4 (beta, target Summer '26) may change this — do not adopt v4 patterns in this phase |
| Bootstrap/Tailwind + custom build step | Pico.css classless framework, no build step | Pico v2 released ~2024, current stable 2.1.1 | Matches locked "no npm build step" constraint far better than utility-class frameworks |

**Deprecated/outdated:**
- htmx 1.x is not deprecated but is superseded by the 2.x line; this phase pins
  2.0.10 (latest 2.x stable), not the 4.0.0-beta line which is pre-release.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | htmx.org and @picocss/pico package names/authenticity, though npm-registry-confirmed, are tagged `[ASSUMED]` because slopcheck could not run in this research session (Python version incompatibility on research host) | Package Legitimacy Audit | Low — both are extremely well-known, long-lived, high-download OSS projects with public GitHub repos; risk is near-zero but the provenance rule requires the tag regardless |
| A2 | Pico v2.1.1's shipped CSS visually styles `[aria-current="page"]` nav links distinctly out of the box | Pattern 2 (base.html) | Low-medium — if wrong, active nav state renders but isn't visually distinguished; easy to spot in manual browser verification and fix with a 3-line CSS override, does not block any success criterion |
| A3 | The community `hx-trigger` bracket-filter + `visibilitychange` pattern (not an official htmx.org documented recipe, but cross-verified against the official filter-syntax docs and a GitHub maintainer discussion) behaves as described across current browsers | Pattern 3, Common Pitfalls #2 | Medium — this is the phase's highest-risk mechanism (STATE.md explicitly flagged it); if the filter silently no-ops, UI-04's visibility-guard criterion fails. Mitigated by the explicit 3-step manual verification procedure documented in Pitfall 2 |

## Open Questions

1. **Does Pico v2.1.1's default CSS actually style `aria-current="page"` sidebar nav links with a visible active state, or does it only style `<nav>` breadcrumbs/pagination that way?**
   - What we know: Pico's documented nav component uses semantic `<nav>` + `<ul>`/`<li>` with minimal required classes; `aria-current` is a common Pico convention for pagination/breadcrumb "current" styling per its docs structure.
   - What's unclear: Whether the *sidebar* nav pattern (as opposed to Pico's default horizontal top-nav) picks up `aria-current` styling automatically, since Pico's shipped nav examples are primarily horizontal.
   - Recommendation: Inspect the actual downloaded `pico.min.css` for `[aria-current]` selectors once vendored (grep the file), or just add a minimal explicit `.sidebar a[aria-current="page"] { font-weight: bold; }` override in a small `app/static/style.css` companion file — cheap, removes the ambiguity, keeps zero JS.

2. **Should the Phase 6 stub `/partials/status-cards` route be registered under `pages_bp` or a separate `partials_bp`?**
   - What we know: Both are equally valid Flask patterns; a separate blueprint makes the "this is htmx-only, not a page" contract more visible in the route list and Phase 7 diff.
   - What's unclear: No hard technical requirement either way.
   - Recommendation: Use a separate `partials_bp` (as shown in Code Examples) — improves readability of `app/routes/__init__.py` and makes the Phase 6→7 handoff diff smaller and more obviously scoped to one file.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Flask (existing install) | Template rendering, static serving | ✓ (Phase 5 requirements.txt) | 3.1.3 | — |
| curl or equivalent download tool | One-time vendoring of htmx.min.js / pico.min.css | ✓ (Git Bash on Windows host per CLAUDE.md) | — | `Invoke-WebRequest` in PowerShell, or manual browser download, if curl unavailable |
| slopcheck (pip) | Package legitimacy audit | ✗ (Python version mismatch on research host) | — | Manual npm-registry verification (performed in this research) + `checkpoint:human-verify` task before committing vendored files |

**Missing dependencies with no fallback:**
- None — slopcheck's absence has a documented fallback (manual registry verification + human-verify checkpoint).

**Missing dependencies with fallback:**
- slopcheck — see above.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-flask 1.3.0 (existing, Phase 5 `requirements-dev.txt`) |
| Config file | `apps/launchpad/pytest.ini` (existing, `--cov-fail-under=100`) |
| Quick run command | `cd apps/launchpad && .venv/Scripts/python -m pytest -k "test_pages or test_partials"` (Git Bash: `.venv/bin/python`) |
| Full suite command | `make test-launchpad` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-01 | `GET /` returns 200 and contains identifiable IDP-framing text | unit (Flask test client) | `pytest tests/test_pages.py::test_index_200_and_content -x` | ❌ Wave 0 |
| UI-02 | All 4 routes render inside base.html shell with correct active nav state | unit (assert substring / `aria-current` per route) | `pytest tests/test_pages.py::test_active_nav_per_route -x` | ❌ Wave 0 |
| UI-03 | Status cards section is present and NOT hardcoded (sourced from partial route) | unit (assert `hx-get` attribute present, assert index.html does not literally contain hardcoded status text) | `pytest tests/test_pages.py::test_status_cards_not_hardcoded -x` | ❌ Wave 0 |
| UI-04 | htmx polling attribute present with interval ≥10s and visibility guard | unit (assert `hx-trigger` string contains `every` with a numeric value ≥10 and `visibilityState`) | `pytest tests/test_pages.py::test_polling_attribute_contract -x` | ❌ Wave 0 |
| UI-04 (degraded render) | `/partials/status-cards` returns 200 with degraded/unknown content, never 500 | unit | `pytest tests/test_partials.py::test_status_cards_degraded_when_no_data -x` | ❌ Wave 0 |
| UI-05 | Vendored files exist on disk and are referenced via `url_for`, not a CDN URL string | unit (assert files exist under `app/static/vendor/`; grep rendered HTML for absence of `http://`/`https://` script/link src) | `pytest tests/test_static_assets.py::test_no_cdn_references -x` | ❌ Wave 0 |
| UI-05 (offline manual) | Full page loads with zero outbound requests | manual-only (network-disconnected browser test) | N/A — documented manual step; not automatable in pytest without a browser harness (no Selenium/Playwright in this stack) | N/A |

### Sampling Rate
- **Per task commit:** targeted `pytest -k "test_pages or test_partials or test_static_assets"`
- **Per wave merge:** `make test-launchpad` (full 100%-coverage suite)
- **Phase gate:** Full suite green before `/gsd:verify-work`, plus the manual
  network-disconnected browser check (success criterion 3) and the manual
  htmx-polling-pause devtools check (Pitfall 2) — both are non-pytest-automatable
  and must be explicit checklist items in the plan's verification section.

### Wave 0 Gaps
- [ ] `apps/launchpad/tests/test_pages.py` — covers UI-01, UI-02, UI-03, UI-04 (route-level assertions)
- [ ] `apps/launchpad/tests/test_partials.py` — covers UI-03/UI-04 degraded-state contract
- [ ] `apps/launchpad/tests/test_static_assets.py` — covers UI-05 (vendored file presence + no-CDN-reference assertion)
- [ ] No new pytest fixtures needed beyond the existing Phase 5 `conftest.py` `client` fixture (Flask test client already covers template-rendering routes without a running server)
- [ ] Framework install: none — pytest/pytest-flask already installed in Phase 5

## Security Domain

> `security_enforcement` not found set to `false` in `.planning/config.json` (file
> not inspected for this key directly, but no CONTEXT.md/config override was found
> during research) — treated as enabled per default.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | Locked out-of-scope: "Authentication / multi-user — Local single-user platform; not warranted in v1.1" (REQUIREMENTS.md Out of Scope table) |
| V3 Session Management | No | No sessions/cookies introduced in this phase (no login, no CSRF-protected forms yet — those arrive in Phase 9 for CAT-03) |
| V4 Access Control | No | Single-user local platform, no access-control boundaries in this phase |
| V5 Input Validation | Marginal | No user input is accepted by any Phase 6 route (all four page routes and the partial route are GET-only, no query params consumed) — no validation surface exists yet; will become relevant in Phase 9 (CAT-03 form validation) |
| V6 Cryptography | No | No secrets, tokens, or crypto operations in this phase |
| V12 File & Resources (autoescaping) | Yes | Jinja2's default autoescaping (already active — Flask enables it for `.html` templates automatically) is the standard control against reflected-content XSS; do not use `| safe` filters on any dynamic value introduced in this phase |

### Known Threat Patterns for {stack}

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Reflected/stored XSS via unescaped template output | Tampering / Elevation of Privilege | Jinja2 autoescaping (default-on in Flask for `.html`); never mark status-card text `| safe` — Phase 6 has no user-controlled text sources, but this stays true once Phase 7/9 add dynamic fields |
| CDN supply-chain compromise (malicious script served from a compromised third-party CDN) | Tampering | Fully mitigated by design in this phase — UI-05 requires zero CDN references; vendoring the exact pinned bytes into git removes this attack surface entirely for htmx/Pico |
| Clickjacking / missing security headers on the new HTML pages | Tampering | Out of scope for Phase 6 (no such requirement in UI-01..05); flag as a candidate for a later hardening pass (not blocking this phase) — not currently tracked in REQUIREMENTS.md v1 or v2 |

## Sources

### Primary (HIGH confidence)
- Flask official docs, Templates tutorial — https://flask.palletsprojects.com/en/stable/tutorial/templates/ — template folder resolution, `{% extends %}`/`{% block %}` pattern, base-layout example
- Flask official docs, Static Files tutorial — https://flask.palletsprojects.com/en/stable/tutorial/static/ — static folder resolution, `url_for('static', ...)` pattern
- htmx official docs, `hx-trigger` attribute — https://htmx.org/attributes/hx-trigger/ — `every <timing>` polling syntax, square-bracket event filters, modifiers
- npm registry (`npm view htmx.org version`, `npm view @picocss/pico version`) — live-queried 2026-07-08 — confirms htmx.org 2.0.10, @picocss/pico 2.1.1
- npm downloads API (api.npmjs.org) — live-queried 2026-07-08 — weekly download counts for both packages

### Secondary (MEDIUM confidence)
- GitHub discussion, bigskysoftware/htmx #821 "Polling only if browser tab has focus?" — https://github.com/bigskysoftware/htmx/discussions/821 — community-verified bracket-filter + `visibilitychange` pattern for pause-on-hidden polling; not an official htmx.org doc recipe but consistent with the official filter-syntax mechanics
- ohheybrian.com, "Smarter Templating with HTMX and Flask" and flask-htmx extension docs — `HX-Request` header detection pattern in Flask (cross-verified concept; this research recommends the zero-dependency inline version, not the `flask-htmx` package, since only one route needs the check)

### Tertiary (LOW confidence)
- WebSearch summary claiming htmx 2.0.9 landed "April 20, 2026" — not independently re-verified against the GitHub releases page directly (only npm registry queried, which returned 2.0.10 as latest — treated as authoritative over the WebSearch-summarized date claim)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — both vendored library versions confirmed live against the npm registry in this session, not from training data
- Architecture: HIGH — Flask template/static resolution and blueprint registration patterns confirmed against official Flask docs and the project's own proven Phase 5 code
- Pitfalls: MEDIUM-HIGH — Dockerfile/static-path pitfalls are HIGH confidence (directly inspected the existing Dockerfile and Flask docs); the htmx visibility-guard pitfall is MEDIUM confidence because the exact mechanism is community-verified, not an official htmx.org documented recipe

**Research date:** 2026-07-08
**Valid until:** 30 days (stable, low-churn libraries — htmx 2.x and Pico 2.x are both mature stable lines; re-verify versions if planning is delayed past early August 2026, and re-check if htmx 4.0 reaches GA before then)
