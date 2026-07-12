---
phase: 09-service-catalog-events-mongodb-crud
plan: 01
subsystem: backend-data-layer
tags: [flask-wtf, csrf, wtforms, pymongo, mongomock, ttl-index, unique-index, tdd]
requires:
  - phase: 07-status-api-field-guide-integration
    provides: mongo singleton + app factory wiring (extensions.py, __init__.py)
  - phase: 08-helm-chart-k8s-diagnostics
    provides: module-attribute import discipline (plan-check BLOCKER 3 lesson)
provides:
  - "app.catalog: never-raise repo helper (ensure_indexes/list_services/get_service/register_service/deregister_service)"
  - "app.events: never-raise events helper (ensure_indexes/record_event/list_recent_events/get_events_for_service/emit_platform_started_once/reset_platform_started_guard_for_tests/_relative_time)"
  - "app.forms.ServiceForm: D-01/D-02 validation schema with UI-SPEC locked error copy"
  - "csrf CSRFProtect singleton wired in create_app() (D-04)"
  - "config keys SECRET_KEY + EVENTS_TTL_SECONDS (D-05, D-10)"
  - "startup index creation: unique services.name + TTL events.ts (604800 default)"
affects:
  - 09-02 (routes/templates consume catalog/events/ServiceForm contracts)
  - 09-03 (chart Secret carries SECRET_KEY; ConfigMap carries EVENTS_TTL_SECONDS)
tech-stack:
  added:
    - Flask-WTF==1.3.0 (WTForms 3.2.2 transitive)
  patterns:
    - never-raise helper modules (status.py shape) extended to CRUD
    - module-level once-per-process guard with test reset hook (D-12)
    - PyMongo.init_app monkeypatch in conftest so startup Mongo ops stay in mongomock
key-files:
  created:
    - apps/launchpad/app/catalog.py
    - apps/launchpad/app/events.py
    - apps/launchpad/app/forms.py
    - apps/launchpad/tests/test_catalog.py
    - apps/launchpad/tests/test_events.py
  modified:
    - apps/launchpad/requirements.txt
    - apps/launchpad/app/extensions.py
    - apps/launchpad/app/config.py
    - apps/launchpad/app/__init__.py
    - apps/launchpad/tests/conftest.py
    - apps/launchpad/tests/test_factory.py
decisions:
  - "register_service stamps registered_at via setdefault so list_services' sort key always exists"
  - "repo_url scheme restriction = Regexp(^https?://) layered before URL(require_tld=True), one shared locked error string"
  - "conftest patches PyMongo.init_app (not post-hoc cx/db) so create_app's startup Mongo ops are hermetic and fast"
  - "name-format error copy uses UI-SPEC en dash (2–40), overriding the plan action text's hyphen typo per locked-copy acceptance criteria"
metrics:
  duration: "~10 min active execution post-approval (checkpoint span 2026-07-12 -> 2026-07-13)"
  tasks: 3
  tests: "106 passed, 100% coverage"
  completed: "2026-07-13"
---

# Phase 9 Plan 01: Data + Validation Foundation Summary

Never-raise catalog/events Mongo helpers with unique-name and 7-day-TTL indexes created at startup, CSRFProtect wired via Flask-WTF 1.3.0, and a ServiceForm whose validators and error copy are the UI-SPEC locked contract — all mongomock-tested at 100% coverage.

## Tasks Completed

| Task | Name | Commit(s) | Key Files |
| ---- | ---- | --------- | --------- |
| 1 | Flask-WTF provenance gate + pin (T-09-SC) | 23b2ebe | requirements.txt |
| 2 | catalog/events helpers, config keys, CSRF singleton, factory wiring (TDD) | 436bb8d (RED), 8744511 (GREEN) | catalog.py, events.py, extensions.py, config.py, __init__.py, conftest.py, test_catalog.py, test_events.py |
| 3 | ServiceForm validation schema with locked copy (TDD) | 4a9d922 (RED), 5b77347 (GREEN) | forms.py, test_catalog.py |

## What Was Built

- **`app/catalog.py`** — bare never-raise repo helper (no Blueprint): `ensure_indexes()` (unique index on `services.name`, idempotent), `list_services()` (newest-registered first, `[]` on failure), `get_service()` (dict-encoded equality match, `None` on absent/failure), `register_service()` (stamps `registered_at`, translates `DuplicateKeyError` into the locked "This name is already registered — choose another." copy, generic failures into the locked form-level copy), `deregister_service()` (`deleted_count == 1`).
- **`app/events.py`** — never-raise events helper: `record_event()` writes `{type, service_name, ts}` and returns False on failure so a feed-write failure never blocks a catalog mutation; `list_recent_events(limit=50)` / `get_events_for_service()` newest-first; `ensure_indexes()` TTL index on `ts` with config-driven `expireAfterSeconds` (default 604800); `emit_platform_started_once()` module-flag guard that only latches when the write succeeded (D-12 "first readiness"); `reset_platform_started_guard_for_tests()`; `_relative_time()` mirroring `cluster_state._pod_age` ("just now" / "N minutes|hours|days ago" / "unknown").
- **`app/forms.py`** — `ServiceForm(FlaskForm)`: name `Regexp(^[a-z0-9-]{2,40}$)`, repo_url `URLField` with `Regexp(^https?://)` + `URL(require_tld=True)` (rejects `javascript:`/`ftp:` schemes, T-09-01), owner `DataRequired` + `Length(max=100)`, optional description, environment select (dev/staging/prod, default dev). All error strings are character-for-character UI-SPEC Copywriting Contract copy.
- **Factory wiring** — `csrf.init_app(app)` after metrics, `WTF_CSRF_TIME_LIMIT=None`; after blueprint registration, deferred `from app import catalog, events` then `catalog.ensure_indexes(); events.ensure_indexes(); events.emit_platform_started_once()` inside `app.app_context()` (needed because `events.ensure_indexes()` reads `current_app.config`).
- **Test harness** — `app` fixture now monkeypatches `PyMongo.init_app` to install mongomock BEFORE `create_app()`, wipes the startup `platform_started` event, and re-arms the guard; documents the mongomock TTL non-expiry limitation (no test sleeps then asserts an events count change).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Worktree recreated after checkpoint teardown**
- **Found during:** resume after Task 1 human-verify approval
- **Issue:** original worktree/branch were force-removed while the plan was paused at the package-legitimacy checkpoint
- **Fix:** recreated worktree + branch `worktree-agent-ad357f7d936b5578b` at spawn-time base `dfcd35b`; all commits land there
- **Files modified:** none (git plumbing only)

