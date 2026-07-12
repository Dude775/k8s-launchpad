---
phase: 09-service-catalog-events-mongodb-crud
verified: 2026-07-13T00:00:00Z
status: gaps_found
score: 6/6 roadmap success criteria verified; 1 critical production-correctness gap found outside literal SC wording
overrides_applied: 0
gaps:
  - truth: "FEED-01 Event-Row Anatomy relative-time element renders a real value ('2 minutes ago' style) for events read from the platform's own in-cluster MongoDB"
    status: failed
    reason: "app/events.py:_relative_time() subtracts a tz-aware datetime.now(timezone.utc) from the timestamp read back from MongoDB without normalizing tzinfo. flask_pymongo/PyMongo decodes BSON dates as timezone-naive by default (no tz_aware=True set anywhere in app/__init__.py's mongo.init_app() call). The naive-minus-aware subtraction raises TypeError, which the blanket except Exception at events.py:141 swallows into the 'unknown' fallback. Reproduced directly: _relative_time(datetime.utcnow()) == 'unknown' vs _relative_time(datetime.now(timezone.utc)) == 'just now'. Confirmed no test in test_events.py or test_partials.py exercises a naive-datetime input — all 8 _relative_time tests and all mongomock-backed integration tests use tz-aware timestamps, and mongomock (unlike real PyMongo) preserves tzinfo without a BSON round-trip, so the entire test suite is structurally blind to this path. Because Phase 9 co-delivers DEP-03 (launchpad's own real in-cluster MongoDB), this is not a hypothetical future regression — it will reproduce on every event rendered by the live deployment starting with the very first real service_registered/service_deregistered/platform_started event. The provided live-deploy evidence (pods READY, /health 200, /api/status service_count 0) did not exercise event rendering against real Mongo (no service was registered), so it did not catch this."
    artifacts:
      - path: "apps/launchpad/app/events.py"
        issue: "_relative_time() (line 116-142) does not normalize naive datetimes before subtracting from an aware datetime.now(timezone.utc); root cause is app/__init__.py's mongo.init_app() not passing tz_aware=True"
    missing:
      - "Either pass tz_aware=True to mongo.init_app() in apps/launchpad/app/__init__.py, or normalize ts.tzinfo is None inside _relative_time() before the subtraction"
      - "A regression test in test_events.py that passes a naive UTC datetime to _relative_time() and asserts a real relative-time string, not 'unknown'"
---

# Phase 9: Service Catalog + Events Feed + MongoDB CRUD Verification Report

**Phase Goal:** Developers can register, view, and deregister services through the dashboard; every platform action writes to a bounded events feed backed by its own in-cluster MongoDB
**Verified:** 2026-07-13
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `GET /catalog` lists services from MongoDB; `POST /catalog/new` with valid input persists, fires `service_registered`, redirects to catalog with new entry visible | VERIFIED | `app/routes/pages.py:catalog_list`/`catalog_new` call `catalog.list_services()`/`catalog.register_service()` + `events.record_event("service_registered", ...)`; `test_catalog_new_post_valid_registers_and_redirects` and `test_catalog_new_post_valid_persists_document` pass (126/126 suite green) |
| 2 | Invalid/missing required fields re-render form with field-level errors and CSRF intact — no document written | VERIFIED | `ServiceForm` validators in `app/forms.py`; `catalog_new()` re-renders `onboard_form.html` with same form object on `validate_on_submit()` failure; `test_catalog_new_post_invalid_rerenders_without_calling_register` asserts `register_service` NOT called; CSRF wiring proven live by `test_onboard_form_rejects_missing_csrf_token` |
| 3 | `GET /catalog/<id>` shows full registration fields and that service's related events | VERIFIED | `catalog_detail()` renders `detail.html` with `service` + `events.get_events_for_service(name)`; shared `partials/event_row.html` reused; `test_catalog_detail_shows_registration_and_events` passes |
| 4 | Deregistering (after confirmation) removes from MongoDB and fires `service_deregistered` visible in feed | VERIFIED | `catalog_delete_confirm()` (GET, zero-JS confirm page) + `catalog_delete()` (POST) call `catalog.deregister_service()` then `events.record_event("service_deregistered", name)`; `test_catalog_delete_post_removes_and_redirects` confirms doc removed and event fired |
| 5 | `events` collection has TTL index on `ts`; `make test-launchpad` passes (mongomock-backed); suite documents TTL expiry is verified live via smoke, not unit tests | VERIFIED | `events.ensure_indexes()` calls `create_index("ts", expireAfterSeconds=...)`; `test_ensure_indexes_ttl_expire_after_seconds_default` asserts `index_information()["ts_1"]["expireAfterSeconds"] == 604800`; `conftest.py` documents the mongomock TTL non-expiry limitation; independently re-ran `pytest --cov=app --cov-fail-under=100` → 126 passed, 100% coverage |
| 6 | launchpad Helm chart embeds `mongo:7` manifests in `charts/launchpad/templates/mongodb/` with database `launchpad`; field-guide-api chart untouched | VERIFIED | Independently ran `helm lint charts/launchpad/` → 0 failures (1 informational icon notice only); `helm template` renders a second `mongo:7` Deployment + `27017` ClusterIP Service; `values.yaml` `mongodb.auth.database: launchpad`; `git status --short charts/field-guide-api/` prints nothing |

