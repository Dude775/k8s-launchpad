---
phase: 09-service-catalog-events-mongodb-crud
reviewed: 2026-07-13T11:26:09Z
depth: standard
files_reviewed: 33
files_reviewed_list:
  - apps/launchpad/app/__init__.py
  - apps/launchpad/app/catalog.py
  - apps/launchpad/app/config.py
  - apps/launchpad/app/events.py
  - apps/launchpad/app/extensions.py
  - apps/launchpad/app/forms.py
  - apps/launchpad/app/routes/pages.py
  - apps/launchpad/app/routes/partials.py
  - apps/launchpad/app/templates/base.html
  - apps/launchpad/app/templates/catalog.html
  - apps/launchpad/app/templates/confirm_delete.html
  - apps/launchpad/app/templates/detail.html
  - apps/launchpad/app/templates/feed.html
  - apps/launchpad/app/templates/feed_full_page.html
  - apps/launchpad/app/templates/onboard_form.html
  - apps/launchpad/app/templates/partials/event_row.html
  - apps/launchpad/app/templates/partials/feed_events.html
  - apps/launchpad/requirements.txt
  - apps/launchpad/tests/conftest.py
  - apps/launchpad/tests/test_catalog.py
  - apps/launchpad/tests/test_events.py
  - apps/launchpad/tests/test_factory.py
  - apps/launchpad/tests/test_pages.py
  - apps/launchpad/tests/test_partials.py
  - charts/launchpad/templates/_helpers.tpl
  - charts/launchpad/templates/configmap.yaml
  - charts/launchpad/templates/deployment.yaml
  - charts/launchpad/templates/mongodb/deployment.yaml
  - charts/launchpad/templates/mongodb/pvc.yaml
  - charts/launchpad/templates/mongodb/secret.yaml
  - charts/launchpad/templates/mongodb/service.yaml
  - charts/launchpad/templates/secret.yaml
  - charts/launchpad/values.yaml
findings:
  critical: 0
  warning: 6
  info: 8
  total: 14
status: issues_found
---

# Phase 9: Code Review Report (Re-Review After Gap Closure)

**Reviewed:** 2026-07-13T11:26:09Z
**Depth:** standard
**Files Reviewed:** 33
**Status:** issues_found

## Summary

Re-review of the Phase 9 service catalog + events feed implementation after the plan 09-04 gap-closure work (commits d4123d0, 8590ac4). The single Critical finding from the prior review (CR-01) is verified fixed. The core layers remain disciplined: never-raise repo helpers, dict-encoded Mongo queries, CSRF on all POSTs, locked copy strings, and unique-index-based name uniqueness.

