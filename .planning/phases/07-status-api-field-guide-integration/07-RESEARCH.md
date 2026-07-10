# Phase 7: Status API + Field-Guide Integration - Research

**Researched:** 2026-07-11
**Domain:** Flask readiness/status endpoints + cross-service HTTP reachability + Prometheus parity + htmx fragment evolution (own-MongoDB wiring via Flask-PyMongo)
**Confidence:** HIGH

## Summary

Phase 7 evolves three already-scaffolded seams in `apps/launchpad/` rather than
building anything from scratch: the `/health` stub (Phase 5), the `/metrics`
endpoint (already fully working since Phase 5 — `prometheus-flask-exporter` is
wired and verified live in this research session), and the
`/partials/status-cards` htmx fragment stub (Phase 6). No new blueprint files
are needed — this phase edits three existing route modules in place and adds
one new module (`app/status.py`, a plain internal helper) plus a new
`GET /api/status` JSON route.

The two genuinely new pieces of infrastructure are (1) Flask-PyMongo wiring
for launchpad's **own** MongoDB (mirroring field-guide-api's proven
`app/extensions.py`/`app/__init__.py` pattern almost verbatim — confirmed live
in this session that `flask-pymongo`/`pymongo` are NOT yet installed in
launchpad's venv, so this is a real new dependency add) and (2) a short-timeout
outbound HTTP call to field-guide-api using `requests` — which is **already
present in launchpad's venv as a transitive dependency of the `kubernetes`
package** (confirmed: `pip show requests` → 2.34.2, `pip show kubernetes` →
`Requires: ... requests ...`) but is **not pinned directly** in
`requirements.txt` and must be added explicitly, since transitive pins are not
guaranteed stable across `kubernetes` package upgrades.

The critical architectural rule from STATE.md (already a locked decision,
confirmed again here): `/health` checks ONLY launchpad's own MongoDB and NEVER
calls field-guide-api; `/api/status` is the ONLY route that reaches across the
cluster network to field-guide-api, and it must degrade gracefully (never
500, never hang the single gunicorn worker) when field-guide-api is
unreachable. This maps directly to the Kubernetes readinessProbe vs.
informational-dashboard-data distinction: a readinessProbe failure removes the
pod from Service Endpoints, so `/health` must reflect only what launchpad
itself needs to serve traffic — not a downstream service's availability.