**Score:** 6/6 roadmap Success Criteria verified as literally worded.

**Note on Truth 3/4 in production:** while the events ARE shown on the detail page and feed, their relative-time display degrades to "unknown" against real MongoDB — see Gap below. This does not violate the literal SC wording (events are still visible/present) but undermines the FEED-01 contract's Event-Row Anatomy in the live deployment this phase's own DEP-03 work enables.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/launchpad/app/catalog.py` | never-raise CRUD helper | VERIFIED | `ensure_indexes/list_services/get_service/register_service/deregister_service` all present, never-raise, 100% covered |
| `apps/launchpad/app/events.py` | never-raise events helper | VERIFIED (with defect) | All interface functions present and wired; `_relative_time` substantive but produces wrong output for real-Mongo naive datetimes (CR-01) |
| `apps/launchpad/app/forms.py` | `ServiceForm` with locked validators/copy | VERIFIED | Regexp/URL/Length/DataRequired validators match UI-SPEC locked copy exactly; scheme-restriction rejects `javascript:`/`ftp:` |
| `apps/launchpad/app/routes/pages.py` | real catalog CRUD routes | VERIFIED | `catalog_list/catalog_new/catalog_detail/catalog_delete_confirm/catalog_delete`, module-attribute imports (`from app import catalog, events`) confirmed, no direct-name imports |
| `apps/launchpad/app/routes/partials.py` | `/partials/feed` fragment/full-page | VERIFIED | HX-Request branch mirrors existing status-cards/cluster-state pattern |
| Seven templates (catalog, onboard_form, detail, confirm_delete, feed, feed_full_page, event_row, feed_events) | real markup, no placeholders | VERIFIED | All read directly; no stub/placeholder copy; anti-pattern grep clean |
| `charts/launchpad/templates/mongodb/{deployment,pvc,secret,service}.yaml` | mongo:7 manifests | VERIFIED | All four files present; `helm template` renders `mongo:7` Deployment + Service on 27017 |
| `charts/launchpad/templates/_helpers.tpl` | `launchpad.mongodb.fullname` + `launchpad.mongodb.selectorLabels` | VERIFIED | Both helpers defined; selector labels distinct from app `launchpad.selectorLabels` (grep confirms `-mongodb` suffix) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `pages.py` | `app.catalog`/`app.events` | module-attribute calls | WIRED | `from app import catalog, events`; no `from app.catalog import` / `from app.events import` direct-name imports found (grep-verified; only a docstring comment mentions the pattern to avoid) |
| `catalog.py` | `mongo.db.services` | insert_one/find/delete_one + unique index | WIRED | Confirmed in source; unique index created via `create_index("name", unique=True)` |
| `events.py` | `mongo.db.events` | insert_one/find sorted by ts + TTL index | WIRED | Confirmed; TTL index test asserts `expireAfterSeconds == 604800` |
| `feed.html` | `partials.feed` | hx-get visibility-guarded 15s poll | WIRED | `hx-get="{{ url_for('partials.feed') }}"`, `every 15s [document.visibilityState === 'visible']` present; `every 10s` absent |
| `detail.html` | `partials/event_row.html` | include in loop | WIRED | `{% include "partials/event_row.html" %}` present, shared with `feed_events.html` |
| `values.yaml (mongoUri)` | `launchpad.mongodb.fullname` Service hostname | in-cluster DNS string | WIRED (hardcoded, not templated) | Functional for default release name; WR-01 (chart review) flags this as a plain string rather than composed via the helper — a maintainability/drift risk, not a functional break for the default install |
| `deployment.yaml` | `SECRET_KEY`/`EVENTS_TTL_SECONDS` | secretKeyRef/configMapKeyRef | WIRED | Confirmed via `helm template` output — both env vars present with correct refs |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `catalog.html` | `services` | `catalog.list_services()` → `mongo.db.services.find()` | Yes | FLOWING |
| `detail.html` | `events_for_service` | `events.get_events_for_service(name)` → `mongo.db.events.find(...)` | Yes | FLOWING |
| `partials/feed_events.html` | `events_list` | `events.list_recent_events()` → `mongo.db.events.find().sort(...)` | Yes | FLOWING |
| `partials/event_row.html` | `events._relative_time(event.ts)` | timestamp from a real MongoDB read (naive datetime) | **No — reproducibly wrong** | ⚠️ HOLLOW — the row itself renders (glyph, label, service link all correct) but the relative-time cell silently degrades to "unknown" for every event once `events.ts` originates from real (non-mongomock) MongoDB |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite passes at 100% coverage | `.venv/Scripts/python -m pytest --cov=app --cov-fail-under=100 -q` (run independently, not trusting SUMMARY claim) | 126 passed, TOTAL coverage 100.00% | PASS |
| `helm lint` passes | `helm lint charts/launchpad/` (run independently) | 1 chart linted, 0 failed (1 INFO: missing icon) | PASS |
| `helm template` renders mongo:7 + app Deployments, SECRET_KEY/EVENTS_TTL_SECONDS env, database `launchpad` | `helm template launchpad charts/launchpad/` | Confirmed both Deployments, Service on 27017, `mongodb.auth.database: launchpad`, `mongoUri` targets `launchpad-mongodb` | PASS |
| `git status --short charts/field-guide-api/` empty (untouched) | `git status --short charts/field-guide-api/` | (empty output) | PASS |
| CR-01 reproduction: naive datetime → `_relative_time` == "unknown"; aware datetime → real value | `python -c "... _relative_time(datetime.utcnow()) vs _relative_time(datetime.now(timezone.utc))"` | naive → `'unknown'`; aware → `'just now'` | CONFIRMED (defect reproduced) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CAT-01 | 09-02 | View service catalog listing | SATISFIED | `catalog_list()` + `catalog.html` table/empty-state |
| CAT-02 | 09-01, 09-02 | Onboard a service via form, persists to MongoDB | SATISFIED | `ServiceForm` + `catalog.register_service()` + `catalog_new()` POST path |
| CAT-03 | 09-01, 09-02 | Server-side validation (CSRF-protected), re-render with field errors | SATISFIED | CSRF-enabled test + invalid-submit re-render test both pass |
| CAT-04 | 09-02 | Service detail page: registration + related events | SATISFIED | `catalog_detail()` + `detail.html` (events display, though relative-time degrades — see gap) |
| CAT-05 | 09-02 | Deregister after confirmation | SATISFIED | `catalog_delete_confirm()` (zero-JS) + `catalog_delete()` POST |
| FEED-01 | 09-01 (helper), 09-02 (route) | Activity/events feed, newest-first, persisted MongoDB collection | PARTIALLY SATISFIED | Feed route/template/data flow all real and wired; the "2 minutes ago"-style relative-time element of the Event-Row Anatomy contract fails against real MongoDB (CR-01) |
| FEED-02 | 09-01, 09-02 | platform_started / service_registered / service_deregistered all write events | SATISFIED | `emit_platform_started_once()`, and both catalog routes call `events.record_event()` on success |
| FEED-03 | 09-01 | TTL-bounded events collection | SATISFIED | TTL index test + `EVENTS_TTL_SECONDS` config plumbed through chart ConfigMap |
| DEP-03 | 09-03 | In-cluster MongoDB via mirrored mongo:7 manifests, field-guide-api untouched | SATISFIED | Chart artifacts verified independently; live-deploy evidence (pods READY, /health 200) provided and consistent with SUMMARY claims |

No orphaned requirements — all 9 IDs from REQUIREMENTS.md Phase 9 rows are claimed across the three plans' frontmatter.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `apps/launchpad/app/events.py` | 126, `__init__.py` 49-52 | Broad `except Exception` masking a real `TypeError` from naive/aware datetime subtraction (CR-01, confirmed via code review + independent reproduction) | Blocker-level correctness defect (not a debt marker; no TODO/FIXME present) | Every event rendered against real MongoDB shows "unknown" instead of a relative timestamp — a silent, untested, production-only failure mode |
| `charts/launchpad/values.yaml:72` | — | `mongoUri` hardcodes hostname+credentials instead of composing via `launchpad.mongodb.fullname`/`mongodb.auth.*` (WR-01, code review) | Warning | Two-value desync risk on password rotation or non-default release name; does not block default-path functionality |
| `apps/launchpad/app/templates/detail.html:12` | 12 | `repo_url` rendered as raw href with no scheme re-check at render boundary (WR-02, code review) | Warning | Stored-XSS vector if a document ever bypasses `ServiceForm` (e.g. direct DB write); form itself does enforce scheme today |
| `apps/launchpad/app/config.py:55` | 55 | `EVENTS_TTL_SECONDS` int() parse at import time, no try/except (WR-03, code review) | Warning | Malformed env var crash-loops gunicorn at boot instead of degrading; breaks the never-raise discipline used everywhere else |
| `apps/launchpad/app/templates/partials/event_row.html:19-24` | 19-24 | Catch-all `{% else %}` labels any unrecognized event type as "Platform started" (WR-04, code review) | Warning | Silently mislabels data the moment a future event type is introduced |
| `charts/launchpad/templates/mongodb/pvc.yaml`, `values.yaml:59` | — | `mongodb.persistence.enabled` flag is declared but never read by any template (WR-05, code review) | Warning | Dead config knob; disabling persistence has no effect, contrary to what the values schema implies |

All 5 warnings from the code review (09-REVIEW.md) were independently confirmed present in the current code during this verification pass.

### Human Verification Required

None — all success criteria and the CR-01 defect are independently confirmable by code/test inspection and reproduction; no visual/UX/real-time judgment call remains open. The live-deploy evidence already provided (pods READY 1/1, /health 200, /api/status clean) is accepted as sufficient for DEP-03's infra claim.

### Gaps Summary

All 6 literal Success Criteria from the roadmap are verified true in the codebase — the CRUD flows, form validation, CSRF, TTL index, and Helm chart mirroring all function and are test-covered. Independent test-suite and `helm lint`/`helm template` re-runs confirm the SUMMARY's claims rather than merely trusting them.

However, one Critical code-review finding (CR-01) is a genuine, reproduced, unmitigated production-correctness defect that this verification independently confirmed in the source: `events._relative_time()` will render "unknown" instead of a real relative timestamp for every single event once the app is reading from its own real in-cluster MongoDB — which is exactly the environment DEP-03 (also delivered in this phase) stands up. The bug is invisible to the entire test suite because mongomock preserves `tzinfo` without a BSON round-trip and no test constructs a naive-datetime input. The live-deploy evidence provided for this phase did not exercise event rendering (service_count was 0, no registration was performed against real Mongo), so it did not catch the defect either.

This does not violate the literal wording of any of the 6 roadmap Success Criteria (events are still recorded and displayed — only their timestamp degrades), so it is reported as a gap rather than a Success-Criteria FAIL. Given it is rated Critical by the code review, is fully reproduced here, has zero test coverage of the failing path, and directly undermines the FEED-01 Event-Row Anatomy contract the moment this phase's own MongoDB goes live, it should be closed before the milestone is considered done — either via a small closure plan or an explicit override if the team accepts shipping with degraded timestamps for now.

**This looks like an unintentional gap, not a deliberate deviation** — no override is suggested; recommend a small closure plan (one-line fix in `app/__init__.py`'s `mongo.init_app(tz_aware=True)` call, or a normalization guard in `_relative_time`, plus one regression test with a naive-datetime input).

---

_Verified: 2026-07-13_
_Verifier: Claude (gsd-verifier)_
