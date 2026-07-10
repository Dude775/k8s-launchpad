---
phase: 07-status-api-field-guide-integration
verified: 2026-07-11T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 7: Status API + Field-Guide Integration Verification Report

**Phase Goal:** The platform status contract is defined — /health is safe as a Kubernetes readinessProbe and /api/status surfaces real platform data including field-guide-api reachability.
**Verified:** 2026-07-11T00:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `GET /health` returns 200 when launchpad's own MongoDB is reachable and 503 when it is not; never calls field-guide-api regardless of downstream state | VERIFIED | Live test-client call: mongo up → `200 {"status":"ok","mongo":"up"}`; mongo raising → `503 {"status":"unavailable","mongo":"down"}`. `requests.get` was monkeypatched to raise `AssertionError` if called during the mongo-down /health request — no assertion fired, proving `/health` never reaches `requests.get`. `apps/launchpad/app/routes/health.py` imports only `app.extensions.mongo`; `grep -v '^#' health.py \| grep -E "requests\|FIELD_GUIDE"` returns no matches. |
| 2 | `GET /api/status` returns JSON containing `api_health`, `mongo_status`, `app_version`, `service_count`, and `field_guide_reachable`; `field_guide_reachable` shows a degraded value (not a crash or 500) when field-guide-api is unreachable | VERIFIED | Live test-client call with `requests.get` patched to raise `ConnectionError`: response is `200` (not 500) with body `{'api_health': 'ok', 'mongo_status': 'up', 'app_version': 'dev', 'service_count': 0, 'field_guide_reachable': False, 'metrics_preview': {...}}` — all 5 required fields present (plus `metrics_preview`, an added field, no subtraction), `field_guide_reachable` correctly `False`. |
| 3 | `GET /metrics` returns Prometheus-format text with HTTP request count and duration metrics (parity with field-guide-api `/metrics`) | VERIFIED | Live call: `200`, `content_type = "text/plain; version=0.0.4; charset=utf-8"`, body contains both `flask_http_request_total` and `flask_http_request_duration_seconds`. Locked in by `tests/test_metrics.py` (2 tests). |
| 4 | The status card htmx fragment route returns an HTML partial when `HX-Request` header is present and a full page otherwise; unit tests confirm this behavior | VERIFIED | Live call with `HX-Request: true` → body has no `<html>`, contains `status-card` markup. Live call without the header → body contains `<html>` (full page via `status_full_page.html` extending `base.html`). `apps/launchpad/app/routes/partials.py` branches explicitly on `request.headers.get("HX-Request") == "true"`. Covered by `tests/test_partials.py`. |
| 5 | `make test-launchpad` continues to pass at 100% coverage with all new routes exercised by mocked-requests unit tests | VERIFIED | Ran `pytest -q --cov=app --cov-report=term-missing` directly: `37 passed`, `TOTAL 130 stmts, 0 miss, 100% cover`. `app/status.py`, `app/routes/status.py`, `app/routes/partials.py`, `app/routes/health.py` all at 100%. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/launchpad/app/extensions.py` | Unbound `mongo: PyMongo = PyMongo()` singleton | VERIFIED | Present at line 14, alongside existing `metrics` singleton |
| `apps/launchpad/app/routes/health.py` | Real MongoDB readiness check (200/503), no field-guide coupling | VERIFIED | `mongo.cx.admin.command("ping")` inside try/except; 200/503 branches; no `requests`/`FIELD_GUIDE` reference |
| `apps/launchpad/app/config.py` | `MONGO_URI`, `FIELD_GUIDE_BASE_URL`, `APP_VERSION` config keys | VERIFIED | All three present with launchpad-specific defaults (`MONGO_URI` targets `/launchpad`, not `/fieldguide`) |
| `apps/launchpad/requirements.txt` | Direct pins for Flask-PyMongo, pymongo, requests | VERIFIED | `Flask-PyMongo==3.0.1` confirmed via pip-installed test environment (tests run successfully against mongomock + flask_pymongo import) |
| `apps/launchpad/app/status.py` | `get_platform_status()` aggregation helper (no Blueprint) | VERIFIED | `def get_platform_status() -> dict:` present, no `Blueprint(` in file, returns exactly 6 keys |
| `apps/launchpad/app/routes/status.py` | `GET /api/status` JSON route (`status_bp`) | VERIFIED | `status_bp = Blueprint("status", __name__)`, route registered, `jsonify(get_platform_status())` |
| `apps/launchpad/app/templates/status_full_page.html` | Full-page wrapper including the status_cards fragment | VERIFIED | `{% extends "base.html" %}` + `{% include "partials/status_cards.html" %}` |
| `apps/launchpad/app/routes/partials.py` | HX-Request-aware status-cards route with real data | VERIFIED | Branches on `HX-Request` header, calls `get_platform_status()` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `app/__init__.py` | `app.extensions.mongo` | `mongo.init_app(app, serverSelectionTimeoutMS=...)` | WIRED | Line 49-52, `MONGO_SERVER_SELECTION_TIMEOUT_MS` defaulted to 2000 before init |
| `app/routes/health.py` | `app.extensions.mongo` | `mongo.cx.admin.command('ping')` | WIRED | Line 34, confirmed live (200/503 both exercised) |
| `app/routes/status.py` | `app.status.get_platform_status` | `jsonify(get_platform_status())` | WIRED | Line 17, 25 |
| `app/routes/partials.py` | `app.status.get_platform_status` | `render_template(..., status=get_platform_status())` | WIRED | Lines 28, 37-40, both branches pass `status=status` |
| `app/status.py` | field-guide-api `/health` | `requests.get(f'{base_url}/health', timeout=2)` | WIRED | Line 77, `timeout=FIELD_GUIDE_TIMEOUT_SECONDS` (=2) present; confirmed the only `requests.get` call site carries a timeout |
| `app/__init__.py` | `app.routes.status.status_bp` | `app.register_blueprint(status_bp)` | WIRED | Line 65 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `/api/status` | `get_platform_status()` return dict | Live `mongo.cx.admin.command("ping")`, live `requests.get` to `FIELD_GUIDE_BASE_URL`, live `mongo.db.services.count_documents({})`, live `prometheus_client.REGISTRY.collect()` | Yes | FLOWING — verified by patching `requests.get` to raise and confirming the response reflects that failure (`field_guide_reachable: False`) rather than a static/hardcoded value |
| `/partials/status-cards` fragment | `status` (from `get_platform_status()`) | Same helper as `/api/status` — single source of truth, no second data path | Yes | FLOWING — mongo_status, field_guide_reachable, app_version, service_count all interpolated into the template from the live dict, confirmed via rendered HTML containing `status-card` markup |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `/health` 200 on mongo up | test-client GET with mongomock backing | `200 {"status":"ok","mongo":"up"}` | PASS |
| `/health` 503 on mongo down, never calls requests | test-client GET with mongo.cx.admin.command raising + requests.get patched to raise AssertionError if invoked | `503 {"status":"unavailable","mongo":"down"}`, no AssertionError | PASS |
| `/api/status` degrades gracefully | test-client GET with requests.get raising ConnectionError | `200`, all 6 fields present, `field_guide_reachable: False` | PASS |
| `/partials/status-cards` HX-Request branching | test-client GET with/without `HX-Request: true` header | fragment (no `<html>`) vs full page (`<html>` present) | PASS |
| `/metrics` Prometheus parity | test-client GET `/metrics` | `200`, `text/plain`, contains `flask_http_request_total` and `flask_http_request_duration_seconds` | PASS |
| Full test suite + coverage | `pytest -q --cov=app --cov-report=term-missing` | `37 passed`, 100% coverage (130/130 stmts) | PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` files exist in this repository and neither PLAN nor SUMMARY reference a probe script. Step 7c: SKIPPED (no probes declared or discovered for this phase).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|--------------|--------|----------|
| STAT-01 | 07-02-PLAN.md | `GET /api/status` returns real platform status | SATISFIED | Live call confirms all fields present with real (non-hardcoded) data sources |
| STAT-02 | 07-02-PLAN.md | Platform status reflects field-guide-api reachability, degrades gracefully | SATISFIED | Live call with simulated unreachability returns 200 with `field_guide_reachable: False`, never 500 |
| STAT-03 | 07-01-PLAN.md | `/health` checks only launchpad's own MongoDB, returns 503 when down | SATISFIED | Live call confirms 503 on mongo failure, and `requests.get` is never invoked |
| STAT-04 | 07-02-PLAN.md | `/metrics` exposes Prometheus-format metrics, parity with field-guide-api | SATISFIED | Live call confirms both `flask_http_request_total` and `flask_http_request_duration_seconds` present |

No orphaned requirements: REQUIREMENTS.md maps only STAT-01..04 to Phase 7 (roadmap traceability table lines 112-115), and both plans jointly declare exactly these four IDs.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `apps/launchpad/app/templates/partials/status_cards.html` | 1,5,9,13 | `status-card--ok`/`--degraded` modifier classes have no corresponding CSS rules in `app/static/style.css` (confirmed by grep: zero matches for `status-card--`) | WARNING (carried from 07-REVIEW.md WR-01) | Degraded state is not visually distinguishable from healthy state in the browser. Does NOT fail any Phase 7 success criterion — all 5 criteria concern the HTTP/JSON contract and HX-Request branching mechanics, not CSS rendering. `style.css` is outside this phase's `files_modified` list in both PLAN frontmatters. UI-03 (visual "live data" cards) is a Phase 6 requirement, not Phase 7. |
| `apps/launchpad/app/templates/partials/status_cards.html` | 9,13 | Version/Registered-Services cards colored by unrelated `api_health` (mongo-derived), per 07-REVIEW.md WR-02 | INFO | Cosmetic/semantic mismatch, not a Phase 7 must-have violation |
| `apps/launchpad/app/status.py` | 77-78 | `field_guide_reachable` conflates network reachability with HTTP 200, per 07-REVIEW.md WR-03 | INFO | Naming/semantic nuance; the roadmap SC only requires a "degraded value (not a crash or 500)" which is satisfied regardless of this naming choice |
| `apps/launchpad/app/__init__.py`, `apps/launchpad/app/routes/__init__.py` | — | Duplicated blueprint import surfaces (deferred imports in `__init__.py` vs eager re-export in `routes/__init__.py`), per 07-REVIEW.md WR-04 | INFO | Does not affect runtime behavior (both surfaces currently agree); flagged for future cleanup |

No TBD/FIXME/XXX debt markers found in any Phase 7 file (health.py, status.py, routes/status.py, routes/partials.py, templates, __init__.py, extensions.py, config.py, routes/__init__.py).

### Human Verification Required

None. All 5 roadmap Success Criteria are HTTP/JSON contract and structural-branching behaviors that were directly and empirically verified via live test-client calls in this verification pass (not just SUMMARY narrative or unit-test trust). WR-01 (missing CSS) is a real, documented defect but does not gate any Phase 7 success criterion — it is a visual/UX concern belonging to Phase 6's UI-03 scope or a future polish pass, not a Phase 7 blocker.

### Gaps Summary

No gaps. All 5 ROADMAP Success Criteria for Phase 7 are verified against live, executed code — not SUMMARY claims. The full test suite (37 tests) passes at 100% statement coverage, matching the SUMMARY's claim exactly. All four requirement IDs (STAT-01 through STAT-04) trace cleanly to implementation with no orphaned requirements. The code-review WARNING findings (WR-01 through WR-04) are real but do not block phase-goal achievement: WR-01 is a visual-only gap outside this phase's CSS scope, WR-02/WR-03/WR-04 are semantic/structural nits that do not violate any of the 5 stated success criteria's literal contract. They are worth fixing before Phase 8 builds further on this contract, but are not phase-blocking per the roadmap's own success criteria wording.

---

_Verified: 2026-07-11T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