**Primary recommendation:** Add `flask-pymongo==3.0.1` + `pymongo==4.13.2` +
`requests==2.34.2` to `apps/launchpad/requirements.txt` (exact versions
matching field-guide-api's proven pins for Flask-PyMongo/pymongo, and the
live-verified current `requests` release for the new dependency); wire Mongo
in `app/extensions.py`/`app/__init__.py` exactly like field-guide-api's Phase-2
pattern (2000ms `serverSelectionTimeoutMS`); evolve `/health` in place to ping
launchpad's own `mongo.cx.admin.command("ping")` (200/503, never touches
field-guide-api); add a new `app/status.py` module with a `get_platform_status()`
helper that `/api/status` and the `/partials/status-cards` fragment both call
(single source of truth, `/api/status` returns JSON, the partial route
renders the same dict into HTML); reach field-guide-api via `requests.get(f"{FIELD_GUIDE_BASE_URL}/health", timeout=2)` inside a
`try/except (requests.exceptions.RequestException)` block that sets
`field_guide_reachable: False` on any failure, never raising; `/metrics`
needs zero code changes (already registered) — this phase's `/metrics` work is
purely a verification + documentation task confirming parity with
field-guide-api's `/metrics`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `/health` readiness (own MongoDB only) | API/Backend (Flask route) | Database (launchpad's own MongoDB) | Kubernetes readinessProbe target — must reflect only what gates traffic to THIS pod; STATE.md locked decision explicitly forbids touching field-guide-api here |
| `/api/status` platform status aggregation | API/Backend (Flask route) | Database (own MongoDB) + external service (field-guide-api over cluster network) | Aggregates multiple internal/external signals into one JSON payload for the dashboard UI to consume; this is the ONLY route permitted to call field-guide-api |
| field-guide-api reachability check | API/Backend (outbound HTTP client inside Flask route) | External service boundary (field-guide-api ClusterIP Service) | Cross-service call over cluster DNS; must be short-timeout and exception-isolated so a downstream outage never propagates to launchpad's own health |
| `/metrics` Prometheus exposition | API/Backend (prometheus-flask-exporter middleware) | — | Already registered via `metrics.init_app(app)` in the Phase-5 app factory; auto-instruments every Flask route including the new ones added this phase |
| Status-cards htmx fragment rendering | Frontend Server (Flask SSR) | API/Backend (shares `get_platform_status()` with `/api/status`) | Phase 6 established this route contract (`HX-Request`-aware, fragment-only); Phase 7 fills in real data without changing the route shape |
| MongoDB connectivity (own instance) | Database / Storage | API/Backend (Flask-PyMongo extension) | Flask-PyMongo owns connection pooling and app-context binding; the route layer only calls `mongo.cx.admin.command("ping")` |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Flask-PyMongo | 3.0.1 | MongoDB integration extension for launchpad's own DB | `[VERIFIED: in-repo]` — identical version already locked in CLAUDE.md and running in production in `apps/field-guide-api/requirements.txt`; reusing the exact pin guarantees API compatibility already proven in this monorepo |
| pymongo | 4.13.2 | MongoDB driver (Flask-PyMongo's underlying dependency) | `[VERIFIED: in-repo]` — same reasoning; field-guide-api's `requirements.txt` already pins this exact version and it works against `mongo:7` |
| requests | 2.34.2 | Short-timeout outbound HTTP call to field-guide-api's `/health` | `[VERIFIED: pip show + WebSearch/PyPI]` — confirmed installed in launchpad's venv today (`pip show requests` → `Version: 2.34.2`) as a transitive dependency of the already-pinned `kubernetes==36.0.2` package; WebSearch cross-verified 2.34.2 as the current PyPI release (May 14 2026). Not currently a *direct* pin in `requirements.txt` — must be added explicitly so the exact version doesn't silently drift if `kubernetes`'s own `requests` pin changes on a future upgrade. |
| prometheus-flask-exporter | 0.23.2 (existing) | `/metrics` Prometheus exposition | `[VERIFIED: in-repo]` — already installed and wired in `apps/launchpad/app/extensions.py`/`app/__init__.py` since Phase 5; confirmed live in this research session that `GET /metrics` already returns 200 with valid Prometheus text format. No version change, no new wiring — this phase only needs a test asserting parity content (`flask_http_request_total`, `flask_http_request_duration_seconds` metric families). |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Flask (existing) | 3.1.3 | Route/blueprint registration, JSON responses | Already locked/installed — no change |
| mongomock (dev/test) | not yet installed — see Open Questions | In-memory MongoDB double for unit tests | Recommended for `/health` and `/api/status` unit tests that need a fake `mongo.cx` without a live cluster; field-guide-api's test suite pattern should be checked before this phase's planner commits to it (see Open Questions) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `requests` for the field-guide-api reachability call | stdlib `urllib.request` | `requests` is already a transitive dependency (zero net-new install cost at the OS/container level, since `kubernetes` pulls it in regardless) and matches field-guide-api's implicit HTTP client ergonomics (though field-guide-api itself makes no outbound calls); `urllib` requires manual timeout/exception-type handling that `requests` already normalizes (`requests.exceptions.RequestException` catches connection, timeout, and HTTP errors uniformly) — `requests` is the pragmatic choice given it's already on disk |
| Flask-PyMongo 3.0.1 for launchpad's own Mongo | raw `pymongo.MongoClient` in the app factory | Same reasoning as field-guide-api's original research: Flask-PyMongo handles app-context teardown and URI config with less boilerplate; reusing the exact same extension the sibling app already uses keeps the monorepo's two Flask apps structurally symmetric, which matters for a portfolio piece being reviewed side-by-side |
| Single shared `get_platform_status()` helper feeding both `/api/status` and the partial | Two independent implementations (one in the JSON route, one in the partial route) | Duplicating the aggregation logic risks the JSON and HTML views silently drifting (e.g. one checks field-guide-api, the other forgets to); a single internal helper returning a plain dict, consumed by both `jsonify()` and `render_template()`, is standard DRY practice and keeps STAT-01/STAT-02's five required JSON fields and the fragment's rendered cards provably in sync |
| `timeout=2` seconds for the field-guide-api HTTP call | `timeout=5` (matching the Phase 8 flagged K8s API `_request_timeout=5` convention) | 2 seconds matches the project's own established Mongo `serverSelectionTimeoutMS=2000` convention (field-guide-api `app/__init__.py`) — consistency with the sibling app's existing "fail fast under 3s" contract (its readinessProbe `timeoutSeconds: 3` is deliberately > the 2s Mongo timeout). Using 2s for field-guide-api reachability keeps `/api/status`'s worst-case latency bounded similarly. A 5s external-call timeout would be reasonable too, but 2s is more consistent with precedent already in this codebase and keeps the single gunicorn worker responsive. |

**Installation:**
```bash
# apps/launchpad/requirements.txt — add these three lines (verified versions above)
echo "Flask-PyMongo==3.0.1" >> apps/launchpad/requirements.txt
echo "pymongo==4.13.2" >> apps/launchpad/requirements.txt
echo "requests==2.34.2" >> apps/launchpad/requirements.txt
cd apps/launchpad && .venv/Scripts/python -m pip install -r requirements.txt
```

**Version verification:** Confirmed live in this research session (2026-07-11):
```
cd apps/launchpad && .venv/Scripts/python -m pip show requests
  -> Version: 2.34.2   (already installed, transitive via kubernetes==36.0.2)
cd apps/launchpad && .venv/Scripts/python -m pip show flask-pymongo pymongo
  -> Package(s) not found: flask-pymongo, pymongo   (confirmed NOT yet installed — new deps)
cd apps/launchpad && .venv/Scripts/python -m pip show prometheus-flask-exporter
  -> Version: 0.23.2   (already installed and wired — /metrics returns 200 today)
```
The Flask-PyMongo 3.0.1 / pymongo 4.13.2 pins are not re-verified against a live
PyPI index in this session (the sandboxed `pip index versions` command returned
a stale/cached mirror showing 2.3.0 / 4.7.3 as "latest" — contradicted by the
fact that `apps/field-guide-api/requirements.txt` already pins and successfully
runs 3.0.1 / 4.13.2 in this exact repo). The in-repo, currently-running pin is
treated as the higher-confidence source over the stale local index.

## Package Legitimacy Audit

> slopcheck was not run in this research session (no `pip install slopcheck`
> attempt made — `apps/launchpad`'s `.venv` uses Python 3.12, and prior-phase
> research (06-RESEARCH.md) already documented a slopcheck installability issue
> on this research host). All three newly-recommended packages are nonetheless
> either (a) already running in production elsewhere in this exact monorepo
> (`Flask-PyMongo`, `pymongo` — copy-pasted pins from `apps/field-guide-api/requirements.txt`,
> itself previously researched and slopcheck-adjacent-verified in the v1.0
> STACK.md) or (b) already installed and executing on disk as a transitive
> dependency (`requests`, pulled in by the already-approved `kubernetes==36.0.2`
> package). Per the provenance rule, all three are tagged `[ASSUMED]` below
> since slopcheck itself did not execute, but the risk profile is very low —
> none of these are novel/unverified package names.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| Flask-PyMongo | PyPI | ~10+ yrs (mongodb-labs/flask-pymongo) | high (exact figure not re-queried this session; already vetted in v1.0 STACK.md) | github.com/mongodb-labs/flask-pymongo | not run — see note | Approved, tag `[ASSUMED]`; already running in `apps/field-guide-api` in this repo |
| pymongo | PyPI | ~15+ yrs, official MongoDB driver | very high (official MongoDB Inc. package) | github.com/mongodb/mongo-python-driver | not run — see note | Approved, tag `[ASSUMED]`; already running in `apps/field-guide-api` in this repo |
| requests | PyPI | ~14+ yrs (psf/requests) | extremely high (one of the most-downloaded PyPI packages) | github.com/psf/requests | not run — see note | Approved, tag `[ASSUMED]`; already installed on disk today as a transitive dep, `pip show` confirms real package metadata (not a slopsquat — matches official PSF project) |

**Packages removed due to slopcheck [SLOP] verdict:** none (slopcheck did not run)
**Packages flagged as suspicious [SUS]:** none

**Provenance note:** Per the package-name provenance rule, all three packages
are tagged `[ASSUMED]` above because slopcheck could not execute this session,
even though `pip show`/in-repo precedent independently confirm real, legitimate
packages already in production use. The planner should still gate the
`requirements.txt` edit behind a lightweight verification step (e.g. `pip show`
the three packages post-install, confirm no unexpected `postinstall`-style
build hooks) rather than a full `checkpoint:human-verify`, since two of the
three are already running unmodified elsewhere in this exact repo and the third
is already installed as a transitive dependency with verified official-source
provenance.

## Architecture Patterns

### System Architecture Diagram

```
Kubernetes kubelet (readinessProbe)          Browser (dashboard page)
        │                                            │
        │ GET /health (probe)                        │ GET / (Phase 6, unchanged)
        ▼                                            ▼
┌───────────────────────────────────────────────────────────────────────┐
│ Flask app (apps/launchpad)                                            │
│                                                                        │
│  health_bp (app/routes/health.py) — EVOLVED IN PLACE                  │
│   └─ GET /health                                                      │
│        - mongo.cx.admin.command("ping") [own Mongo ONLY]              │
│        - 200 {"status":"ok","mongo":"up"}                             │
│        - 503 {"status":"unavailable","mongo":"down"}                  │
│        - NEVER calls field-guide-api, regardless of its state         │
│                                                                        │
│  status_bp (app/routes/status.py) — NEW                               │
│   └─ GET /api/status                                                  │
│        - calls app/status.py::get_platform_status()                   │
│        - returns JSON: api_health, mongo_status, app_version,         │
│          service_count, field_guide_reachable                        │
│        - NEVER 500s — every sub-check is exception-isolated           │
│                                                                        │
│  partials_bp (app/routes/partials.py) — EVOLVED IN PLACE (Phase 6     │
│   stub → Phase 7 real data)                                           │
│   └─ GET /partials/status-cards                                       │
│        - calls the SAME app/status.py::get_platform_status()          │
│        - renders partials/status_cards.html with real per-metric      │
│          cards (replaces Phase 6's static "unknown" stub)             │
│        - still fragment-only; HX-Request contract unchanged            │
│                                                                        │
│  app/status.py — NEW internal helper module (not a blueprint)         │
│   └─ get_platform_status() -> dict                                    │
│        1. mongo_status: mongo.cx.admin.command("ping") [own Mongo]    │
│        2. field_guide_reachable: requests.get(                        │
│             f"{FIELD_GUIDE_BASE_URL}/health", timeout=2)              │
│             wrapped in try/except RequestException -> False on any    │
│             failure, never raises                                     │
│        3. app_version: os.environ.get("APP_VERSION", "dev")           │
│        4. service_count: placeholder (Phase 9 wires real Mongo count) │
│        5. api_health: derived from mongo_status ("ok"/"degraded")     │
│                                                                        │
│  Flask-PyMongo extension (app/extensions.py) — NEW binding            │
│   └─ mongo.init_app(app, serverSelectionTimeoutMS=2000)               │
│        - own MongoDB only (MONGO_URI env var, launchpad's DB)         │
│                                                                        │
│  prometheus-flask-exporter (app/extensions.py) — UNCHANGED, Phase 5   │
│   └─ GET /metrics  (already registered; auto-instruments every        │
│        route added above with zero extra code)                       │
└───────────────────────────────────────────────────────────────────────┘
        │                                            │
        │ MongoDB wire protocol, own DB only         │ HTTP GET, short timeout,
        ▼                                            │ never blocks own health
┌──────────────────────┐                             ▼
│ launchpad-mongodb     │                   ┌──────────────────────────┐
│ (ClusterIP Service,   │                   │ field-guide-api            │
│  Phase 9 manifests —  │                   │ (ClusterIP Service,        │
│  not yet deployed)    │                   │  name: "field-guide-api",  │
└──────────────────────┘                   │  port 80 -> targetPort     │
                                             │  8000; DNS name confirmed  │
                                             │  from live chart source)   │
                                             └──────────────────────────┘
```

Data flow for the primary use case (dashboard status-cards refresh):
1. Browser polls `GET /partials/status-cards` (htmx, established Phase 6 contract, unchanged interval/guard).
2. The route calls `get_platform_status()`, which pings launchpad's own MongoDB (`serverSelectionTimeoutMS=2000`) and separately attempts a 2-second-timeout `requests.get()` to field-guide-api's `/health`.
3. Both sub-checks are independently exception-isolated: a Mongo failure does not prevent the field-guide-api check from running, and vice versa; neither can raise past `get_platform_status()`.
4. The route renders `partials/status_cards.html` with the returned dict, replacing Phase 6's static "unknown" fragment with real per-metric cards — HTML structure and card count may need to grow, but the route path, template name, and `HX-Request` fragment-only contract are unchanged.
5. `GET /api/status` (used for a future JSON-consuming client, and directly asserted by `make smoke-launchpad` in Phase 10 per ROADMAP success criterion) calls the identical `get_platform_status()` and returns it as JSON — guaranteeing the dashboard's visual state and the JSON contract can never silently diverge.
6. `GET /health` (the Kubernetes readinessProbe target) is architecturally separate: it does NOT call `get_platform_status()` and does NOT touch field-guide-api — it performs its own narrow, single-purpose Mongo ping.

### Recommended Project Structure
```
apps/launchpad/app/
├── __init__.py              # MODIFIED — mongo.init_app() added (mirrors field-guide-api)
├── config.py                # MODIFIED — add MONGO_URI / FIELD_GUIDE_BASE_URL / APP_VERSION env keys
├── extensions.py            # MODIFIED — add `mongo: PyMongo = PyMongo()` unbound singleton
├── k8s.py                   # unchanged (Phase 5, Phase 8 consumer)
├── status.py                # NEW — get_platform_status() internal helper, no Blueprint
├── routes/
│   ├── __init__.py          # MODIFIED — export new status_bp
│   ├── health.py            # MODIFIED IN PLACE — real Mongo ping, 200/503 (STAT-03)
│   ├── pages.py             # unchanged (Phase 6)
│   ├── partials.py          # MODIFIED IN PLACE — real status_cards data (STAT-01/02)
│   └── status.py            # NEW — GET /api/status route (STAT-01/02)
├── templates/
│   └── partials/
│       └── status_cards.html   # MODIFIED — real per-metric cards, degraded states
└── static/                  # unchanged (Phase 6)
```
Note the naming overlap: `app/status.py` (plain helper module, no Flask
Blueprint) vs. `app/routes/status.py` (the Blueprint file). This mirrors the
project's existing separation of concerns (`app/k8s.py` as a bare helper vs.
`app/routes/*.py` as Blueprint modules) — do not merge the two into one file.

