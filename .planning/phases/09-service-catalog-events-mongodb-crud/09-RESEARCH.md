# Phase 9: Service Catalog + Events / MongoDB CRUD - Research

**Researched:** 2026-07-12
**Domain:** Flask-WTF forms/CSRF, PyMongo TTL indexes, mongomock test-harness limitations, Helm MongoDB manifest mirroring
**Confidence:** HIGH

## Summary

Phase 9 adds one new runtime dependency (Flask-WTF, pulling in WTForms as a transitive
dependency) and two new MongoDB collections (`services`, `events`) to an already-established
app-factory / extensions-singleton / never-raise-helper architecture. Nothing here requires a
new architectural pattern — it is a straight extension of the Phase 5-8 conventions already in
the codebase (`app/extensions.py` singleton wiring, `app/status.py`-style bare helper modules,
`app/routes/partials.py`'s HX-Request fragment/full-page branching, the module-attribute import
discipline from Phase 8's plan-check BLOCKER 3).

The two areas with real technical risk are (1) TTL index semantics in mongomock, which **silently
accepts** `expireAfterSeconds` without ever purging documents (confirmed by reading the installed
mongomock 4.3.0 source directly — no `NotImplementedError`, no background thread), meaning the
test suite can prove the index *exists* but never that expiry *works* — live smoke verification is
mandatory and must be documented in `conftest.py`, exactly as D-10 anticipated; and (2) the
Flask-WTF CSRF story requires two distinct test postures (CSRF-disabled for the majority of route
tests, CSRF-enabled for the one test proving SC #2's "CSRF protection intact" claim) that Flask-WTF
does not provide out of the box — the CSRF-enabled test must extract the token from a rendered
form and round-trip it through a second request.

The Mongo manifest work (DEP-03) is a pure mechanical mirror of
`charts/field-guide-api/templates/mongodb/` with a `launchpad.mongodb.*` helper prefix substituted
for `field-guide-api.mongodb.*` — every file, field, and probe strategy is a copy with names
swapped and database name changed to `launchpad`.

**Primary recommendation:** Pin `Flask-WTF==1.3.0` (pulls `WTForms>=3.1.0`, resolves to 3.2.2).
Wire `CSRFProtect` in `extensions.py` alongside the existing `mongo`/`metrics` singletons. Build
`app/catalog.py` and `app/events.py` as bare never-raise helper modules mirroring `status.py`'s
shape, imported via `from app import events` (module-attribute, not `from app.events import
record_event`) wherever tests need to monkeypatch. Create both indexes (unique on
`services.name`, TTL on `events.ts`) once, idempotently, at `create_app()` extension-init time —
never on first request — using a config-driven TTL value so smoke tests can override it to a short
window.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Service registration form (CSRF, validation) | API / Backend (Flask route + WTForms) | Browser (native HTML5 `type="url"` hint only, no JS validation) | Server-side validation is the enforcement boundary per CAT-03; browser input types are UX hints only, never trusted |
| Service catalog persistence | Database / Storage (MongoDB `services` collection) | API / Backend (never-raise repo helper) | Flask-PyMongo singleton already owns all DB access; catalog is just a second collection off the same client |
| Uniqueness enforcement (`name` slug) | Database / Storage (unique index) | API / Backend (pre-check for UX, index for correctness) | MongoDB unique index is the source of truth; app-level pre-check only improves error UX, never replaces the index (race-safe design) |
| Events feed persistence + TTL bounding | Database / Storage (MongoDB `events` collection + TTL index) | API / Backend (event-writer helper) | TTL expiry is a database-native background mechanism; the app only ever writes, never deletes, event documents |
| Events feed rendering (htmx polling) | API / Backend (Flask route renders partial) | Browser (htmx swap, visibility-guarded poll) | Established Phase 6-8 pattern — `/partials/*` routes own the fragment/full-page branch; browser only owns the poll trigger |
| Deregister confirmation | API / Backend (server-rendered confirm page + POST) | Browser (zero JS, per D-08) | Explicit locked decision — no client-side `confirm()`, so this capability lives entirely server-side |
| Mongo manifests (Deployment/PVC/Secret/Service) | Database / Storage (Kubernetes manifests) | — | Direct mirror of the field-guide-api chart's Mongo tier; no new tier introduced |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Flask-WTF | 1.3.0 | `CSRFProtect` extension + `FlaskForm` base class | `[VERIFIED: PyPI registry]` Confirmed via `pypi.org/pypi/Flask-WTF/json` (authoritative registry, not search-only) — version 1.3.0, released 2026-04-23, published under `pallets-eco` org (same maintainers as Flask itself), 52 total releases dating to 2010. Requires `flask, itsdangerous, wtforms` per `requires_dist`. |
| WTForms | 3.2.2 (transitive via Flask-WTF) | Field validators, error collection, `hidden_tag()` CSRF rendering | `[VERIFIED: PyPI registry]` Confirmed via `pypi.org/pypi/WTForms/json` — `pallets-eco` org, 34 releases, `requires_python >=3.10` (compatible with the locked Python 3.11). Not pinned directly in `requirements.txt` — let Flask-WTF's dependency resolution select it (pin the range only if a specific WTForms bug must be avoided; none found in this research). |

### Supporting

No new supporting libraries. `pymongo==4.13.2` (already pinned) provides `create_index()` and
`pymongo.errors.DuplicateKeyError` used directly — no additional package needed for TTL or unique
indexes.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Flask-WTF `FlaskForm` | Bare WTForms `Form` + manual CSRF (Flask's own `session`-based token) | D-04 explicitly locks Flask-WTF — "No hand-rolled CSRF." Bare WTForms requires reimplementing token generation/validation that Flask-WTF already provides via `CSRFProtect`; strictly more code for zero benefit at this scale. |
| `insert_one()` + catch `DuplicateKeyError` | `update_one(..., upsert=True)` | Upsert is for idempotent "insert-or-replace" semantics; registration is a genuine create operation where a duplicate must produce a user-facing validation error, not a silent overwrite — `insert_one` + exception handling is the correct fit here. |
| Plain `Deployment` for events/services Mongo (same instance as Phase 8's readinessProbe target) | Two separate MongoDB Deployments (one per collection concern) | Out of scope — DEP-03 explicitly specifies ONE in-cluster MongoDB (`database name launchpad`) holding both `services` and `events` collections; a second Mongo instance would be unwarranted operational overhead for a single-database app. |

**Installation:**
```bash
pip install Flask-WTF==1.3.0
```
Add to `apps/launchpad/requirements.txt`:
```
Flask-WTF==1.3.0
```
(WTForms resolves transitively; do not pin it separately unless a future issue requires narrowing the range.)

**Version verification:** Verified directly against the PyPI JSON API (`https://pypi.org/pypi/Flask-WTF/json` and `.../WTForms/json`), which is the authoritative source for exact version + publish date — not WebSearch alone. `pip index versions` on this dev machine returned a stale cached index (1.1.1) and must NOT be trusted as the source of truth for pinning; the PyPI JSON API result (1.3.0) is authoritative and matches CLAUDE.md's convention of citing PyPI directly.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| Flask-WTF | PyPI | ~16 years (first release 0.1, 2010) | Not queried (no API access to download stats in this session) | github.com/pallets-eco/flask-wtf | not available in this environment | Approved — `[ASSUMED]` per graceful degradation, see below |
| WTForms | PyPI | ~19 years (first release 0.4, ~2007) | Not queried | github.com/pallets-eco/wtforms | not available in this environment | Approved — `[ASSUMED]` per graceful degradation, see below |

`slopcheck` could not be installed in this research session (`pip install slopcheck` returned "No
matching distribution found" — no compatible wheel available for this environment's Python/platform
combination). Per the Package Legitimacy Gate protocol's graceful-degradation clause, both packages
are therefore tagged `[ASSUMED]` for the purposes of the planner's checkpoint gating, **despite**
strong independent legitimacy evidence gathered manually:

- Both published under the `pallets-eco` GitHub organization — the official continuation of the
  Pallets project (Flask, Jinja2, Werkzeug, Click's ecosystem), not an individual/anonymous
  publisher.
- Both have decade-plus release histories (52 and 34 releases respectively) — the opposite profile
  of a slopsquatted/hallucinated package (which would be days-to-weeks old with 0-1 releases).
- Both are already implicitly trusted transitively (Flask itself is `pallets`; `pallets-eco` is the
  extension-maintainer org Flask's own docs link to for WTForms integration — see the Flask docs
  "Form Validation with WTForms" page fetched during this research, which names Flask-WTF as the
  recommended extension).

**Packages removed due to slopcheck `[SLOP]` verdict:** none
**Packages flagged as suspicious `[SUS]`:** none — but both remain `[ASSUMED]` per the graceful-
degradation rule since the automated slopcheck tool itself did not run. The planner should insert
a lightweight `checkpoint:human-verify` (or fold into the existing T-08-02-style pattern already
used for Secret placeholders) before `pip install Flask-WTF==1.3.0` is added to `requirements.txt`,
even though the manual evidence above is strong.

## Architecture Patterns

### System Architecture Diagram

```
Browser
  │
  ├─ GET /catalog ─────────────────► pages.catalog()
  │                                    └─ app.catalog.list_services() [never-raise]
  │                                         └─ mongo.db.services.find().sort(registered_at, -1)
  │                                    ◄─ renders catalog.html (table or empty-state CTA)
  │
  ├─ GET /catalog/new ──────────────► pages.catalog_new()
  │                                    └─ renders onboard_form.html with fresh CSRFProtect token
  │
  ├─ POST /catalog/new ─────────────► pages.catalog_new()
  │     (CSRF token in body)           ├─ CSRFProtect validates token (raises 400 if bad/missing)
  │                                    ├─ ServiceForm(request.form).validate_on_submit()
  │                                    │     ├─ invalid → re-render same template, same form
  │                                    │     │            object (field errors + entered values
  │                                    │     │            preserved automatically by WTForms;
  │                                    │     │            NO document written)
  │                                    │     └─ valid → app.catalog.register_service(data)
  │                                    │            ├─ insert_one() into services
  │                                    │            │    (unique index on name enforces CAT-03)
  │                                    │            ├─ catch DuplicateKeyError → re-render form
  │                                    │            │    with a field-level uniqueness error
  │                                    │            └─ app.events.record_event("service_registered", ...)
  │                                    └─ redirect → /catalog (SC #1)
  │
  ├─ GET /catalog/<name> ───────────► pages.catalog_detail()
  │                                    ├─ app.catalog.get_service(name) [never-raise, None if absent]
  │                                    ├─ 404 if None
  │                                    └─ app.events.get_events_for_service(name)
  │                                         └─ renders detail.html (Registration + Related Events,
  │                                              reusing partials/event_row.html — D-09)
  │
  ├─ GET /catalog/<name>/delete ────► pages.catalog_delete_confirm()
  │                                    └─ renders confirm.html (zero JS, D-08)
  │
  ├─ POST /catalog/<name>/delete ───► pages.catalog_delete()
  │     (CSRF token in body)           ├─ CSRFProtect validates token
  │                                    ├─ app.catalog.deregister_service(name)
  │                                    │    ├─ delete_one({"name": name})
  │                                    │    └─ app.events.record_event("service_deregistered", ...)
  │                                    └─ redirect → /catalog (SC #4)
  │
  ├─ GET /feed ──────────────────────► pages.feed() — static shell, htmx poll target inside
  │       │
  │       └─ hx-get every 15s ──────► partials.feed()
  │                                    ├─ app.events.list_recent_events() [never-raise]
  │                                    ├─ HX-Request? → partials/feed_events.html (fragment)
  │                                    └─ else → feed_full_page.html (wraps the fragment)
  │
  └─ create_app() (startup, once per gunicorn worker — workers=1 so effectively once per process)
        ├─ mongo.init_app(app, ...)              [existing]
        ├─ csrf = CSRFProtect(); csrf.init_app(app)   [NEW]
        ├─ app.catalog.ensure_indexes()            [NEW — unique index on services.name]
        ├─ app.events.ensure_indexes()             [NEW — TTL index on events.ts]
        └─ app.events.emit_platform_started_once()  [NEW — D-12 guard, see Pattern 3]
```

### Recommended Project Structure

```
apps/launchpad/app/
├── extensions.py          # ADD: csrf = CSRFProtect() singleton, bound in create_app()
├── forms.py                # NEW — ServiceForm(FlaskForm) with all D-01/D-02 validators
├── catalog.py               # NEW — never-raise repo helper: list/get/register/deregister
├── events.py                 # NEW — never-raise repo helper: record_event/list_recent/get_for_service
│                                     + ensure_indexes() + emit_platform_started_once() guard
├── routes/
│   ├── pages.py             # EXTEND — fill /catalog, /catalog/new, /catalog/<name>,
│   │                                    /catalog/<name>/delete (GET+POST), /feed (unchanged shell)
│   └── partials.py           # EXTEND — add GET /partials/feed (mirrors status-cards/cluster-state)
└── templates/
    ├── catalog.html           # REPLACE stub — table + empty-state CTA (D-07, D-09)
    ├── onboard_form.html       # NEW — single-column form (D-01, D-06)
    ├── detail.html              # NEW — Registration block + Related Events block (D-09)
    ├── confirm_delete.html       # NEW — zero-JS confirm page (D-08)
    ├── feed.html                 # EXTEND stub — poll shell wrapping partials/feed_events.html
    └── partials/
        ├── event_row.html         # NEW — shared partial consumed by BOTH feed and detail (D-09)
        ├── feed_events.html        # NEW — list of event_row.html, newest first
        └── feed_full_page.html      # NEW — wraps feed_events.html for direct navigation

charts/launchpad/templates/mongodb/    # NEW directory — 4-file mirror of field-guide-api's analog
├── deployment.yaml
├── pvc.yaml
├── secret.yaml
└── service.yaml
```

### Pattern 1: FlaskForm with WTForms validators (D-01, D-02, D-06)

**What:** A single `ServiceForm(FlaskForm)` class in `app/forms.py` declares all five fields with
their validators. CSRF token is automatic (every `FlaskForm` subclass gets a `csrf_token` field
when `CSRFProtect` is initialized on the app).

**When to use:** The one and only onboard form (CAT-02, CAT-03).

**Example:**
```python
# Source: Flask official docs "Form Validation with WTForms"
# (flask.palletsprojects.com/en/stable/patterns/wtforms/) + Flask-WTF docs (flask-wtf.readthedocs.io)
import re

from flask_wtf import FlaskForm
from wtforms import SelectField, StringField, TextAreaField, URLField
from wtforms.validators import DataRequired, Length, Regexp, URL

NAME_PATTERN = re.compile(r"^[a-z0-9-]{2,40}$")


class ServiceForm(FlaskForm):
    name = StringField(
        "Service Name",
        validators=[
            DataRequired(message="This field is required."),
            Regexp(
                NAME_PATTERN,
                message="Use lowercase letters, numbers, and hyphens only (2-40 characters).",
            ),
        ],
    )
    repo_url = URLField(
        "Repository URL",
        validators=[
            DataRequired(message="This field is required."),
            URL(require_tld=True, message="Enter a valid http:// or https:// URL."),
        ],
    )
    owner = StringField(
        "Owner",
        validators=[DataRequired(message="Owner is required."), Length(max=100)],
    )
    description = TextAreaField("Description")  # optional — no validators
    environment = SelectField(
        "Environment",
        choices=[("dev", "dev"), ("staging", "staging"), ("prod", "prod")],
        default="dev",
        validators=[DataRequired()],
    )
```

**Uniqueness is NOT a WTForms validator** — MongoDB's unique index is the actual enforcement
mechanism (see Pattern 4). A form-level uniqueness *pre-check* (querying `mongo.db.services` inside
a custom validator) is optional UX polish, not the source of truth, and must never replace the
`try/except DuplicateKeyError` at insert time.

### Pattern 2: CSRFProtect app-factory wiring

**What:** `CSRFProtect` follows the exact same unbound-singleton-then-`init_app()` shape as the
existing `mongo`/`metrics` extensions.

**When to use:** Once, in `extensions.py` + `create_app()`.

**Example:**
```python
# Source: Flask-WTF docs (flask-wtf.readthedocs.io/en/latest/csrf/) — app factory pattern
# app/extensions.py
from flask_wtf import CSRFProtect

csrf: CSRFProtect = CSRFProtect()
```
```python
# app/__init__.py, inside create_app(), alongside existing mongo.init_app()/metrics.init_app()
from app.extensions import csrf, metrics, mongo

app.config.setdefault("WTF_CSRF_TIME_LIMIT", None)  # tokens don't expire mid-demo session
csrf.init_app(app)
```
`SECRET_KEY` is required for CSRF token signing (Flask-WTF docs: "By default this will use the
Flask app's SECRET_KEY"). D-05 already locks this — add `SECRET_KEY` to `Config` (env-sourced, dev
default) and to the launchpad chart Secret alongside the existing `MONGO_URI` key.

### Pattern 3: `platform_started` once-per-process guard (D-12)

**What:** A module-level flag on `app/events.py`, checked and set at the end of `create_app()`
after Mongo is confirmed reachable, gated so repeated `create_app()` calls in tests do not spam
the feed.

**When to use:** Exactly once, wired into `create_app()`.

**Example:**
```python
# app/events.py — module-level guard, NOT stored on the Flask app object, because the
# requirement is "once per PROCESS" (gunicorn workers=1 is locked in this project, so
# process == the single worker; test isolation still needs an explicit reset hook).
_platform_started_emitted = False


def emit_platform_started_once() -> None:
    """Fire the platform_started event exactly once per process.

    Never raises. If Mongo is unreachable at call time, the event write fails
    silently (same never-raise contract as record_event) and the guard flag is
    NOT set — so a later successful write attempt (e.g. a subsequent
    create_app() call once Mongo becomes reachable) can still fire it. This
    matches D-12's "first readiness" framing more precisely than an
    unconditional one-shot flag.
    """
    global _platform_started_emitted
    if _platform_started_emitted:
        return
    if record_event("platform_started", service_name=None):
        _platform_started_emitted = True


def reset_platform_started_guard_for_tests() -> None:
    """Test-only reset hook — conftest.py's `app` fixture calls this so each
    isolated test app can independently exercise the guard's first-call path."""
    global _platform_started_emitted
    _platform_started_emitted = False
```
Call `events.emit_platform_started_once()` at the end of `create_app()`, AFTER `mongo.init_app()`
and AFTER `events.ensure_indexes()` (index creation should happen before the first write, though
MongoDB will build the index either way — ordering here is about avoiding an unindexed collection
scan on the very first insert, not correctness).

**conftest.py implication:** the `app` fixture must call
`events.reset_platform_started_guard_for_tests()` (or monkeypatch the module attribute directly)
so `platform_started` firing behavior is itself testable as a first-class path, consistent with
how `k8s_disabled`/`k8s_enabled` are first-class tested branches in the existing harness — not an
afterthought.

### Pattern 4: Unique index + `DuplicateKeyError` race handling (D-02, D-03)

**What:** A pre-check query (fast-fail UX) backed by a unique index (correctness) and a caught
`DuplicateKeyError` (race safety) — three layers, not one.

**Example:**
```python
# Source: PyMongo API docs (pymongo.readthedocs.io/en/stable/api/pymongo/collection.html)
# + MongoDB manual "Unique Indexes" — standard try/except pattern, cross-verified across
# multiple community sources (oneuptime.com, labex.io) for the DuplicateKeyError shape.
from pymongo.errors import DuplicateKeyError

from app.extensions import mongo


def ensure_indexes() -> None:
    """Idempotent — safe to call on every create_app(). Never raises."""
    try:
        mongo.db.services.create_index("name", unique=True)
    except Exception:
        pass  # never block app startup on an index-creation hiccup; degrade, don't crash


def register_service(data: dict) -> tuple[bool, str | None]:
    """Returns (success, error_message). Never raises DuplicateKeyError to the caller —
    translates it into the D-06 field-level error message contract."""
    try:
        mongo.db.services.insert_one(data)
        return True, None
    except DuplicateKeyError:
        return False, "This name is already registered — choose another."
```

### Pattern 5: TTL index creation + config-driven expiry (D-10, FEED-03)

**What:** `create_index("ts", expireAfterSeconds=<config value>)` called once at startup, value
sourced from `app.config["EVENTS_TTL_SECONDS"]` (default 604800 = 7 days) so a smoke-test override
can pass a short value (e.g. 30 seconds) via env var.

**Example:**
```python
# Source: MongoDB manual "TTL Indexes" (mongodb.com/docs/manual/core/index-ttl/) — VERIFIED
# via direct WebFetch of the official docs page during this research session.
def ensure_indexes() -> None:
    ttl_seconds = current_app.config["EVENTS_TTL_SECONDS"]
    try:
        mongo.db.events.create_index("ts", expireAfterSeconds=ttl_seconds)
    except Exception:
        pass
```
```python
# app/config.py addition
EVENTS_TTL_SECONDS: int = int(os.environ.get("EVENTS_TTL_SECONDS", "604800"))  # 7 days
```
```yaml
# charts/launchpad/values.yaml addition (ConfigMap-sourced, not secret)
config:
  eventsTtlSeconds: "604800"
```

### Anti-Patterns to Avoid

- **Calling `create_index()` with a changed `expireAfterSeconds` value across deploys without
  `collMod`:** MongoDB raises an error ("Index with name: ... already exists with different
  options") if `create_index()` is called again with the SAME auto-generated index name (`ts_1`)
  but a different `expireAfterSeconds`. If the TTL value is ever changed after the index already
  exists in a real cluster, `create_index()` alone will NOT update it — this requires the
  `collMod` admin command. For this phase (fresh chart install, TTL fixed at 604800 in the app
  default), this is a documented risk, not an active bug — but the pitfall must be called out so a
  future TTL-value change doesn't silently fail via a swallowed `except Exception: pass`.
- **Using a form-level pre-check query as the ONLY uniqueness guard:** two concurrent registration
  requests with the same `name` can both pass a "does this exist?" pre-check before either
  `insert_one()` runs. The unique index + caught `DuplicateKeyError` is the actual correctness
  boundary; the pre-check (if added at all) is UX-only.
- **`from app.events import record_event` (direct-name import) in any module tests need to
  monkeypatch:** per the Phase 8 plan-check BLOCKER 3 lesson, this binds the original function at
  import time, defeating `monkeypatch.setattr(events_module, "record_event", ...)`. Any route or
  helper that tests need to intercept must do `from app import events` then call
  `events.record_event(...)`.
- **htmx form submission for the onboard form:** D-06 explicitly forbids this ("avoids the
  CSRF-token-in-swapped-fragment footgun") — the onboard form is a classic full-page POST, no
  `hx-post` attribute anywhere on `onboard_form.html`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CSRF token generation/validation | Custom `secrets.token_hex()` + session comparison | Flask-WTF `CSRFProtect` | D-04 locked; hand-rolled CSRF is a well-known source of timing-attack and session-fixation bugs; Flask-WTF's implementation is battle-tested across the entire Pallets ecosystem |
| Form field validation + error collection | Manual `if not request.form.get("name"): errors.append(...)` chains | WTForms validators (`DataRequired`, `Regexp`, `URL`, `Length`) | Manual validation chains are exactly the "code quickly becomes hard to read" problem the Flask docs cite as WTForms' reason to exist; also loses automatic multi-error-at-once collection needed for D-06's "all field errors show simultaneously" |
| Relative-time rendering ("2 minutes ago") | A hand-rolled `datetime` diff formatter, or a JS date library | Small pure-Python helper (stdlib `datetime` diff, same shape as `cluster_state.py`'s existing `_pod_age()` helper) | The UI-SPEC explicitly forbids a JS date library ("do NOT introduce a relative-time library or JS") but does NOT forbid a tiny server-side helper — `_pod_age()` in `cluster_state.py` is the exact precedent to mirror (age-string formatting, not a general date library) |
| Document expiry / cleanup | A cron job or Celery task that periodically deletes old events | MongoDB TTL index (`expireAfterSeconds`) | This is precisely what TTL indexes exist to replace — a background sweep the database already runs every ~60s; a custom scheduled-deletion job would be redundant infrastructure for a problem MongoDB solves natively |

**Key insight:** Every "don't hand-roll" item in this phase already has a first-class MongoDB or
Flask-WTF primitive. The only genuinely new code this phase writes is business logic (which fields
a service has, which three event types exist, when to fire them) — never plumbing.

## Common Pitfalls

### Pitfall 1: mongomock silently accepts TTL index creation but never expires documents

**What goes wrong:** A test asserts `mongo.db.events.create_index("ts", expireAfterSeconds=604800)`
succeeds, then writes a fake-old event and asserts it's gone after some wait — this test will hang
or fail, because mongomock has no background expiry thread.

**Why it happens:** `[VERIFIED: mongomock 4.3.0 source, inspected directly]` mongomock's
`create_index()` stores `expireAfterSeconds` in its internal index metadata dict identically to how
real PyMongo/MongoDB does — so the CALL succeeds and looks correct — but `collection.py` contains
no code path that ever reads that metadata to purge documents. There is no `background`, `TTL`, or
`expire`-sweep logic anywhere in the module beyond the metadata storage itself (confirmed by
grepping the unpacked wheel source for those terms).

**How to avoid:** Test suite verifies ONLY that the index exists with the correct
`expireAfterSeconds` value (`mongo.db.events.index_information()`), never that a document
disappears. TTL *timing* correctness is verified live via smoke only (already the D-10 decision) —
document this explicitly in `conftest.py` as a code comment, matching the discipline already used
for the K8s-client mocking rationale.

**Warning signs:** A test that sleeps or advances a mocked clock and then asserts a document count
change on the `events` collection — this is a red flag that the test author forgot mongomock's TTL
limitation.

### Pitfall 2: `IndexOptionsConflict`-equivalent error if the TTL value changes between deploys

**What goes wrong:** If `EVENTS_TTL_SECONDS` is changed (e.g. from 604800 to a different value) and
the app is redeployed against a MongoDB that already has the `ts_1` index from a previous deploy,
`create_index()` raises `OperationFailure` ("Index with name: ts_1 already exists with different
options") — both in real MongoDB `[CITED: mongodb.com/docs/manual/core/index-ttl/]` and in
mongomock (confirmed identical conflict-check logic in the inspected source: `if existing_index and
index_dict != existing_index: raise OperationFailure(...)`).

**Why it happens:** `create_index()` is not a "create or update" operation for TTL value changes —
MongoDB explicitly documents that changing `expireAfterSeconds` on an existing index requires the
`collMod` admin command, not `createIndex()`.

**How to avoid:** `ensure_indexes()` wraps `create_index()` in `try/except Exception: pass` (never
crash startup on an index-creation conflict) — this is a deliberate degrade-not-crash choice
consistent with every other helper in this codebase, but it means a silent TTL-value drift is
possible if this is ever hit in the live cluster. For this phase's scope (fresh chart install,
fixed default), this is documented as a known limitation, not fixed — a future phase adding a
`collMod`-based migration path is out of scope here.

**Warning signs:** Startup logs (if ever added) showing an index-creation exception being
swallowed silently — currently invisible since nothing logs the caught exception.

### Pitfall 3: `WTF_CSRF_ENABLED=False` in ALL tests hides a broken CSRF wiring

**What goes wrong:** If every single test sets `WTF_CSRF_ENABLED=False` (the common blanket
testing pattern `[MEDIUM confidence, WebSearch cross-verified across 3 sources]`), SC #2's
"CSRF protection intact" claim is never actually exercised by the test suite — a regression that
removes `csrf.init_app(app)` entirely would still pass all tests.

**Why it happens:** `WTF_CSRF_ENABLED=False` is the standard, low-friction way to keep the majority
of route tests simple (no need to fetch+relay a token for every POST test). But blanket-applying it
project-wide silently defeats the one test that matters most for CAT-03.

**How to avoid:** Two test configurations are needed, as flagged in the phase's key research
questions: (1) the default `app`/`client` fixtures in `conftest.py` keep `WTF_CSRF_ENABLED=False`
for convenience across most catalog/form tests; (2) ONE dedicated test (or a small dedicated
fixture, e.g. `csrf_enabled_client`) constructs an app WITHOUT that override, performs a GET to
capture the token from the rendered form's hidden input (parse via a simple regex or a minimal HTML
parse — no new dependency needed for one token extraction), and POSTs with (a) no token → expect
400, and (b) the captured token → expect success. This proves the wiring is live without adding
CSRF-token plumbing to every other test.

**Warning signs:** grep the test suite for `WTF_CSRF_ENABLED` — if the string appears in exactly
one place (a blanket global override) and nowhere does a test assert a 400/403 on a missing/invalid
token, SC #2 is not actually covered.

### Pitfall 4: Flask-PyMongo 3.x test-harness pattern (`mongo.cx` / `mongo.db` monkeypatch) extends unchanged to the new collections

**What goes wrong:** None, if followed — but worth confirming explicitly since it's easy to assume
a new collection needs new fixture plumbing.

**Why it happens:** N/A — this is a confirmation, not a real pitfall. `conftest.py`'s existing `app`
fixture already monkeypatches `mongo.cx`/`mongo.db` to mongomock equivalents; `mongo.db.services`
and `mongo.db.events` are just new collection names on the SAME mocked `db` object — no new fixture
is needed beyond what already exists.

**How to avoid:** N/A. Documented here only so the planner does not over-scope Wave 0 test
infrastructure work that isn't actually needed.

### Pitfall 5: `URLField` / `URL()` validator accepting non-http(s) schemes

**What goes wrong:** WTForms' `URL()` validator by default validates general URL syntax, not
specifically `http`/`https` — a value like `ftp://example.com` or `javascript:alert(1)` could pass
generic URL syntax checks if the validator isn't scoped.

**Why it happens:** `URL(require_tld=True)` alone checks shape (scheme + domain + TLD), not an
explicit scheme allowlist.

**How to avoid:** Layer a `Regexp` validator (or a custom validator) restricting the scheme to
`^https?://` in addition to `URL()`, OR use a custom validator that calls
`urllib.parse.urlparse(value).scheme in ("http", "https")`. The UI-SPEC's exact error copy ("Enter
a valid http:// or https:// URL") implies scheme is being checked, not just general URL shape —
implement this explicitly rather than assuming `URL()` alone covers it.

**Warning signs:** A form test submitting `javascript:alert(1)` as `repo_url` that unexpectedly
passes validation.

## Code Examples

### CSRF-enabled test proving SC #2

```python
# Source: pattern synthesized from Flask-WTF docs (CSRFProtect requires SECRET_KEY) +
# community pattern (gist.github.com/singingwolfboy/2fca1de64950d5dfed72, modernized —
# the gist's RequestShim approach is dated; the simpler "GET first, scrape token, POST it
# back" approach below avoids the extra indirection) [MEDIUM confidence — community pattern,
# not officially documented by Flask-WTF, but the underlying mechanism (session-bound token,
# rendered in a hidden input) is directly from the official CSRF docs].
import re


def test_onboard_form_rejects_missing_csrf_token(app):
    app.config["WTF_CSRF_ENABLED"] = True  # override the test-default False for this one test
    client = app.test_client()

    get_resp = client.get("/catalog/new")
    match = re.search(r'name="csrf_token" type="hidden" value="([^"]+)"', get_resp.text)
    token = match.group(1)

    # Missing/garbage token -> Flask-WTF's CSRFProtect raises CSRFError -> 400
    bad_resp = client.post("/catalog/new", data={"name": "svc", "csrf_token": "invalid"})
    assert bad_resp.status_code == 400

    # Valid captured token -> request proceeds past the CSRF check (may still fail
    # WTForms field validation separately, but must NOT be a CSRF 400)
    good_resp = client.post(
        "/catalog/new",
        data={"name": "svc-a", "repo_url": "https://github.com/org/repo",
              "owner": "team", "environment": "dev", "csrf_token": token},
    )
    assert good_resp.status_code != 400
```

### Never-raise event writer (mirrors `status.py`/`cluster_state.py` shape)

```python
# app/events.py
from datetime import datetime, timezone

from app.extensions import mongo


def record_event(event_type: str, service_name: str | None) -> bool:
    """Write one event document. Never raises — returns False on any failure
    so callers (registration/deregistration flows) can proceed even if the
    events write fails; the primary catalog mutation must not be blocked by
    a secondary feed-write failure."""
    try:
        mongo.db.events.insert_one(
            {
                "type": event_type,
                "service_name": service_name,
                "ts": datetime.now(timezone.utc),
            }
        )
        return True
    except Exception:
        return False
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `CsrfProtect` (lowercase-s class name) | `CSRFProtect` | Flask-WTF ~0.14 (multi-year-old rename) | Not relevant to a fresh 1.3.0 install — mentioned only because older tutorials/StackOverflow answers still show the deprecated spelling; do not copy code samples using `CsrfProtect`. |
| Bitnami MongoDB Helm chart | Plain `mongo:7` manifests | Already resolved in Phase 8 research (Broadcom paywall, Sep 2025) | Directly reused here — DEP-03's manifests are the SAME pattern already proven in `charts/field-guide-api/templates/mongodb/`, just re-namespaced. No new decision needed. |

**Deprecated/outdated:** None newly discovered this phase — the codebase's existing choices
(mongo:7 plain manifests, Deployment+PVC not StatefulSet) remain current per Phase 8's research and
apply unchanged here.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Flask-WTF 1.3.0 and WTForms 3.2.2 are legitimate, non-malicious packages | Package Legitimacy Audit | LOW — both verified via PyPI JSON API (authoritative registry) with strong independent signals (pallets-eco org, decade+ history); slopcheck itself could not run in this environment, so the formal audit gate is unmet even though manual evidence is strong. Planner should still gate the `pip install` behind a lightweight human-verify checkpoint per protocol. |
| A2 | `URL(require_tld=True)` + a supplementary scheme-restricting `Regexp`/custom validator is the correct WTForms pattern for "http(s) only" validation | Pitfall 5 / Pattern 1 | LOW-MEDIUM — this is a reasonable, standard WTForms composition but was not verified against Flask-WTF's own docs page for `URLField` specifically (the fetched docs pages covered CSRF and general form patterns, not this exact field type in depth); the planner/implementer should double check `URLField` vs `StringField` + `URL()` validator equivalence when writing the task. |
| A3 | `EVENTS_TTL_SECONDS` should be sourced from `app.config` (ConfigMap-backed) rather than the Secret | Pattern 5 | LOW — TTL seconds is not sensitive data; this follows the existing `APP_VERSION`/`FIELD_GUIDE_BASE_URL` ConfigMap precedent in `values.yaml`'s `config:` block, not the `MONGO_URI`/`SECRET_KEY` Secret block. High-confidence inference from existing chart structure, but not an explicit locked decision in CONTEXT.md. |

## Open Questions

1. **(RESOLVED — via Recommendation below; plans follow it)** Exact WTForms `URLField` vs `StringField` + `URL()` validator choice
   - What we know: WTForms ships both a generic `StringField` (paired with a `URL()` validator) and
     a dedicated `URLField` (which renders `<input type="url">`, matching the UI-SPEC's Form
     Contract table exactly: `repo_url` → `<input type="url">`).
   - What's unclear: Whether `URLField`'s default validation behavior (if any beyond rendering)
     differs meaningfully from `StringField` + explicit `URL()` — this was not verified against
     WTForms' own field-reference docs in this session (only Flask-WTF's CSRF/form-basics pages
     were fetched).
   - Recommendation: Use `URLField` (matches the UI-SPEC's exact input type) with an explicit
     `URL(require_tld=True)` validator plus the scheme-restriction addition from Pitfall 5 — this
     combination is defensive regardless of `URLField`'s exact default behavior.

2. **Whether `ensure_indexes()` should log (not just silently swallow) index-creation failures**
   - What we know: every existing helper in this codebase (`status.py`, `cluster_state.py`) follows
     a strict never-raise, never-log-exception-detail discipline (T-08-06/T-07-07).
   - What's unclear: whether index-creation failure (a startup-time, not request-time, concern)
     should be exempted from that discipline since it's not user-facing and wouldn't leak anything
     to an HTTP response.
   - Recommendation: Claude's Discretion per CONTEXT.md — planner can decide; recommend keeping the
     silent-swallow pattern for consistency, since no logging infrastructure exists anywhere else
     in this codebase yet (no evidence of a `logging` setup in any reviewed module).

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CAT-01 | Developer can view a service catalog listing services registered in MongoDB | Pattern: `app.catalog.list_services()` never-raise helper (mirrors `status.py` shape); Table Contract in UI-SPEC; sort by `registered_at` descending |
| CAT-02 | Developer can onboard a new service through a form; the registration persists in MongoDB | Pattern 1 (FlaskForm + validators), Pattern 4 (unique index + insert), Standard Stack (Flask-WTF 1.3.0) |
| CAT-03 | The onboard form validates input server-side (CSRF-protected) and re-renders with field-level errors on invalid input | Pattern 1 + Pattern 2 (CSRFProtect wiring), Pitfall 3 (two-tier CSRF test posture), Code Example (CSRF-enabled test) |
| CAT-04 | Developer can open a service detail page showing the full registration and that service's related events | Architecture diagram (`GET /catalog/<name>` flow), `app.events.get_events_for_service()`, shared `event_row.html` partial (D-09) |
| CAT-05 | Developer can deregister (delete) a service from the catalog after a confirmation step | Architecture diagram (`GET`/`POST /catalog/<name>/delete` flow), Anti-Patterns (zero-JS confirm, D-08) |
| FEED-01 | Developer sees an activity/events feed of recent platform events (newest first), backed by a persisted MongoDB collection | `app.events.list_recent_events()`, `/partials/feed` route mirroring `partials.py`'s established HX-Request branching |
| FEED-02 | Platform actions write events into the feed | Pattern 3 (`platform_started` once-per-process guard), `record_event()` helper called from registration/deregistration flows |
| FEED-03 | The events collection is bounded by a TTL index | Pattern 5 (TTL index creation), Pitfall 1 (mongomock cannot verify expiry), Pitfall 2 (`IndexOptionsConflict`-equivalent risk) |
| DEP-03 | Launchpad runs its own in-cluster MongoDB via `mongo:7` manifests; field-guide-api chart untouched | Recommended Project Structure (`charts/launchpad/templates/mongodb/` 4-file mirror); direct analog to `charts/field-guide-api/templates/mongodb/` already read in this session |
</phase_requirements>

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| PyPI registry access | Package version verification | Yes | — | — |
| slopcheck | Package legitimacy gate | No | — | Manual legitimacy evidence gathered (pallets-eco org, release history); planner gates install behind human-verify checkpoint per graceful-degradation protocol |
| Context7 MCP / ctx7 CLI | Library docs lookup | No (`ctx7` not found on PATH, no MCP tools available) | — | WebFetch against official docs (flask-wtf.readthedocs.io, mongodb.com/docs, flask.palletsprojects.com) used instead — all HIGH/MEDIUM confidence sources still reached |
| mongo:7 Docker image | In-cluster MongoDB | Not verified live this session (no cluster interaction required for research) | — | Already proven working in Phase 8 (field-guide-api's own mongo:7 manifests deployed successfully per Phase 8 STATE.md notes) |

**Missing dependencies with no fallback:** none — all gaps had viable fallbacks used during this
research session.

**Missing dependencies with fallback:** slopcheck (manual evidence gathered instead), Context7
(official docs WebFetch used instead).

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|----------------|---------|-------------------|
| V2 Authentication | No | Explicitly out of scope for v1.1 (REQUIREMENTS.md "Authentication / multi-user... not warranted in v1.1") |
| V3 Session Management | Partial — CSRF token relies on Flask's signed session cookie | Flask's default `itsdangerous`-signed session cookie, keyed by `SECRET_KEY` (D-05); no new session mechanism introduced |
| V4 Access Control | No | Single-user local platform; no per-service ownership enforcement beyond the `owner` display field (metadata, not an access-control boundary) |
| V5 Input Validation | Yes | WTForms validators (`DataRequired`, `Regexp`, `URL`, `Length`) at the form layer; MongoDB unique index at the persistence layer — defense in depth, not a single point of trust |
| V6 Cryptography | Partial — CSRF token generation | Delegated entirely to Flask-WTF/itsdangerous; never hand-rolled (D-04 explicit lock) |
| V13 API and Web Service | Yes (implicitly, via CSRF) | `CSRFProtect` covers all state-changing (`POST`) requests app-wide once initialized — including the two new POST routes this phase adds (`/catalog/new`, `/catalog/<name>/delete`) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|-----------------------|
| CSRF on registration/deregistration POST routes | Spoofing / Tampering | `CSRFProtect` app-wide (D-04); every `FlaskForm` auto-includes a token; the delete-confirm form (Pattern in UI-SPEC, `POST /catalog/<name>/delete`) must ALSO be a `FlaskForm` (or embed `{{ csrf_token() }}` directly) even though it has no other fields — easy to forget since it's "just a delete button" |
| NoSQL injection via unsanitized `name` used as a MongoDB query key | Tampering | The `name` field is validated by `Regexp(^[a-z0-9-]{2,40}$)` BEFORE ever reaching a MongoDB query (both at insert time via the form, and at lookup time via the URL path `/catalog/<name>`); PyMongo's BSON encoding of Python dicts (not raw string interpolation into a query) is inherently injection-resistant for this use case as long as the value is used as a plain equality match (`{"name": name}`), never as a `$where` clause or similar |
| Reflected XSS via unescaped `description` (free-text field) rendered in `detail.html` | Tampering / Information Disclosure | Jinja2 auto-escapes all template variables by default (`{{ service.description }}` is escaped unless explicitly marked `\| safe`) — no new escaping code needed, but the implementer must never add `\| safe` to any user-supplied field render |
| Error message leaking internal detail (Mongo connection string, stack trace) on a failed insert | Information Disclosure | Continues the established T-08-06 discipline (never `str(exception)` in HTML) — the UI-SPEC's exact copy ("Could not save this service. Check the fields below and try again.") is a fixed generic string, matching the pattern already used in `status.py`/`cluster_state.py` |

## Sources

### Primary (HIGH confidence)

- `https://pypi.org/pypi/Flask-WTF/json` — Flask-WTF version 1.3.0, release date 2026-04-23, `pallets-eco` org, `requires_dist` — VERIFIED via authoritative registry API, not search
- `https://pypi.org/pypi/WTForms/json` — WTForms version 3.2.2, `requires_python >=3.10`, `pallets-eco` org — VERIFIED via authoritative registry API
- `https://www.mongodb.com/docs/manual/core/index-ttl/` — TTL index syntax, `IndexOptionsConflict` behavior, `collMod` requirement for changing `expireAfterSeconds`, 60s background sweep interval, BSON-date field type requirement — fetched directly, official MongoDB docs
- `https://flask.palletsprojects.com/en/stable/patterns/wtforms/` — official Flask docs recommending Flask-WTF, canonical view-function pattern (`validate_on_submit`/`validate()`, render same template on failure) — fetched directly
- mongomock 4.3.0 wheel source (`mongomock/collection.py`), downloaded via `pip download` and inspected directly in this session — confirmed `expireAfterSeconds` is stored in index metadata without any background purge logic; confirmed the `existing_index and index_dict != existing_index` conflict-raise path mirrors real MongoDB's `IndexOptionsConflict`

### Secondary (MEDIUM confidence)

- `https://flask-wtf.readthedocs.io/en/latest/csrf/` — CSRFProtect app-factory setup (`csrf.init_app(app)`), `SECRET_KEY` requirement — fetched directly but page content was thin on testing-specific guidance (WTF_CSRF_ENABLED not mentioned on this specific page)
- WebSearch (multiple results) — `WTF_CSRF_ENABLED = False` as the standard test-config pattern; cross-verified across 3+ independent sources (flowfx.de blog, a GitHub gist, general Flask-WTF community consensus)
- `https://gist.github.com/singingwolfboy/2fca1de64950d5dfed72` — CSRF-enabled test client pattern; noted as somewhat dated (custom `RequestShim` class), simplified to a GET-then-scrape-token approach in this research's Code Example since the underlying mechanism (token rendered in a hidden form input) is directly confirmable from the official CSRF docs
- WebSearch — PyMongo `DuplicateKeyError` try/except pattern; cross-verified across 3+ sources (oneuptime.com, labex.io, Snyk advisor), all describing the identical standard pattern

### Tertiary (LOW confidence)

- GitHub issue `mongomock/mongomock#655` — historical discussion of TTL support proposals; superseded by direct source inspection of the installed 4.3.0 wheel (Primary source above), which is authoritative for this project's actual pinned version

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — both new packages verified via PyPI JSON API directly, with independent legitimacy signals (org, release history) gathered manually since slopcheck was unavailable
- Architecture: HIGH — every pattern is a direct, verifiable extension of code already read in this codebase this session (extensions.py, status.py, cluster_state.py, partials.py, conftest.py, Phase 8 chart mirror)
- Pitfalls: HIGH for TTL/mongomock (verified by direct source inspection, not just search); MEDIUM for CSRF testing pattern (community-sourced but internally consistent and cross-verified against official CSRF mechanism docs)

**Research date:** 2026-07-12
**Valid until:** 2026-08-11 (30 days — stable ecosystem, no fast-moving dependencies in this phase's scope)
