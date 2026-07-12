---
phase: 09-service-catalog-events-mongodb-crud
reviewed: 2026-07-12T21:43:19Z
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
  critical: 1
  warning: 5
  info: 7
  total: 13
status: issues_found
---

# Phase 9: Code Review Report

**Reviewed:** 2026-07-12T21:43:19Z
**Depth:** standard
**Files Reviewed:** 33
**Status:** issues_found

## Summary

Reviewed the Phase 9 service catalog + events feed implementation: Flask route/repository/form layers, Jinja templates, the test suite, and the Helm chart additions (in-cluster MongoDB manifests, app Secret/ConfigMap wiring). The overall structure is disciplined — never-raise repo helpers, dict-encoded Mongo queries (no injection surface), CSRF on all POSTs, locked copy strings, unique-index-as-enforcement-boundary for name uniqueness, and a coherent chart with correct selector separation between app and MongoDB pods.

One production-correctness bug survived the test suite: relative timestamps ("2 minutes ago") will render as "unknown" for every event read from a real MongoDB, because PyMongo returns timezone-naive datetimes by default and `_relative_time()` swallows the resulting `TypeError`. Tests pass only because mongomock preserves tzinfo and the partial tests inject tz-aware fakes. Additional warnings concern chart config drift (`mongoUri` hardcodes hostname + credentials that the helper docs claim are single-sourced), an import-time crash path in config parsing, an ignored `persistence.enabled` knob, a stored-URL scheme gap on the detail page, and an event-row fallback that mislabels unknown event types.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Relative event times render "unknown" for all events read from real MongoDB (tz-naive datetimes)

**File:** `apps/launchpad/app/events.py:126` (root cause surfaced here), `apps/launchpad/app/__init__.py:49-52` (fix site)
**Issue:** `record_event()` stores tz-aware `datetime.now(timezone.utc)` values, but PyMongo (and therefore Flask-PyMongo) decodes BSON dates as **timezone-naive** datetimes by default (`tz_aware=False`, no `tz_aware` option is set anywhere in the app — verified by grep). So in production every `event["ts"]` returned by `list_recent_events()` / `get_events_for_service()` is naive, and at `events.py:126` `datetime.now(timezone.utc) - ts` raises `TypeError: can't subtract offset-naive and offset-aware datetimes`, which the blanket `except Exception` at line 141 swallows into `"unknown"`. Result: the Activity Feed and the detail page's Related Events show "unknown" for 100% of real events — the FEED-01 Event-Row Anatomy's relative-time element silently never works outside tests. The test suite cannot catch this: mongomock stores/returns Python datetime objects without a BSON round-trip (tzinfo preserved), and `test_partials.py` injects tz-aware fake events directly. `test_relative_time_*` tests also only pass tz-aware inputs.
**Fix:** Either enable tz-aware decoding at init time:
```python
# apps/launchpad/app/__init__.py
mongo.init_app(
    app,
    serverSelectionTimeoutMS=app.config["MONGO_SERVER_SELECTION_TIMEOUT_MS"],
    tz_aware=True,
)
```
or (more defensive, no driver-wide behavior change) normalize inside `_relative_time`:
```python
# apps/launchpad/app/events.py, inside the try block before subtraction
if ts.tzinfo is None:
    ts = ts.replace(tzinfo=timezone.utc)  # PyMongo returns naive UTC by default
delta = datetime.now(timezone.utc) - ts
```
Add a regression test that passes a **naive** UTC datetime to `_relative_time()` and asserts a real value (e.g. "just now"), not "unknown".

## Warnings

### WR-01: `mongoUri` default hardcodes the MongoDB hostname and duplicates credentials — desyncs from the helper and from `mongodb.auth.password`

