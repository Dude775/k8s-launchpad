---
phase: 07-status-api-field-guide-integration
plan: 02
subsystem: api
tags: [flask, prometheus-flask-exporter, htmx, jinja2, requests, tdd]

# Dependency graph
requires:
  - phase: 07-status-api-field-guide-integration
    plan: 01
    provides: "mongo PyMongo singleton, MONGO_URI/FIELD_GUIDE_BASE_URL/APP_VERSION config keys, requests==2.34.2 pin, mongomock app/mongo_down/mock_requests_get test fixtures"
provides:
  - "get_platform_status() single-source-of-truth aggregation helper (app/status.py) consumed by both /api/status and /partials/status-cards"
  - "GET /api/status JSON route returning api_health, mongo_status, app_version, service_count, field_guide_reachable, metrics_preview — never 500s"
  - "GET /partials/status-cards HX-Request-aware routing: fragment for htmx, full page (status_full_page.html) for direct navigation"
  - "metrics_preview field reading prometheus_client.REGISTRY (the same registry backing /metrics) with a never-raise fallback"
  - "/metrics parity test locking in flask_http_request_total / flask_http_request_duration_seconds family names"
affects: [08-helm-chart-launchpad-deployment, 09-service-catalog-mongodb-crud]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared aggregation helper (get_platform_status()) consumed by both a JSON route and an HTML-rendering route to prevent JSON/UI drift"
    - "HX-Request header branching inside a single route (fragment vs full-page) — a deliberate, documented evolution of the prior phase's no-branch contract"
    - "metrics_preview reads the SAME prometheus_client.REGISTRY that backs /metrics rather than standing up a second registry"
    - "Every outbound requests.get() call to a sibling service carries a mandatory timeout= keyword, verified by both a grep gate and a unit test"

key-files:
  created:
    - apps/launchpad/app/status.py
    - apps/launchpad/app/routes/status.py
    - apps/launchpad/app/templates/status_full_page.html
    - apps/launchpad/tests/test_status.py
    - apps/launchpad/tests/test_metrics.py
  modified:
    - apps/launchpad/app/routes/partials.py
    - apps/launchpad/app/routes/__init__.py
    - apps/launchpad/app/__init__.py
    - apps/launchpad/app/templates/partials/status_cards.html
    - apps/launchpad/tests/test_partials.py
    - apps/launchpad/tests/conftest.py

key-decisions:
  - "Sourced FIELD_GUIDE_BASE_URL/APP_VERSION from flask.current_app.config rather than os.environ.get directly, per PATTERNS.md's flagged discretion point — consistent with the project's Config-class-as-source-of-truth convention and gives tests override control via config_overrides"
  - "metrics_preview test drives the flask_http_request Counter directly (via prometheus_client's collector registry) instead of relying on a fresh test-client request, because prometheus-flask-exporter's export_defaults() guards against duplicate metric registration on the shared global REGISTRY — once one test's app fixture has registered the defaults, later create_app() calls in the same pytest process silently skip re-wiring before/after-request instrumentation hooks for their own app instance. This is a pre-existing test-isolation property of the library + app-factory pattern, not a bug in this plan's code."
  - "service_count and app_version cards render unconditionally styled by overall api_health rather than their own independent status class, since neither field has its own up/down concept distinct from mongo/field-guide reachability"

patterns-established:
  - "Pattern: single aggregation helper feeding both a JSON API route and an HTML partial route — established here for status, to be reused by any future dual-representation endpoint"
  - "Pattern: HX-Request-aware single route (fragment vs full page) — the sanctioned way to add direct-navigation support to an existing htmx-fragment route without duplicating markup"

requirements-completed: [STAT-01, STAT-02, STAT-04]

# Metrics
duration: 34min
completed: 2026-07-10
---

# Phase 7 Plan 2: Status API + Field-Guide Integration Summary

**Shared get_platform_status() helper aggregates own-Mongo status, field-guide-api reachability (2s-timeout, exception-isolated), version, service count, and a metrics_preview read from the live Prometheus registry — feeding both the new GET /api/status JSON endpoint and an HX-Request-aware /partials/status-cards route that now renders real per-metric cards.**