**2. [Rule 1 - Bug] Test fixture would have executed real-network Mongo ops at startup**
- **Found during:** Task 2 GREEN verification (fixture setup measured ~1.5s/test; 34-test subset took 41s)
- **Issue:** `create_app()` now performs three Mongo operations at startup, but the fixture patched mongomock in only AFTER `create_app()` — every test attempted real localhost:27017 connections (slow, and non-hermetic if a local MongoDB existed)
- **Fix:** fixture monkeypatches `PyMongo.init_app` so mongomock is installed before `create_app()` runs; startup ops (index creation + platform_started emit) execute in-memory; startup event wiped + guard re-armed for deterministic per-test state
- **Files modified:** apps/launchpad/tests/conftest.py
- **Commit:** 8744511 (subset runtime dropped 41s → 1.2s)

**3. [Rule 1 - Bug] test_factory.py direct create_app() calls slow + stale docstring**
- **Found during:** Task 2 GREEN
- **Issue:** two tests call `create_app()` without the fixture; with startup Mongo ops they each burned ~6s against PyMongo's 2s default timeout, and the "does not connect" docstring became false
- **Fix:** pass `MONGO_SERVER_SELECTION_TIMEOUT_MS: 10` overrides and update docstrings to describe the never-raise startup degradation these tests now also prove
- **Files modified:** apps/launchpad/tests/test_factory.py
- **Commit:** 8744511

### Discretion Decisions

- **registered_at stamping:** `register_service()` sets `registered_at` via `setdefault` so `list_services()`' sort key is guaranteed — the plan interface left the data dict to callers.
- **Locked-copy conflict resolved toward UI-SPEC:** the plan's Task 3 action text contained "(2-40 characters.)" (hyphen, misplaced period); acceptance criteria mandate character-for-character UI-SPEC copy, so "(2–40 characters)." (en dash) was implemented and asserted.
- **Subset verification commands use `--no-cov`:** pytest.ini's `addopts` enforce `--cov-fail-under=100` globally, which spuriously fails partial-file runs; full-suite runs keep the 100% gate.

## Verification Evidence

- Full suite: `python -m pytest` → **106 passed, TOTAL coverage 100%** (gate `--cov-fail-under=100` enforced by pytest.ini)
- `python -c "import app.catalog, app.events, app.forms"` → ok
- Grep gates: `mongo.db.services.create_index("name", unique=True)` × 1; `mongo.db.events.create_index("ts", expireAfterSeconds=` × 1; zero `from app.events import` / `from app.catalog import` direct-name imports anywhere in app/ or tests/
- `index_information()["ts_1"]["expireAfterSeconds"] == 604800` asserted (`test_ensure_indexes_ttl_expire_after_seconds_default`); no test sleeps then asserts expiry
- Guard: exactly one `platform_started` on first call, zero on second, one more after reset; flag NOT latched when `record_event` returns False

## TDD Gate Compliance

- Task 2: RED 436bb8d (`test(09-01)`) → GREEN 8744511 (`feat(09-01)`) — RED run failed on missing `app.catalog`/`app.events` (2 collection errors)
- Task 3: RED 4a9d922 (`test(09-01)`) → GREEN 5b77347 (`feat(09-01)`) — RED run failed 20/20 on missing `app.forms`
- No refactor commits needed

## Known Stubs

None — all helpers are wired to real (mongomock-tested) MongoDB collections; no placeholder values flow to any consumer.

## Threat Flags

None — all new surface (form validation boundary, CSRF signing key, Mongo query keys, TTL bounding) is covered by the plan's threat register (T-09-01..05, T-09-SC); no additional endpoints, auth paths, or schema changes were introduced.

## Auth Gates

Task 1 was a blocking package-legitimacy human-verify gate (not an auth gate): user approved Flask-WTF 1.3.0 / pallets-eco provenance before the pin was committed.

## Notes for 09-02

- Import discipline for routes: `from app import catalog, events` then call via module attribute — tests monkeypatch these functions directly.
- `catalog.DUPLICATE_NAME_ERROR` / `catalog.GENERIC_SAVE_ERROR` and the form message constants in `app/forms.py` are importable if templates/tests need the locked strings.
- Route tests should set `WTF_CSRF_ENABLED=False` per-test (fixture default leaves CSRF on); the one CSRF-enabled round-trip test per RESEARCH Pitfall 3 still needs writing in 09-02.