**File:** `charts/launchpad/values.yaml:72`, `charts/launchpad/templates/secret.yaml:18`, `charts/launchpad/templates/_helpers.tpl:38-43`
**Issue:** `_helpers.tpl` declares `launchpad.mongodb.fullname` as the "SINGLE source of truth" used by "templates/secret.yaml (MONGO_URI hostname)" — but `secret.yaml` does not use the helper at all; it renders `.Values.mongoUri` verbatim, whose default hardcodes `launchpad-mongodb` and `launchpad-dev-password`. Two failure modes: (1) installing with any release name other than `launchpad` produces a Service named `<release>-launchpad-mongodb` while the app still dials `launchpad-mongodb` — connection failure with only a values-file comment as mitigation; (2) `--set mongodb.auth.password=<real>` rotates the Mongo root password but the app keeps authenticating with the stale password embedded in `mongoUri` — auth failure unless the operator remembers to update two coupled values in lockstep.
**Fix:** Compose the URI in the template from the single sources of truth and keep `mongoUri` only as an optional explicit override:
```yaml
# charts/launchpad/templates/secret.yaml
stringData:
  MONGO_URI: {{ .Values.mongoUri | default (printf "mongodb://%s:%s@%s:27017/%s?authSource=admin&serverSelectionTimeoutMS=2000" .Values.mongodb.auth.username .Values.mongodb.auth.password (include "launchpad.mongodb.fullname" .) .Values.mongodb.auth.database) | quote }}
```
and set `mongoUri: ""` in values.yaml.

### WR-02: Detail page renders stored `repo_url` as a raw href — no scheme re-check at the render boundary

**File:** `apps/launchpad/app/templates/detail.html:12`
**Issue:** `<a href="{{ service.repo_url }}">` trusts that every document in `services` passed through `ServiceForm`'s `^https?://` regexp. The form is the only enforcement boundary — any document written directly to MongoDB (mongosh seeding, a future import endpoint, another platform component sharing the DB) can carry `javascript:alert(1)` as `repo_url`, and Jinja autoescaping does not neutralize a `javascript:` scheme inside an href (it only escapes HTML metacharacters). That is a stored-XSS vector one write away.
**Fix:** Add defense in depth at the render or read boundary, e.g. in the template:
```jinja
{% if service.repo_url and service.repo_url.startswith(('http://', 'https://')) %}
<dd><a href="{{ service.repo_url }}" rel="noopener noreferrer">{{ service.repo_url }}</a></dd>
{% else %}
<dd>{{ service.repo_url or '—' }}</dd>
{% endif %}
```
or validate the scheme in `catalog.register_service()` so the invariant holds at the data layer regardless of the write path.

### WR-03: Malformed `EVENTS_TTL_SECONDS` env var crashes the app at import time

**File:** `apps/launchpad/app/config.py:55`
**Issue:** `EVENTS_TTL_SECONDS: int = int(os.environ.get("EVENTS_TTL_SECONDS", "604800"))` executes at class-body (module import) time. A malformed value (e.g. `"7d"`, `"604800 "` is fine but `"1e6"` is not) raises `ValueError` while importing `app.config`, before `create_app()` runs — gunicorn workers crash-loop on boot with a traceback instead of degrading. This is the only config value with an import-time crash path; every other consumer in the codebase (catalog/events helpers) follows a never-raise discipline. The chart makes typos easy: `eventsTtlSeconds` is a free-form string in values.yaml.
**Fix:**
```python
try:
    EVENTS_TTL_SECONDS: int = int(os.environ.get("EVENTS_TTL_SECONDS", "604800"))
except ValueError:
    EVENTS_TTL_SECONDS = 604800  # fall back to 7-day default on malformed env
```

### WR-04: Event-row template mislabels any unknown event type as "Platform started"

**File:** `apps/launchpad/app/templates/partials/event_row.html:19-24`
**Issue:** The `{% else %}` branch is the catch-all: any event whose `type` is not `service_registered` / `service_deregistered` — including malformed documents and every future event type (deploys, scans, etc. are on the roadmap for this IDP) — renders with the "Platform started" label. That is silently wrong data shown to the user the moment a fourth event type exists, and nothing will fail loudly.
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

### WR-05: `mongodb.persistence.enabled` is a dead knob — PVC and volume are rendered unconditionally

**File:** `charts/launchpad/templates/mongodb/pvc.yaml:1`, `charts/launchpad/templates/mongodb/deployment.yaml:61-67`, `charts/launchpad/values.yaml:59`
**Issue:** `values.yaml` exposes `mongodb.persistence.enabled: true`, but no template ever reads it — `pvc.yaml` and the deployment's `volumeMounts`/`volumes` are gated only on `mongodb.enabled`. An operator setting `persistence.enabled: false` (e.g. for a throwaway CI cluster) still gets a PVC that sits Pending on clusters without a default StorageClass, blocking the mongod pod from scheduling — the exact opposite of what disabling persistence should do.
**Fix:** Either honor the flag (`{{- if and .Values.mongodb.enabled .Values.mongodb.persistence.enabled }}` in pvc.yaml, plus an `emptyDir` fallback for the `data` volume in deployment.yaml), or delete the `enabled` key from values.yaml so the schema doesn't advertise a capability the chart doesn't have.