## Performance

- **Duration:** 34 min
- **Started:** 2026-07-10T22:53:00Z
- **Completed:** 2026-07-10T23:27:33Z
- **Tasks:** 3 (2 TDD auto, 1 auto)
- **Files modified:** 11 (5 created, 6 modified)

## Accomplishments
- `app/status.py::get_platform_status()` aggregates own-Mongo ping, field-guide-api `/health` reachability (mandatory `timeout=2`, `requests.exceptions.RequestException`-isolated), `app_version`, `service_count` (`mongo.db.services.count_documents({})`, correctly 0 until Phase 9), and `metrics_preview` (summed from the same `prometheus_client.REGISTRY` backing `/metrics`) into a never-raising six-field dict
- `GET /api/status` returns that dict as JSON, 200 always — verified never to 500 even when field-guide-api is mocked unreachable
- `GET /partials/status-cards` now branches on `HX-Request: true` — returns the bare fragment for htmx, or a full page (`status_full_page.html`, `{% extends "base.html" %}` + `{% include "partials/status_cards.html" %}`) for direct navigation, with zero markup duplication
- `status_cards.html` rewritten from the Phase 6 `{% if status == "unknown" %}` sentinel into four real per-field cards (MongoDB, Field Guide API, Version, Registered Services) using the `status-card--ok`/`status-card--degraded` convention
- `/metrics` parity with field-guide-api locked in by a new test asserting `flask_http_request_total` and `flask_http_request_duration_seconds` are present — zero application code changed for this task
- `make test-launchpad` passes 37/37 tests at 100% coverage

## Task Commits

Each task was committed atomically (TDD: test → feat):

1. **Task 1: get_platform_status() helper + /api/status route** - `298115f` (test, RED) / `69fad80` (feat, GREEN)
2. **Task 2: HX-Request branch + real status cards** - `d03cac2` (test, RED) / `a882b4f` (feat, GREEN)
3. **Task 3: /metrics parity verification** - `d255f2a` (test only — no application code changed)

**Plan metadata:** (pending — this commit)

## Files Created/Modified
- `apps/launchpad/app/status.py` - NEW: `get_platform_status()` aggregation helper, no Blueprint, mirrors `app/k8s.py`'s bare-helper shape
- `apps/launchpad/app/routes/status.py` - NEW: `status_bp` with `GET /api/status`
- `apps/launchpad/app/templates/status_full_page.html` - NEW: full-page wrapper around the status-cards fragment
- `apps/launchpad/app/routes/partials.py` - evolved in place: `HX-Request`-aware branch, real `get_platform_status()` data, rewritten docstring documenting the deliberate Phase 6→7 contract evolution
- `apps/launchpad/app/routes/__init__.py` - added `status_bp` to barrel export
- `apps/launchpad/app/__init__.py` - registered `status_bp` in the deferred-import block
- `apps/launchpad/app/templates/partials/status_cards.html` - rewritten: four real per-field cards replacing the "unknown" stub
- `apps/launchpad/tests/test_status.py` - NEW: 8 tests covering every `get_platform_status()`/`/api/status` branch
- `apps/launchpad/tests/test_metrics.py` - NEW: 2 tests locking in `/metrics` parity with field-guide-api
- `apps/launchpad/tests/test_partials.py` - extended: HX-Request fragment/full-page, degraded card, real-data rendering
- `apps/launchpad/tests/conftest.py` - added `mock_requests_get_unreachable` fixture (ConnectionError) alongside the existing success fixture