However, the gap-closure work addressed ONLY CR-01. All five prior warnings (WR-01 through WR-05) remain present verbatim in the current code and are carried forward unchanged, as do all seven prior Info items. One NEW warning was found this pass: the `test_factory.py` tests bypass the mongomock fixture entirely and will open real sockets to `localhost:27017` (and write real documents into a developer's local `launchpad` database when a local MongoDB is running) — directly contradicting conftest.py's "no real MongoDB/network is used in any test" contract.

### Resolved Since Prior Review

**CR-01 (RESOLVED): Relative event times rendered "unknown" for events read from real MongoDB.**
Verified fixed at both layers:
- `apps/launchpad/app/__init__.py:51-55` — `mongo.init_app(..., tz_aware=True)` makes PyMongo decode BSON dates as tz-aware UTC at the source.
- `apps/launchpad/app/events.py:130-131` — `_relative_time()` now normalizes a naive datetime (`ts.replace(tzinfo=timezone.utc)`) before the aware-vs-naive subtraction; non-datetime garbage still raises `AttributeError` inside the `try` and correctly falls through to `"unknown"`.
- Regression tests `test_relative_time_naive_utc_now_returns_just_now` and `test_relative_time_naive_utc_past_returns_real_value` (`apps/launchpad/tests/test_events.py:258-265`) pass naive UTC datetimes and assert real values, exactly as the prior review prescribed.

The fix is belt-and-suspenders (driver-level + render-level) and correct. Note that mongomock's `init_app` replacement in conftest.py silently discards the `tz_aware=True` kwarg, so the driver-level half is only verifiable against a real MongoDB (Phase 10 smoke) — the render-level guard is what the unit tests actually prove, which is acceptable.

## Narrative Findings (AI reviewer)

## Warnings

### WR-01: `mongoUri` default hardcodes the MongoDB hostname and duplicates credentials — desyncs from the helper and from `mongodb.auth.password` (carried forward, unresolved)

**File:** `charts/launchpad/values.yaml:72`, `charts/launchpad/templates/secret.yaml:18`, `charts/launchpad/templates/_helpers.tpl:38-46`
**Issue:** `_helpers.tpl` still declares `launchpad.mongodb.fullname` as the "SINGLE source of truth" used by "templates/secret.yaml (MONGO_URI hostname)" — but `secret.yaml:18` renders `.Values.mongoUri` verbatim, whose default hardcodes `launchpad-mongodb` and `launchpad-dev-password`. Two failure modes: (1) installing with any release name other than `launchpad` produces a Service named `<release>-launchpad-mongodb` while the app still dials `launchpad-mongodb` — connection failure mitigated only by a values-file comment; (2) `--set mongodb.auth.password=<real>` rotates the Mongo root password but the app keeps authenticating with the stale password embedded in `mongoUri` — auth failure unless the operator updates two coupled values in lockstep. The helper's documentation is factually false about its own consumers.
**Fix:** Compose the URI in the template from the single sources of truth; keep `mongoUri` only as an optional explicit override:
```yaml
# charts/launchpad/templates/secret.yaml
stringData:
  MONGO_URI: {{ .Values.mongoUri | default (printf "mongodb://%s:%s@%s:27017/%s?authSource=admin&serverSelectionTimeoutMS=2000" .Values.mongodb.auth.username .Values.mongodb.auth.password (include "launchpad.mongodb.fullname" .) .Values.mongodb.auth.database) | quote }}
```
and set `mongoUri: ""` in values.yaml.

### WR-02: Detail page renders stored `repo_url` as a raw href — no scheme re-check at the render boundary (carried forward, unresolved)

**File:** `apps/launchpad/app/templates/detail.html:12`
**Issue:** `<a href="{{ service.repo_url }}">` trusts that every document in `services` passed through `ServiceForm`'s `^https?://` regexp. The form is the only enforcement boundary — any document written directly to MongoDB (mongosh seeding, a future import endpoint, another platform component sharing the DB) can carry `javascript:alert(1)` as `repo_url`, and Jinja autoescaping does not neutralize a `javascript:` scheme inside an href. Stored-XSS vector one out-of-band write away.
**Fix:** Add defense in depth at the render boundary:
```jinja
{% if service.repo_url and service.repo_url.startswith(('http://', 'https://')) %}
<dd><a href="{{ service.repo_url }}" rel="noopener noreferrer">{{ service.repo_url }}</a></dd>
{% else %}
<dd>{{ service.repo_url or '—' }}</dd>
{% endif %}
```
or validate the scheme in `catalog.register_service()` so the invariant holds at the data layer regardless of the write path.

### WR-03: Malformed `EVENTS_TTL_SECONDS` env var crashes the app at import time (carried forward, unresolved)

**File:** `apps/launchpad/app/config.py:55`
**Issue:** `EVENTS_TTL_SECONDS: int = int(os.environ.get("EVENTS_TTL_SECONDS", "604800"))` executes at class-body (module import) time. A malformed value (e.g. `"7d"`, `"1e6"`) raises `ValueError` while importing `app.config`, before `create_app()` runs — gunicorn workers crash-loop on boot instead of degrading. This is the only config value with an import-time crash path in a codebase whose helpers otherwise follow a strict never-raise discipline, and the chart makes typos easy (`eventsTtlSeconds` is a free-form string in values.yaml).
**Fix:**
```python
try:
    EVENTS_TTL_SECONDS: int = int(os.environ.get("EVENTS_TTL_SECONDS", "604800"))
except ValueError:
    EVENTS_TTL_SECONDS = 604800  # fall back to 7-day default on malformed env
```

### WR-04: Event-row template mislabels any unknown event type as "Platform started" (carried forward, unresolved)

**File:** `apps/launchpad/app/templates/partials/event_row.html:19-25`
**Issue:** The `{% else %}` branch is the catch-all: any event whose `type` is not `service_registered` / `service_deregistered` — including malformed documents and every future event type this IDP roadmap implies (deploys, scans) — renders with the "Platform started" label. Silently wrong data shown to the user the moment a fourth event type exists; nothing fails loudly.
**Fix:** Match `platform_started` explicitly and give unknowns a neutral fallback:
```jinja
{% elif event.type == 'platform_started' %}
  ... existing platform-started row ...
{% else %}
<div class="event-row">
  <span style="color: var(--pico-muted-color);">&bull;</span>
  <span>{{ event.type | replace('_', ' ') | capitalize }}</span>
  <small style="color: var(--pico-muted-color);">{{ events._relative_time(event.ts) }}</small>
</div>
{% endif %}
```

### WR-05: `mongodb.persistence.enabled` is a dead knob — PVC and volume are rendered unconditionally (carried forward, unresolved)

**File:** `charts/launchpad/templates/mongodb/pvc.yaml:1`, `charts/launchpad/templates/mongodb/deployment.yaml:61-67`, `charts/launchpad/values.yaml:58-59`
**Issue:** `values.yaml` exposes `mongodb.persistence.enabled: true`, but no template reads it — `pvc.yaml` and the deployment's `volumeMounts`/`volumes` are gated only on `mongodb.enabled` (verified by grep: zero references to `persistence.enabled` in any template). An operator setting `persistence.enabled: false` still gets a PVC that sits Pending on clusters without a default StorageClass, blocking the mongod pod — the opposite of what disabling persistence should do.
**Fix:** Either honor the flag (`{{- if and .Values.mongodb.enabled .Values.mongodb.persistence.enabled }}` in pvc.yaml plus an `emptyDir` fallback for the `data` volume in deployment.yaml), or delete the `enabled` key from values.yaml so the schema doesn't advertise a capability the chart doesn't have.

### WR-06: `test_factory.py` tests bypass mongomock and touch a real local MongoDB when one is running (NEW)

**File:** `apps/launchpad/tests/test_factory.py:35,60`, `apps/launchpad/tests/conftest.py:1-11`, `apps/launchpad/app/config.py:14,31-33`
**Issue:** `test_create_app_returns_flask_app` and `test_create_app_constructs_with_no_live_mongo` call `create_app()` directly without the `app` fixture, so the mongomock `PyMongo.init_app` patch is NOT in place. Since Phase 9, `create_app()` performs real Mongo operations at startup (`ensure_indexes` x2 + `emit_platform_started_once`). These tests therefore open real sockets to the URI from `Config.MONGO_URI` — `mongodb://localhost:27017/launchpad` by default, or whatever the developer's `.env` supplies (config.py runs `load_dotenv()` at import). On a machine where a local MongoDB is up (the normal dev state for this project), the tests: (1) create a unique index and a TTL index on the developer's REAL `launchpad` database, (2) insert a real `platform_started` document into its `events` collection, and (3) set the module-global `_platform_started_emitted` guard as a side effect. This directly contradicts conftest.py's stated contract ("No real cluster, kubeconfig, or MongoDB/network is used in any test") and makes test behavior environment-dependent — the 10ms `MONGO_SERVER_SELECTION_TIMEOUT_MS` only makes the failure path fast, it does not prevent the success path.
**Fix:** Apply the same isolation these tests' siblings get — e.g. reuse the mongomock patch:
```python
def test_create_app_returns_flask_app(monkeypatch):
    import mongomock
    from flask_pymongo import PyMongo

    mock_client = mongomock.MongoClient()
    monkeypatch.setattr(
        PyMongo, "init_app",
        lambda self, flask_app, **kw: setattr(self, "cx", mock_client)
        or setattr(self, "db", mock_client["test_db"]),
    )
    ...
```
or at minimum point `MONGO_URI` at a guaranteed-unroutable address (`mongodb://192.0.2.1:27017/test` — TEST-NET-1) via the config override so the never-raise degradation path is what is actually exercised, deterministically.

## Info

### IN-01: Templates call the private `events._relative_time()` via a module passed into render context (carried forward)

**File:** `apps/launchpad/app/routes/pages.py:84-86`, `apps/launchpad/app/routes/partials.py:73-74`, `apps/launchpad/app/templates/partials/event_row.html:8,17,23`
**Issue:** The whole `events` module is injected as a template variable so Jinja can call an underscore-private function. Leaks module internals into the view layer; every route including `event_row.html` must remember `events=events` or hit a runtime `UndefinedError` only when an event renders.
**Fix:** Register once in `create_app()`: `app.jinja_env.filters["relative_time"] = events._relative_time`, use `{{ event.ts | relative_time }}`, drop the `events=` kwargs.

### IN-02: `registered_at` is stamped in two places (carried forward)

**File:** `apps/launchpad/app/routes/pages.py:67`, `apps/launchpad/app/catalog.py:77`
**Issue:** The route sets `registered_at` and `register_service()` also `setdefault`s it. Two owners of one invariant invite drift.
**Fix:** Remove the route-level stamp; let the repository be the single owner, as its docstring already claims.

### IN-03: `mongodb.auth.database` value is unused (carried forward)

**File:** `charts/launchpad/values.yaml:57`
**Issue:** No template references `.Values.mongodb.auth.database`; the DB name lives only inside the hardcoded `mongoUri` path. Dead config suggesting wiring that doesn't exist.
**Fix:** Reference it when composing `MONGO_URI` (see WR-01 fix) or remove it.

### IN-04: MongoDB container has no resources and no securityContext (carried forward)

**File:** `charts/launchpad/templates/mongodb/deployment.yaml:34-63`
**Issue:** The app container gets requests/limits, `runAsNonRoot`, and `allowPrivilegeEscalation: false`; the mongod container gets none — it runs as root with unbounded resources on the shared kind node. Acceptable for local dev, inconsistent with the chart's own security posture.
**Fix:** Add a `resources:` block sourced from `.Values.mongodb.resources` and at minimum `allowPrivilegeEscalation: false` on the container.

### IN-05: POST delete of a non-existent service redirects 302 instead of 404 (carried forward)

**File:** `apps/launchpad/app/routes/pages.py:98-105`
**Issue:** `GET /catalog/<name>/delete` 404s when the service is absent, but `POST` for the same absent name silently redirects to `/catalog`. The DB-error and not-found cases are also indistinguishable (`deregister_service` collapses both to `False`). Inconsistent surface; benign in effect.
**Fix:** Mirror the confirm route (`if catalog.get_service(name) is None: abort(404)`), or document the idempotent-delete semantics.

### IN-06: Form-level generic save error is attached to the Name field (carried forward)

**File:** `apps/launchpad/app/routes/pages.py:73`
**Issue:** `form.name.errors.append(message)` is right for the duplicate-name copy, but when `register_service` fails generically (DB down) "Could not save this service. Check the fields below…" also lands under the Name field — implying a field problem the user cannot fix, and triggering `first_error_field` autofocus on Name.
**Fix:** Route the generic failure to a form-level slot (`form.form_errors` in WTForms 3.x, or a dedicated template variable above the fields); keep only `DUPLICATE_NAME_ERROR` on `form.name.errors`.

### IN-07: Exact-whitespace HTML assertion is brittle (carried forward)

**File:** `apps/launchpad/tests/test_partials.py:49`
**Issue:** `assert 'status-card status-card--degraded">\n  <header>Field Guide API</header>' in body` couples the test to the template's exact newline/indentation. Any whitespace-only reformat of `status_cards.html` breaks it — flaky-by-construction (flagged per the test-reliability exception).
**Fix:** Assert structurally, e.g. `re.search(r'status-card--degraded"\s*>\s*<header>Field Guide API</header>', body)`.

### IN-08: CR-01 regression tests use deprecated `datetime.utcnow()` (NEW)

**File:** `apps/launchpad/tests/test_events.py:259,264`
**Issue:** `datetime.utcnow()` is deprecated as of Python 3.12 (scheduled for removal). The project pins Python 3.11 so it currently emits no warning, but a runtime bump or a `filterwarnings = error` pytest posture will turn these two regression tests into failures for a reason unrelated to what they protect.
**Fix:** Produce the naive datetime explicitly: `datetime.now(timezone.utc).replace(tzinfo=None)` — same value, no deprecated API, and self-documenting about the naivety being intentional.

---

_Reviewed: 2026-07-13T11:26:09Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