### Pattern 1: Evolve `/health` in place to check ONLY launchpad's own MongoDB
**What:** Replace the Phase 5 stub body with a `mongo.cx.admin.command("ping")`
call inside try/except, returning 200/503 — an almost verbatim copy of
field-guide-api's already-proven `app/routes/health.py`.
**When to use:** `GET /health` — this is the Kubernetes readinessProbe target
(wired in Phase 8's Deployment manifest, not this phase, but the contract must
be correct now so Phase 8 can wire it without further route changes).
**Example:**
```python
# Source: apps/field-guide-api/app/routes/health.py (existing, proven pattern)
# adapted 1:1 for launchpad's own MongoDB — same shape, same exception
# handling, same status codes. This is the STAT-03 implementation.
from flask import Blueprint, jsonify

from app.extensions import mongo

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health():
    """Return launchpad's own MongoDB readiness status.

    NEVER calls field-guide-api — see /api/status for downstream checks.
    This route name/contract stays stable: Phase 8 wires it as the
    Kubernetes readinessProbe target unchanged.
    """
    try:
        mongo.cx.admin.command("ping")
        return jsonify({"status": "ok", "mongo": "up"}), 200
    except Exception:
        return jsonify({"status": "unavailable", "mongo": "down"}), 503
```
Bare `except Exception` (not a narrower PyMongo exception type) is the
project's own established precedent here — field-guide-api's `/health` uses
the identical broad catch, on the reasoning that ANY failure to ping (network,
auth, timeout, or an unexpected driver exception) should uniformly produce a
503, since a readinessProbe target must never itself throw a 500.