## Decisions Made
- `current_app.config` chosen over `os.environ.get` for `FIELD_GUIDE_BASE_URL`/`APP_VERSION` in `status.py`, per PATTERNS.md's flagged discretion point — keeps the `Config` class the single source of truth and gives tests override control via `create_app(config_overrides)`
- `metrics_preview`'s increment test drives the underlying `Counter` object directly rather than issuing a fresh test-client request, because `prometheus-flask-exporter`'s `export_defaults()` skips re-registering its default metrics once any app in the same pytest process has already registered them on the shared global `REGISTRY` — a pre-existing library + app-factory interaction, not a defect in this plan's implementation (see Deviations)
- Version and service-count cards styled by overall `api_health` rather than an independent status concept, since neither field has its own up/down state distinct from mongo/field-guide reachability

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed a flaky metrics_preview test caused by cross-test Prometheus registry state**
- **Found during:** Task 1 (test execution — passed in isolation, failed when run as part of the full suite)
- **Issue:** The first version of `test_status_metrics_preview_increments_after_request` issued a fresh test-client request and asserted the counter was `>= 1`. This passed when run alone but failed intermittently depending on test execution order: `prometheus-flask-exporter`'s `export_defaults()` calls `self.info(...)` guarded by `except ValueError: return` to avoid re-registering already-registered metric names on the process-global `prometheus_client.REGISTRY`. Because the `tests/conftest.py` `app` fixture calls `create_app()` fresh per test, the FIRST test in the process to create an app "wins" the registration; every subsequent test's fresh `Flask` app has `metrics.init_app()` called on it but its own before/after-request instrumentation hooks are silently skipped, so requests made through that app's test client never increment the shared counter.
- **Fix:** Rewrote the test to (a) assert the type/shape contract via a before/after delta measured on the SAME app instance, and (b) drive the underlying `Counter` collector directly (found via `prometheus_client.REGISTRY._collector_to_names`) rather than relying on a fresh test-client request incrementing it — this exercises `get_platform_status()`'s read/summation logic without depending on cross-test instrumentation-registration ordering, which is an inherent property of the library + app-factory pattern, not something this plan's code controls.
- **Files modified:** apps/launchpad/tests/test_status.py
- **Verification:** `pytest tests/test_status.py -q` and the full `pytest -q` suite both pass deterministically regardless of test order; 100% coverage maintained.
- **Committed in:** `69fad80` (Task 1 GREEN commit — the corrected test landed in the same GREEN cycle since the flakiness was discovered during that task's verification, before any separate commit had captured the flawed version)

**2. [Rule 1 - Bug] Fixed an over-broad grep-companion test matching comment text**
- **Found during:** Task 1 (test execution)
- **Issue:** `test_status_no_requests_get_call_missing_timeout` (a unit-test companion to the plan's `grep -v '^#' ... requests.get` acceptance-criteria gate) naively scanned every source line containing the substring `requests.get(` for a `timeout=` keyword, including comment/docstring lines. A comment line explaining the timeout rationale (`# requests.get() can hang the entire pod...`) tripped a false failure.
- **Fix:** Skip lines whose stripped content starts with `#` before checking for the substring, matching the intent of the plan's own `grep -v '^#'` acceptance criterion.
- **Files modified:** apps/launchpad/tests/test_status.py
- **Verification:** Test passes; the real `grep -v '^#' apps/launchpad/app/status.py | grep 'requests\.get'` gate independently confirms the one real call carries `timeout=FIELD_GUIDE_TIMEOUT_SECONDS`.
- **Committed in:** `69fad80` (Task 1 GREEN commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 — test-correctness bugs discovered during verification, not application-code bugs)
**Impact on plan:** No scope creep; both fixes are test-only and were resolved before the Task 1 GREEN commit landed, so no separate commit was needed to correct them. `get_platform_status()`'s actual implementation was correct from the first GREEN pass.

## Issues Encountered
None beyond the deviations above.

## User Setup Required
None — no external service configuration required. All three tasks were `autonomous: true` with no checkpoints.

## Next Phase Readiness
- `/api/status`, `/partials/status-cards`, and `/metrics` are all real, tested, and never-500 — Phase 8's Helm chart can wire `/health` as the readinessProbe target (already locked from Plan 01) without further route changes, and Phase 10's `make smoke-launchpad` can assert against `/api/status` directly per ROADMAP.
- `service_count` is correctly `0` today via a real (not hardcoded) `count_documents({})` call — Phase 9 populates the `services` collection with zero code change required here.
- No blockers.

---
*Phase: 07-status-api-field-guide-integration*
*Completed: 2026-07-10*