## Info

### IN-01: Templates call the private `events._relative_time()` via a module passed into render context

**File:** `apps/launchpad/app/routes/pages.py:84-86`, `apps/launchpad/app/routes/partials.py:73-74`, `apps/launchpad/app/templates/partials/event_row.html:8,17,23`
**Issue:** The whole `events` module is injected as a template variable so Jinja can call an underscore-private function. This leaks module internals into the view layer and forces every route that includes `event_row.html` to remember to pass `events=events` (forgetting it produces a runtime `UndefinedError` only when an event renders).
**Fix:** Register it once as a Jinja filter/global in `create_app()` (`app.jinja_env.filters["relative_time"] = events._relative_time`) and use `{{ event.ts | relative_time }}`; drop the `events=` kwargs.

### IN-02: `registered_at` is stamped in two places

**File:** `apps/launchpad/app/routes/pages.py:67`, `apps/launchpad/app/catalog.py:77`
**Issue:** The route sets `registered_at` in the document and `register_service()` also `setdefault`s it. Harmless today, but two owners of one invariant invite drift.
**Fix:** Remove the route-level stamp; let the repository (`register_service`) be the single owner, as its docstring already claims.

### IN-03: `mongodb.auth.database` value is unused

**File:** `charts/launchpad/values.yaml:57`
**Issue:** No template references `.Values.mongodb.auth.database`; the DB name lives only inside the hardcoded `mongoUri` path. Dead config that suggests a wiring that doesn't exist.
**Fix:** Reference it when composing `MONGO_URI` (see WR-01 fix) or remove it.

### IN-04: MongoDB container has no resources and no securityContext

**File:** `charts/launchpad/templates/mongodb/deployment.yaml:34-63`
**Issue:** The app container gets requests/limits, `runAsNonRoot`, and `allowPrivilegeEscalation: false`; the mongod container gets none of these — it runs as root with unbounded resources on the shared kind node. Acceptable for local dev, inconsistent with the chart's own security posture.
**Fix:** Add a `resources:` block sourced from `.Values.mongodb.resources` and at minimum `allowPrivilegeEscalation: false` on the container.

### IN-05: POST delete of a non-existent service redirects 302 instead of 404

**File:** `apps/launchpad/app/routes/pages.py:98-105`
**Issue:** `GET /catalog/<name>/delete` 404s when the service is absent, but `POST /catalog/<name>/delete` for the same absent name silently redirects to `/catalog`. The DB-error case and the not-found case are also indistinguishable (`deregister_service` collapses both to `False`). Inconsistent surface; benign in effect.
**Fix:** Mirror the confirm route: `if catalog.get_service(name) is None: abort(404)` before deleting, or accept and document the idempotent-delete semantics.

### IN-06: Form-level generic save error is attached to the Name field

**File:** `apps/launchpad/app/routes/pages.py:73`
**Issue:** `form.name.errors.append(message)` is correct for the duplicate-name copy, but when `register_service` fails generically (DB down) the message "Could not save this service. Check the fields below…" also lands under the Name field — implying a field problem the user cannot fix by editing fields, and triggering the `first_error_field` autofocus on Name.
**Fix:** Route the generic failure to a form-level slot (`form.form_errors` in WTForms 3.x, or a dedicated template variable rendered above the fields) and keep only `DUPLICATE_NAME_ERROR` on `form.name.errors`.

### IN-07: Exact-whitespace HTML assertion is brittle

**File:** `apps/launchpad/tests/test_partials.py:49`
**Issue:** `assert 'status-card status-card--degraded">\n  <header>Field Guide API</header>' in body` couples the test to the template's exact newline/indentation. Any whitespace-only reformat of `status_cards.html` breaks it — a flaky-by-construction pattern (flagged per the test-reliability exception).
**Fix:** Assert structurally instead, e.g. regex `re.search(r'status-card--degraded"\s*>\s*<header>Field Guide API</header>', body)` or parse with a lightweight HTML check.

---

_Reviewed: 2026-07-12T21:43:19Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