### Pattern 2: Shared status-aggregation helper (`app/status.py`), consumed by both JSON and HTML routes
**What:** A single `get_platform_status()` function that performs all
sub-checks (own Mongo, field-guide-api reachability, version, service count)
and returns a plain `dict`. Both `GET /api/status` (`jsonify(status)`) and
`GET /partials/status-cards` (`render_template(..., status=status)`) call it.
**When to use:** Any time two different response formats need to represent
the same underlying data — prevents the JSON contract and the HTML fragment
from silently drifting apart.
**Example:**
```python
# Source: pattern synthesized from this repo's own field-guide-api /health
# (Mongo ping shape) + the Phase 6 partials.py stub contract + STAT-01/02's
# required JSON field list. Not copied from an external doc — this is the
# project-specific aggregation seam STAT-01/02 requires.
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
`requests.exceptions.RequestException` is the base class for every exception
`requests` can raise on a failed call (`ConnectionError`, `Timeout`,
`HTTPError`, etc.) — catching this one base class, rather than the bare
`Exception`, is `requests`'s own documented pattern for "catch anything this
library might throw" without accidentally swallowing unrelated bugs (e.g. a
`TypeError` from a future refactor of this function).

### Pattern 3: `/api/status` JSON route
**What:** A thin Blueprint route that calls `get_platform_status()` and
returns it as JSON.
**When to use:** `GET /api/status` (STAT-01, STAT-02).
**Example:**
```python
# Source: pattern mirrors the project's existing thin-Blueprint idiom
# (app/routes/health.py, app/routes/pages.py) applied to the new status
# aggregation helper.
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

### Pattern 4: Evolve the status-cards partial in place with real data
**What:** Replace Phase 6's hardcoded `status="unknown", cards=[]` call with
`get_platform_status()`'s real dict; the template gains real per-metric cards
and a degraded-state branch for `field_guide_reachable: False`.
**When to use:** `GET /partials/status-cards` — same route, same fragment-only
contract as Phase 6, now with live data.
**Example:**
```python
# Source: apps/launchpad/app/routes/partials.py (existing Phase 6 stub,
# evolved in place per its own documented forward-looking docstring:
# "Phase 7 replaces the stub data with real /api/status internals — route
# path, template name, and the htmx hx-get target in index.html all stay
# the same.")
from flask import Blueprint, render_template

from app.status import get_platform_status

partials_bp = Blueprint("partials", __name__, url_prefix="/partials")


@partials_bp.route("/status-cards", methods=["GET"])
def status_cards():
    """Real platform status fragment (Phase 7). Still fragment-only by
    design — see the module docstring's standing contract."""
    status = get_platform_status()
    return render_template("partials/status_cards.html", status=status)
```
The template's `{% if status == "unknown" %}` branch from Phase 6 must be
replaced (not merely extended) since `status` is now always a populated dict,
never the literal string `"unknown"` — this is a real template rewrite, not
an additive change. The template needs a per-field degraded-state check, e.g.
`{% if not status.field_guide_reachable %}` renders a distinct "degraded" card
for field-guide-api specifically, while `mongo_status` renders its own
up/down card — UI-03/UI-04's "degrades gracefully, never a 500 or empty page"
requirement extends into this phase's real-data version.

### Pattern 5: HX-Request-aware fragment vs. full-page routing (if the planner chooses to expose a non-htmx path)
**What:** STAT success criterion 4 explicitly requires unit tests confirming
`/partials/status-cards` returns an HTML partial when `HX-Request` is present
and "a full page otherwise." This is a **change of contract from Phase 6**:
Phase 6's Pitfall 3 explicitly forbade adding an `HX-Request`-conditional
branch to this exact route ("never grow an HX-Request-conditional branch that
wraps it in base.html... add a NEW route instead"). Phase 7's success
criterion 4 directly requires that behavior. This is a deliberate, documented
in-place evolution of the Phase-6 contract, not a violation of it — Phase 6's
own docstring anticipated Phase 7 would "replace the stub data ... route path,
template name, and the htmx hx-get target ... stay the same," which is
consistent with adding an `HX-Request` branch as long as the *route path* and
*template name* don't change.
**When to use:** `GET /partials/status-cards` needs to branch on
`request.headers.get("HX-Request") == "true"`.
**Example:**
```python
# Source: this repo's own Phase 6 zero-dependency HX-Request pattern
# (06-RESEARCH.md Pattern 3), extended per Phase 7's STAT success criterion 4.
from flask import Blueprint, render_template, request

from app.status import get_platform_status

partials_bp = Blueprint("partials", __name__, url_prefix="/partials")


@partials_bp.route("/status-cards", methods=["GET"])
def status_cards():
    status = get_platform_status()
    if request.headers.get("HX-Request") == "true":
        return render_template("partials/status_cards.html", status=status)
    # Full-page fallback for direct navigation / no-JS / test harness —
    # wraps the SAME fragment content inside base.html via template
    # inheritance, not a code duplicate.
    return render_template("status_full_page.html", status=status)
```
A minimal `status_full_page.html` that `{% extends "base.html" %}` and
`{% include "partials/status_cards.html" %}` inside its content block avoids
duplicating the card markup — this keeps Pattern 4's single-source-of-truth
property intact even with the new branch.

### Anti-Patterns to Avoid
- **Calling field-guide-api from `/health`:** Explicitly forbidden by the
  locked STATE.md decision and this phase's success criterion 1. `/health`
  must return 200/503 based ONLY on launchpad's own MongoDB.
- **Letting a field-guide-api timeout/connection error propagate as a 500
  from `/api/status` or the partial route:** Both routes must catch
  `requests.exceptions.RequestException` (or broader) around the outbound
  call specifically — never let an unhandled exception escape either route.
- **Using the default 30-second `serverSelectionTimeoutMS`:** Would let a
  Mongo outage hang the single gunicorn worker for 30 seconds per request;
  field-guide-api's own `app/__init__.py` comment explains exactly why this
  matters (readiness must fail by 503, not probe timeout) — reuse the same
  2000ms setdefault pattern verbatim.
- **Hardcoding the field-guide-api base URL as `http://localhost:8080`:** That
  is the host's port-forward address, not the in-cluster DNS name. Inside the
  cluster the correct hostname is the Service name (`field-guide-api`,
  confirmed from the live Helm chart's `_helpers.tpl` — release name
  "field-guide-api" collapses `fullname` to `field-guide-api` per the
  `contains $name .Release.Name` branch), reachable at `http://field-guide-api`
  on port 80 (Service `port: 80` → `targetPort: 8000`). Always source this
  from an env var (`FIELD_GUIDE_BASE_URL`) with that in-cluster DNS name as
  the default, never a literal `localhost` in the route code.
- **Duplicating status-aggregation logic between `/api/status` and the
  partial route:** Violates Pattern 2's single-source-of-truth design; a
  future field added to one and forgotten in the other silently breaks
  STAT-01/02's implied JSON/UI parity.
- **Re-adding the Phase 6 stub's literal string `status="unknown"` as a
  sentinel inside the real `get_platform_status()` dict:** The dict now
  always has real (possibly degraded) values; there is no more "unknown"
  state once this phase lands — "degraded" (e.g. `mongo_status: "down"`,
  `field_guide_reachable: False`) is the correct vocabulary going forward.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| MongoDB connection pooling / app-context binding | Custom `MongoClient` singleton with manual teardown | `Flask-PyMongo` (`mongo.init_app(app, serverSelectionTimeoutMS=2000)`) | Already the project's own established pattern in field-guide-api; reinventing this for launchpad would introduce a second, subtly different Mongo-wiring style in the same monorepo for no benefit |
| HTTP timeout/retry/exception handling for the field-guide-api call | Custom `socket`-level timeout logic or a hand-rolled retry loop | `requests.get(url, timeout=N)` + catching `requests.exceptions.RequestException` | `requests` already normalizes connection errors, timeouts, and HTTP errors under one exception hierarchy; a hand-rolled version would need to separately handle `socket.timeout`, `ConnectionRefusedError`, DNS failures, etc. — already solved, and the library is already on disk |
| Prometheus metric registration/exposition format | Custom `/metrics` route emitting hand-formatted text | `prometheus-flask-exporter` (already wired) | Already fully working since Phase 5 — zero-config auto-instruments every route including the two new ones this phase adds; hand-rolling this would also risk metric-name/format drift from field-guide-api's `/metrics`, breaking the requested parity |
| JSON/HTML dual-representation of the same status data | Two independent code paths | Single `get_platform_status()` helper (Pattern 2) | Guarantees `/api/status` and the dashboard cards can never silently diverge; this is the single most important "don't hand-roll twice" decision in this phase |

**Key insight:** Every piece of new infrastructure in this phase (Mongo
wiring, HTTP client, Prometheus exposition) already has a proven,
in-repo-precedent solution. The actual engineering risk in this phase is not
"which library to pick" but "correctly isolating the two failure domains"
(own-Mongo vs. field-guide-api-reachability) so a downstream outage can never
turn into a readinessProbe failure or an unhandled 500.

## Common Pitfalls

### Pitfall 1: `/health` accidentally becomes coupled to field-guide-api
**What goes wrong:** A future edit (or a well-intentioned "let's also check
field-guide-api in health for completeness") adds a call to field-guide-api
inside `/health`. Now a field-guide-api outage causes Kubernetes to mark the
launchpad pod NotReady and pull it from Service Endpoints — even though
launchpad itself is perfectly healthy and could still serve its own dashboard.
**Why it happens:** It "feels" more thorough to check everything in one
route; the distinction between a readinessProbe target and a status dashboard
is easy to blur once both routes exist side by side in the same file.
**How to avoid:** Keep `/health` and `get_platform_status()` structurally
separate — `/health` must import ONLY `app.extensions.mongo`, never
`app.status` or `requests`. A grep-able rule for code review: `health.py`
should never contain the substring `requests` or `FIELD_GUIDE`.
**Warning signs:** `health.py`'s diff starts importing `requests` or
referencing field-guide-api in any form.

### Pitfall 2: `requests.get()` with no timeout hangs the single gunicorn worker
**What goes wrong:** `requests.get(url)` with no `timeout=` argument blocks
indefinitely if field-guide-api's Service exists but the pod behind it is
unresponsive (not a clean connection-refused, which fails fast) — this is a
classic partial-outage failure mode. With only 1 gunicorn worker (project's
locked convention, per CLAUDE.md's `--workers 1` rationale), this single
hanging request blocks the entire pod, including its own `/health` and
`/metrics` traffic on the SAME worker process for the request's duration
(gunicorn's threaded worker mitigates but does not eliminate this under load).
**Why it happens:** `requests`'s default timeout is `None` (no timeout) —
this is easy to miss since the library "works fine" in the common case where
field-guide-api responds instantly.
**How to avoid:** Always pass `timeout=2` (or the chosen constant) explicitly
on every `requests.get()` call to field-guide-api; never rely on the default.
**Warning signs:** A `requests.get()` call anywhere in `app/status.py` without
a `timeout=` keyword argument.

### Pitfall 3: Flask-PyMongo `mongo.init_app()` called with a missing/malformed `MONGO_URI` crashes app startup, not just `/health`
**What goes wrong:** Unlike the field-guide-api pattern (where a Kubernetes
Secret always injects a well-formed `MONGO_URI`), launchpad's local dev
`.env.example` currently has NO `MONGO_URI` key at all (confirmed: current
`.env.example` only documents `FLASK_DEBUG`). If `mongo.init_app()` is called
with an empty/unset `MONGO_URI`, PyMongo may raise at `init_app()` time
(app-factory construction) rather than at first query time, which would break
`create_app()` for every test and every local `flask run` unless a default is
supplied.
**Why it happens:** Flask-PyMongo's `init_app()` eagerly parses the URI;
field-guide-api's chart always supplies a valid Secret-backed URI, so this
failure mode was never exercised there.
**How to avoid:** Supply a sane local-dev default in `app/config.py` — e.g.
`MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/launchpad")`
— so `create_app()` never crashes even with no `.env` present; the `/health`
route's own try/except already handles the case where that default URI has no
listener (connection refused → 503, not a crash). Add `MONGO_URI=` to
`.env.example` with a comment mirroring field-guide-api's discipline. This
also directly affects test isolation: `conftest.py`'s `app` fixture calls
`create_app({"TESTING": True})` with no override today — the planner must
decide whether tests inject a mongomock-backed URI/client or monkeypatch
`mongo.cx` directly (see Open Questions).
**Warning signs:** `pytest` fails at collection/fixture-setup time (not inside
a specific test) with a PyMongo `ConfigurationError` or `InvalidURI`.

### Pitfall 4: `/api/status`'s `service_count` field is easy to over-scope into Phase 9's territory
**What goes wrong:** STAT-01 asks for "registered-service count." Phase 9
(Service Catalog) is the phase that actually creates the `services` MongoDB
collection and CRUD routes — that collection does not exist yet in Phase 7.
Implementing a real `mongo.db.services.count_documents({})` call in this phase
would either (a) silently return `0` forever until Phase 9 (harmless but
slightly misleading if not documented) or (b) tempt scope creep into
building collection schema/seed data that belongs to Phase 9.
**Why it happens:** The requirement text sounds like it wants a "real" count,
but the roadmap's own phase boundary (STAT-01..04 in Phase 7; CAT-01..05 in
Phase 9) makes clear the catalog itself is out of scope here.
**How to avoid:** Implement `service_count` as `mongo.db.services.count_documents({})`
against launchpad's own (now-connected) MongoDB — this is NOT hardcoded (satisfies
"not hardcoded values" framing from UI-03's sibling requirement) and will
correctly return `0` today and the real count once Phase 9 populates the
collection, with zero code change needed in Phase 9. Do not build any
service-registration logic in this phase.
**Warning signs:** A plan task that creates `services` collection indexes,
seed documents, or a registration route — that is Phase 9 scope, not Phase 7.

### Pitfall 5: 100%-coverage gate breaks because the field-guide-api HTTP call and Mongo ping both need mocked failure-path tests
**What goes wrong:** `pytest.ini`'s `--cov-fail-under=100` (unchanged this
phase) means every branch in `get_platform_status()` — Mongo up, Mongo down,
field-guide-api reachable, field-guide-api unreachable (both a timeout AND a
connection-refused/DNS-failure case, if both are handled via the same except
clause they only need ONE test to cover the branch, but a naive
implementation with two separate except clauses would need two tests) — must
be exercised by at least one unit test, or the phase's own success criterion
5 ("`make test-launchpad` continues to pass at 100% coverage with all new
routes exercised by mocked-requests unit tests") fails outright.
**Why it happens:** Cross-service HTTP calls and DB pings are exactly the
kind of code that's easy to write correctly but under-test, since manually
triggering "Mongo is down" or "field-guide-api times out" requires mocking,
not just hitting a route.
**How to avoid:** `conftest.py` already has a `mock_requests_get` fixture
placeholder built specifically for this phase (docstring: "Placeholder
pattern for mocking `requests.get` ahead of Phase 7's field-guide-api
reachability check (STAT-02)") — extend it (or add sibling fixtures) to cover
both the success case (`status_code=200`) and failure case
(`monkeypatch.setattr(requests, "get", lambda *a, **kw: (_ for _ in ()).throw(requests.exceptions.ConnectionError))`
or similar) explicitly. For Mongo, the planner must decide between mongomock
and a monkeypatched `mongo.cx` (see Open Questions) — either way, both the
ping-succeeds and ping-raises branches need explicit test coverage.
**Warning signs:** `pytest --cov-report=term-missing` shows uncovered lines
inside the `except` blocks of `app/status.py` or `app/routes/health.py`.

## Code Examples

### `app/extensions.py` — adding the Mongo singleton alongside the existing metrics singleton
```python
# Source: apps/field-guide-api/app/extensions.py (existing, proven), merged
# with apps/launchpad/app/extensions.py's existing metrics singleton (Phase 5)
from flask_pymongo import PyMongo
from prometheus_flask_exporter import PrometheusMetrics

# Unbound PyMongo singleton — bound to app in create_app() via mongo.init_app(app).
# Own MongoDB only (launchpad's DB) — never used to reach field-guide-api's DB.
mongo: PyMongo = PyMongo()

# Unbound PrometheusMetrics singleton — unchanged from Phase 5.
metrics: PrometheusMetrics = PrometheusMetrics.for_app_factory()
```

### `app/__init__.py` — the Mongo-binding addition inside `create_app()`
```python
# Source: apps/field-guide-api/app/__init__.py lines 43-51 (existing, proven
# 2000ms-timeout pattern), applied verbatim to launchpad's own Mongo.
app.config.setdefault("MONGO_SERVER_SELECTION_TIMEOUT_MS", 2000)
mongo.init_app(
    app,
    serverSelectionTimeoutMS=app.config["MONGO_SERVER_SELECTION_TIMEOUT_MS"],
)
metrics.init_app(app)  # unchanged from Phase 5
```

### `app/config.py` — new env keys this phase introduces
```python
# Source: pattern extends apps/launchpad/app/config.py's existing
# _env_flag/Config class shape (Phase 5); new keys per Pitfall 3 and the
# in-cluster DNS name confirmed from charts/field-guide-api/templates/_helpers.tpl
class Config:
    DEBUG: bool = _env_flag("FLASK_DEBUG")
    TESTING: bool = False

    # Own MongoDB — local-dev default matches a bare `mongod` on localhost;
    # Phase 8/9's Helm chart Secret overrides this in-cluster.
    MONGO_URI: str = os.environ.get("MONGO_URI", "mongodb://localhost:27017/launchpad")

    # In-cluster DNS name for field-guide-api's ClusterIP Service — confirmed
    # from the live chart: release name "field-guide-api" collapses fullname
    # to "field-guide-api", Service port 80. Override via env for local dev
    # (e.g. http://localhost:8080 when both apps are port-forwarded locally).
    FIELD_GUIDE_BASE_URL: str = os.environ.get("FIELD_GUIDE_BASE_URL", "http://field-guide-api")

    # Surfaced in /api/status; no packaging metadata (no pyproject.toml) exists
    # in this monorepo yet, so this is env-var-sourced with a "dev" fallback —
    # see Open Questions for the Helm-chart-injection question (Phase 8 concern).
    APP_VERSION: str = os.environ.get("APP_VERSION", "dev")
```

### Mocking pattern for `get_platform_status()`'s two external calls (test file, illustrative)
```python
# Source: extends apps/launchpad/tests/conftest.py's existing
# mock_requests_get fixture placeholder (Phase 5, built exactly for this
# phase) + this repo's own monkeypatch-and-auto-restore discipline
# (documented in conftest.py's module docstring).
import requests


def test_status_mongo_up_field_guide_reachable(monkeypatch, app):
    import app.extensions as ext

    monkeypatch.setattr(ext.mongo, "cx", _FakeMongoClient(ping_ok=True))
    fake_resp = type("R", (), {"status_code": 200})()
    monkeypatch.setattr(requests, "get", lambda *a, **kw: fake_resp)

    with app.app_context():
        from app.status import get_platform_status
        result = get_platform_status()

    assert result["mongo_status"] == "up"
    assert result["field_guide_reachable"] is True


def test_status_field_guide_unreachable_degrades_gracefully(monkeypatch, app):
    import app.extensions as ext

    monkeypatch.setattr(ext.mongo, "cx", _FakeMongoClient(ping_ok=True))

    def _raise(*a, **kw):
        raise requests.exceptions.ConnectionError("connection refused")

    monkeypatch.setattr(requests, "get", _raise)

    with app.app_context():
        from app.status import get_platform_status
        result = get_platform_status()

    assert result["field_guide_reachable"] is False  # never raises, never 500
```
`_FakeMongoClient` is illustrative — the planner must decide the exact
Mongo-mocking mechanism (mongomock vs. a hand-rolled fake `.admin.command()`)
per Open Question 1 below before writing real test code.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Phase 5 `/health` — plain `{"status": "ok"}`, no Mongo check | Phase 7 `/health` — real `mongo.cx.admin.command("ping")`, 200/503 | This phase (STAT-03) | The route's return shape changes; any existing manual `curl localhost:8081/health` expectation of always-200 must be updated in developer muscle memory / smoke scripts once this lands |
| Phase 6 `/partials/status-cards` — static `status="unknown"` stub | Phase 7 — real `get_platform_status()` dict, degraded per-field | This phase (STAT-01/02) | Template rewrite required (Pattern 4) — Phase 6's `{% if status == "unknown" %}` branch structure does not survive unchanged |
| No outbound HTTP client used anywhere in launchpad | `requests` becomes a direct (not just transitive) dependency | This phase | First cross-service network call in the launchpad app; establishes the timeout/exception-isolation pattern that any future cross-service call in this monorepo should follow |

**Deprecated/outdated:** None — this phase is a pure additive evolution of
already-current, already-installed libraries (Flask-PyMongo 3.0.1, pymongo
4.13.2, prometheus-flask-exporter 0.23.2 all already locked/proven in this
exact repo; `requests` 2.34.2 already installed and current per PyPI).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `requests==2.34.2` and `Flask-PyMongo==3.0.1`/`pymongo==4.13.2` package identities, though `pip show`/in-repo-verified, are tagged `[ASSUMED]` because slopcheck did not execute this session | Package Legitimacy Audit | Low — Flask-PyMongo/pymongo are copy-pasted pins from an already-running sibling app in this exact repo; requests is already installed on disk today via an already-approved transitive dependency chain. Risk is near-zero. |
| A2 | `FIELD_GUIDE_BASE_URL` default of `http://field-guide-api` (port 80, no explicit port in the URL) correctly resolves in-cluster once Phase 8/9 actually deploy launchpad into the same namespace as field-guide-api | Anti-Patterns, Code Examples (config.py) | Medium — this is inferred from reading `charts/field-guide-api/templates/service.yaml`/`_helpers.tpl` (Service `port: 80`, name resolves to literal `field-guide-api` when release name = "field-guide-api", per the Makefile's `RELEASE ?= field-guide-api`), but launchpad's OWN chart does not exist yet (Phase 8) so same-namespace deployment is not yet verified end-to-end. If Phase 8 deploys launchpad into a different namespace, this default must become a fully-qualified `field-guide-api.<namespace>.svc.cluster.local` instead — low implementation cost to fix, but worth flagging now before Phase 8 locks the chart. |
| A3 | 2-second timeout for the field-guide-api reachability call is an appropriate value (not officially mandated by any requirement — the "Recommend a specific timeout value" instruction in the phase brief has no external source, this is a project-consistency inference from the existing 2000ms Mongo `serverSelectionTimeoutMS` pattern) | Alternatives Considered, Pattern 2 | Low — even if 2s later proves too aggressive or too lax under real load, it is a one-line constant change (`FIELD_GUIDE_TIMEOUT_SECONDS`), not an architectural decision |
| A4 | No packaging metadata (`pyproject.toml`, `setup.py`, `__version__`) exists anywhere in this monorepo, so `APP_VERSION` must be env-var-sourced rather than read from package metadata | Code Examples (config.py) | Low-medium — confirmed by direct file-listing of both `apps/launchpad/` and `apps/field-guide-api/` (grep for VERSION/`__version__` across both app trees returned zero hits in Python/YAML/Dockerfile sources); if a future phase introduces packaging metadata, `APP_VERSION`'s source should be revisited, but env-var-with-fallback is a safe default that requires zero migration when that happens |

**If this table is empty:** N/A — see rows above.

## Open Questions

1. **How should launchpad's tests mock the own-MongoDB ping — mongomock, or a monkeypatched `mongo.cx`?**
   - What we know: `mongomock` is not currently installed in `apps/launchpad/requirements-dev.txt` (confirmed by reading the file — only `pytest`, `pytest-flask`, `pytest-cov` are listed). STATE.md's Blockers/Concerns section flags that Phase 9 already anticipates using mongomock ("mongomock cannot verify TTL expiry timing — document in conftest.py"), implying the project intends to adopt mongomock at some point, but does not confirm Phase 7 is where it's introduced.
   - What's unclear: Whether Phase 7 should introduce `mongomock` now (so Phase 9 inherits an established pattern) or use a simpler `monkeypatch.setattr(mongo, "cx", <fake object>)` approach scoped to just the `admin.command("ping")` call this phase needs, deferring mongomock's heavier CRUD-simulation capabilities to Phase 9 where they're actually exercised (`mongo.db.services.find()`, etc.).
   - Recommendation: For Phase 7's narrow need (mock a single `admin.command("ping")` call succeeding or raising), a lightweight monkeypatched fake object is sufficient and avoids adding a new dev dependency one phase early. If the planner prefers front-loading mongomock now for Phase 9's benefit, that's a reasonable alternative — either choice satisfies this phase's 100%-coverage requirement. Flag this as a discuss-phase-worthy decision if not already resolved by CONTEXT.md.

2. **Should `/partials/status-cards` grow the `HX-Request` full-page branch described in Pattern 5, or does "full page otherwise" in success criterion 4 mean something narrower (e.g. just asserting the fragment lacks `<html>` when `HX-Request` is absent vs. present, without necessarily building a full separate page)?**
   - What we know: The phase's success criterion 4 states: "The status card htmx fragment route returns an HTML partial when the `HX-Request` header is present and a full page otherwise; unit tests confirm this behavior." This is unambiguous about the desired *behavior* but does not specify whether "full page" means a complete `base.html`-wrapped page or simply a non-fragment response.
   - What's unclear: Whether a minimal `status_full_page.html` (Pattern 5) is the right scope, or whether the planner should treat this as testing the existing Phase 6-established convention more thoroughly (i.e., the Phase 6 stub route currently has NO `HX-Request` branch at all — it always returns the bare fragment regardless of the header — so satisfying this criterion requires new branching logic regardless of how minimal the "full page" response is).
   - Recommendation: Implement Pattern 5's minimal `status_full_page.html` (extends `base.html`, includes the same fragment content) — this is the smallest change that unambiguously satisfies "a full page otherwise" while reusing Pattern 4's fragment content via `{% include %}`, avoiding markup duplication.

3. **Does `GET /api/status` need htmx-fragment awareness at all, or is it purely a JSON endpoint regardless of headers?**
   - What we know: STAT-01's requirement text says `GET /api/status` "returns real platform status" as JSON — no mention of HTML/htmx behavior for this specific route. The `HX-Request` full-page/partial distinction in success criterion 4 is explicitly scoped to "the status card htmx fragment route" (i.e., `/partials/status-cards`), not `/api/status`.
   - What's unclear: Nothing significant — this is a low-risk clarification, included for completeness so the planner doesn't accidentally conflate the two routes' contracts.
   - Recommendation: `/api/status` should be JSON-only, always, regardless of any request header — Pattern 3 above reflects this. Do not add `HX-Request` branching to `/api/status`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Flask-PyMongo / pymongo (pip install) | STAT-01, STAT-03 (own MongoDB wiring) | ✗ (not yet installed in launchpad's `.venv`, confirmed via `pip show`) | — (will be pinned 3.0.1 / 4.13.2) | None needed — `pip install -r requirements.txt` after the requirements.txt edit is a standard, low-risk step; both packages already proven installable in this repo's field-guide-api venv |
| requests (already installed, transitive) | STAT-02 (field-guide-api reachability) | ✓ | 2.34.2 (verified live via `pip show`) | — |
| A live MongoDB instance for launchpad (own DB) | `/health` returning 200 in a real deployment | ✗ locally (no launchpad Mongo manifests exist yet — DEP-03/Phase 9 territory) | — | `/health` returning 503 locally (no Mongo running) is the CORRECT, expected behavior per this phase's own success criterion 1 — not a blocker. Unit tests mock the Mongo call entirely (see Open Question 1), so `make test-launchpad` does not require a live Mongo. |
| A live field-guide-api instance reachable from launchpad | `/api/status`'s `field_guide_reachable: true` case in a real deployment | ✗ locally outside a running kind cluster (both apps' Helm charts for launchpad don't exist until Phase 8) | — | `field_guide_reachable: false` (degraded) is the CORRECT, expected local-dev behavior per STAT-02 — not a blocker. Unit tests mock `requests.get` entirely. |
| curl or Flask test client | Manual verification of `/health`, `/api/status`, `/metrics` during phase execution | ✓ (Git Bash on Windows host per CLAUDE.md; Flask test client always available via pytest) | — | — |

**Missing dependencies with no fallback:**
- None — every "missing" item above (live Mongo, live field-guide-api) is an
  expected-and-correctly-handled degraded state for local/unit-test execution
  in this phase, not a blocker to completing the phase's own success criteria.

**Missing dependencies with fallback:**
- Flask-PyMongo/pymongo — standard `pip install` after the requirements.txt edit (no fallback needed, low risk).

## Validation Architecture

> Skipped — `.planning/config.json` sets `workflow.nyquist_validation: false` explicitly.

## Security Domain

> `security_enforcement` is not set to `false` in `.planning/config.json` (key absent) — treated as enabled per default.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | Locked out-of-scope per REQUIREMENTS.md Out of Scope table ("Authentication / multi-user — Local single-user platform"); no auth introduced by this phase's routes |
| V3 Session Management | No | No sessions/cookies introduced; all new routes (`/health`, `/api/status`, `/partials/status-cards`) are stateless GET-only |
| V4 Access Control | No | Single-user local platform, no access-control boundaries added this phase |
| V5 Input Validation | No user input surface | All three routes (`/health`, `/api/status`, `/partials/status-cards`) are GET-only with zero query params or request bodies consumed — no validation surface exists in this phase; becomes relevant starting Phase 9 (CAT-03 form validation) |
| V6 Cryptography | No | No secrets, tokens, or crypto operations added; `MONGO_URI` follows the existing project pattern of env-var/Kubernetes-Secret injection, never hardcoded (mirrors field-guide-api's `secret.yaml` pattern, to be wired in Phase 8/9's launchpad chart) |
| V7 Error Handling and Logging | Yes | Every new failure path (`/health`'s Mongo ping, `get_platform_status()`'s Mongo ping and field-guide-api call) is caught and converted to a structured response (503 JSON, or a degraded field value) — never an unhandled stack trace leaked to the client. gunicorn's `--access-logfile -`/`--error-logfile -` (Dockerfile, unchanged) route these to stdout for `kubectl logs`. |
| V13 API and Web Service | Yes | `/api/status` is a read-only JSON GET endpoint with no state mutation; response content is limited to platform status fields only — no internal stack traces, file paths, or credentials are ever included in the JSON body (the bare `except Exception` blocks intentionally discard the exception detail, returning only a fixed-shape degraded value) |

### Known Threat Patterns for Flask + cross-service HTTP + MongoDB

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Server-Side Request Forgery (SSRF) via a user-controlled target URL for the "reachability" check | Tampering / Information Disclosure | Not applicable this phase — `FIELD_GUIDE_BASE_URL` is sourced exclusively from server-side environment configuration (env var / future Helm ConfigMap), never from request input; no route in this phase accepts a URL parameter from the client. Document this explicitly so a future "let users configure which service to check" feature does not accidentally reintroduce SSRF risk without review. |
| Denial of Service via unbounded outbound call blocking the sole worker | Denial of Service | Mitigated by mandatory `timeout=2` on every `requests.get()` call (Pitfall 2) and `serverSelectionTimeoutMS=2000` on the Mongo client (Pitfall 3-adjacent) — both bound worst-case latency for `/api/status` and the status-cards fragment to a few seconds even under total downstream failure |
| Information disclosure via verbose error messages in `/api/status` | Information Disclosure | `get_platform_status()`'s except blocks discard exception details and return only fixed-shape degraded values (`"down"`, `False`) — never `str(exception)` — preventing internal hostnames, stack traces, or connection-string fragments from leaking into the public JSON response |
| NoSQL injection via unsanitized query construction | Tampering | Not applicable this phase — the only Mongo operation introduced is `admin.command("ping")` (a fixed, parameterless command) and (per Pitfall 4) a fixed `count_documents({})` call with an empty filter; no user input reaches any Mongo query in this phase. Document this precedent (mirrors field-guide-api's existing "all queries are passed as Python dicts, no string interpolation" T-02-03 note) for when Phase 9 introduces real user-input-driven queries. |

## Sources

### Primary (HIGH confidence)
- Direct repository inspection — `apps/field-guide-api/app/routes/health.py`, `app/extensions.py`, `app/__init__.py` (the proven Mongo-ping/timeout pattern this phase's `/health` and `app/status.py` directly reuse)
- Direct repository inspection — `apps/launchpad/app/{__init__,config,extensions,k8s}.py`, `app/routes/{health,partials,pages}.py`, `tests/conftest.py` (current Phase 5/6 state, confirms exact extension points and the pre-built `mock_requests_get` fixture placeholder)
- Direct repository inspection — `charts/field-guide-api/templates/{service.yaml,_helpers.tpl,deployment.yaml,secret.yaml}` (confirms in-cluster DNS name resolution mechanics and the MONGO_URI/timeout wiring precedent Phase 8/9 will need to mirror for launchpad)
- Live command execution this session — `pip show requests` (2.34.2, installed), `pip show flask-pymongo pymongo` (not installed — confirmed net-new), `pip show prometheus-flask-exporter` (0.23.2, installed and working), `python -c "...create_app...get('/metrics')..."` (confirmed 200 + valid Prometheus text today)
- `.planning/config.json` — confirms `nyquist_validation: false` (Validation Architecture section correctly skipped) and no `security_enforcement: false` override (Security Domain section correctly included)

### Secondary (MEDIUM confidence)
- WebSearch, requests PyPI page — confirms 2.34.2 as the current release (May 14, 2026), cross-verified against the live `pip show` output in this exact venv
- WebSearch, prometheus-flask-exporter GitHub README/PyPI — confirms default metric names (`flask_http_request_duration_seconds`, `flask_http_request_total`, `flask_http_request_exceptions_total`) for the parity-verification test this phase should write
- WebSearch, PyMongo/Flask-PyMongo docs (pymongo.readthedocs.io, flask-pymongo PyPI) — confirms `admin.command('ping')` as the standard low-cost readiness check and `serverSelectionTimeoutMS`'s role/default (30000ms) — consistent with and explaining why field-guide-api's existing 2000ms override matters

### Tertiary (LOW confidence)
- `pip index versions Flask-PyMongo`/`pymongo` local sandboxed output (returned stale-looking results — 2.3.0/4.7.3 — contradicted by this repo's own working `requirements.txt` pins of 3.0.1/4.13.2; treated as unreliable and NOT used as the version source of truth in this research, in favor of the in-repo precedent)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every recommended package is either already running in this exact monorepo (Flask-PyMongo, pymongo, prometheus-flask-exporter) or already installed and version-confirmed live via `pip show` (requests)
- Architecture: HIGH — the `/health` vs `/api/status` separation is a pre-existing locked STATE.md decision, not a new judgment call; the shared `get_platform_status()` helper pattern is a direct, low-risk DRY application over two already-scoped consumer routes
- Pitfalls: HIGH — Pitfalls 1-3 are directly grounded in live file inspection (existing `.env.example`, existing STATE.md locked decision, existing field-guide-api timeout precedent); Pitfalls 4-5 are inferred from the phase's own requirement text and the project's own `--cov-fail-under=100` gate, both directly verified in this session

**Research date:** 2026-07-11
**Valid until:** 30 days (all core libraries are stable, low-churn, and largely already proven in this exact repo; re-verify `requests` version only if planning is delayed past mid-August 2026)
