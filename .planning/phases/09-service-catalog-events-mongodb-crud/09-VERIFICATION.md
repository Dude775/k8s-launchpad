---
phase: 09-service-catalog-events-mongodb-crud
verified: 2026-07-13T12:00:00Z
status: passed
score: 7/7 must-haves verified (6 roadmap SCs + CR-01 gap-closure truth)
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: "6/6 roadmap SCs verified; 1 critical gap (CR-01) found outside literal SC wording"
  gaps_closed:
    - "FEED-01 Event-Row Anatomy relative-time element renders a real value for events read from real MongoDB (CR-01: naive/aware datetime subtraction no longer raises a swallowed TypeError)"
  gaps_remaining: []
  regressions: []
---

# Phase 9: Service Catalog + Events Feed + MongoDB CRUD Verification Report

**Phase Goal:** Developers can register, view, and deregister services through the dashboard; every platform action writes to a bounded events feed backed by its own in-cluster MongoDB
**Verified:** 2026-07-13
**Status:** passed
**Re-verification:** Yes — after gap closure (plan 09-04, commits d4123d0, 8590ac4)

## Goal Achievement

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `GET /catalog` lists services from MongoDB; `POST /catalog/new` with valid input persists, fires `service_registered`, redirects to catalog with new entry visible | VERIFIED | `app/routes/pages.py:catalog_list`/`catalog_new` call `catalog.list_services()`/`catalog.register_service()` + `events.record_event("service_registered", ...)`; file re-read this pass, unchanged since prior verification and still present |
| 2 | Invalid/missing required fields re-render form with field-level errors and CSRF intact — no document written | VERIFIED | `ServiceForm` validators in `app/forms.py`; `catalog_new()` re-renders `onboard_form.html` on `validate_on_submit()` failure; unchanged since prior pass |
| 3 | `GET /catalog/<id>` shows full registration fields and that service's related events | VERIFIED | `catalog_detail()` renders `detail.html` with `service` + `events.get_events_for_service(name)`; template file re-confirmed present |
| 4 | Deregistering (after confirmation) removes from MongoDB and fires `service_deregistered` visible in feed | VERIFIED | `catalog_delete_confirm()`/`catalog_delete()` call `catalog.deregister_service()` then `events.record_event("service_deregistered", name)`; unchanged |
| 5 | `events` collection has TTL index on `ts`; `make test-launchpad` passes (mongomock-backed); suite documents TTL expiry is verified live via smoke, not unit tests | VERIFIED | `events.ensure_indexes()` unchanged; independently re-ran `pytest --cov=app --cov-fail-under=100` this session → **128 passed, 100.00% coverage** (up from 126 pre-gap-closure — the 2 new CR-01 regression tests) |
| 6 | launchpad Helm chart embeds `mongo:7` manifests in `charts/launchpad/templates/mongodb/` with database `launchpad`; field-guide-api chart untouched | VERIFIED | Independently re-ran `helm lint charts/launchpad/` this session → 0 failures (1 informational icon notice only); `git status --short` clean, no chart drift |
| 7 (gap-closure) | FEED-01 Event-Row Anatomy relative-time element renders a real value ("2 minutes ago" style) for events read from real MongoDB — CR-01 closed | VERIFIED | Direct reproduction run this session (not trusting SUMMARY): `events._relative_time(datetime.utcnow())` → `"just now"`; naive datetime ~2min in past → `"2 minutes ago"`; `None` → `"unknown"`; garbage string → `"unknown"` (never-raise discipline intact). Source: `app/events.py:130-131` normalizes `ts.tzinfo is None` before subtraction; `app/__init__.py:51-55` passes `tz_aware=True` to `mongo.init_app()`. Both layers present exactly as the gap-closure plan specified. |

**Score:** 7/7 — all 6 roadmap Success Criteria plus the CR-01 gap-closure truth verified true in the codebase.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/launchpad/app/catalog.py` | never-raise CRUD helper | VERIFIED | Present, unchanged since prior pass |
| `apps/launchpad/app/events.py` | never-raise events helper | VERIFIED | `_relative_time` now normalizes naive datetimes (lines 126-131) before subtraction — CR-01 fix confirmed in source, not just SUMMARY narration |
| `apps/launchpad/app/__init__.py` | mongo.init_app with tz_aware=True | VERIFIED | `mongo.init_app(app, serverSelectionTimeoutMS=..., tz_aware=True)` at lines 51-55, with inline CR-01 rationale comment |
| `apps/launchpad/tests/test_events.py` | naive-datetime regression tests | VERIFIED | `test_relative_time_naive_utc_now_returns_just_now` and `test_relative_time_naive_utc_past_returns_real_value` present at lines 258-265, both pass; existing 6 tz-aware tests + None/garbage tests untouched and still pass |
| `apps/launchpad/app/forms.py` | `ServiceForm` with locked validators/copy | VERIFIED | Unchanged since prior pass |
| `apps/launchpad/app/routes/pages.py` | real catalog CRUD routes | VERIFIED | Unchanged since prior pass |
| `apps/launchpad/app/routes/partials.py` | `/partials/feed` fragment/full-page | VERIFIED | Unchanged since prior pass |
| Seven templates (catalog, onboard_form, detail, confirm_delete, feed, feed_full_page, event_row, feed_events) | real markup, no placeholders | VERIFIED | All confirmed present via filesystem listing this session |
| `charts/launchpad/templates/mongodb/{deployment,pvc,secret,service}.yaml` | mongo:7 manifests | VERIFIED | All four files confirmed present this session |
| `charts/launchpad/templates/_helpers.tpl` | `launchpad.mongodb.fullname` + `launchpad.mongodb.selectorLabels` | VERIFIED | Unchanged since prior pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `pages.py` | `app.catalog`/`app.events` | module-attribute calls | WIRED | Unchanged since prior pass |
| `catalog.py` | `mongo.db.services` | insert_one/find/delete_one + unique index | WIRED | Unchanged |
| `events.py` | `mongo.db.events` | insert_one/find sorted by ts + TTL index | WIRED | Unchanged |
| `events.py::_relative_time` | `datetime.now(timezone.utc)` subtraction | tzinfo normalization guard | WIRED | `if ts.tzinfo is None: ts = ts.replace(tzinfo=timezone.utc)` executes before every subtraction; verified live via direct interpreter reproduction, not just grep |
| `__init__.py::create_app` | `mongo.init_app` | `tz_aware=True` kwarg | WIRED | Confirmed via `grep -n "tz_aware" app/__init__.py` → match at line 54, and functionally via the direct reproduction (naive-in real Mongo path is now moot since the guard covers it defensively regardless) |
| `test_events.py` | `app.events._relative_time` | naive-datetime input assertions | WIRED | Both new tests call `_relative_time` directly with `datetime.utcnow()`-derived naive values and assert non-"unknown" real strings; both pass |
| `feed.html` | `partials.feed` | hx-get visibility-guarded 15s poll | WIRED | Unchanged since prior pass |
| `detail.html` | `partials/event_row.html` | include in loop | WIRED | Unchanged since prior pass |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `catalog.html` | `services` | `catalog.list_services()` → `mongo.db.services.find()` | Yes | FLOWING |
| `detail.html` | `events_for_service` | `events.get_events_for_service(name)` → `mongo.db.events.find(...)` | Yes | FLOWING |
| `partials/feed_events.html` | `events_list` | `events.list_recent_events()` → `mongo.db.events.find().sort(...)` | Yes | FLOWING |
| `partials/event_row.html` | `events._relative_time(event.ts)` | timestamp from a real MongoDB read (now tz-aware at source, and defensively normalized regardless) | **Yes — reproduced fixed** | ✓ FLOWING (previously HOLLOW under CR-01; direct reproduction this session confirms naive input now yields real relative-time strings, not "unknown") |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite passes at 100% coverage (independently re-run, not trusting SUMMARY) | `.venv/Scripts/python -m pytest --cov=app --cov-fail-under=100 -q` | 128 passed, TOTAL coverage 100.00% | PASS |
| `helm lint` passes (independently re-run) | `helm lint charts/launchpad/` | 1 chart linted, 0 failed (1 INFO: missing icon) | PASS |
| Working tree matches committed state | `git status --short` | (empty output) | PASS |
| CR-01 fix reproduction: naive datetime → real relative-time string | `python -c "... events._relative_time(datetime.utcnow())"` | `"just now"` (was `"unknown"` pre-fix) | PASS — gap closed |
| CR-01 fix reproduction: naive datetime ~2min in past → real relative-time string | `python -c "... events._relative_time(datetime.utcnow() - timedelta(minutes=2, seconds=10))"` | `"2 minutes ago"` | PASS — gap closed |
| Never-raise discipline preserved: None / garbage still "unknown" | `python -c "... events._relative_time(None); events._relative_time('not-a-timestamp')"` | `"unknown"`, `"unknown"` | PASS — no regression |
| Task commits present in git history | `git log --oneline -- app/events.py app/__init__.py tests/test_events.py` | `8590ac4 fix(09-04)...`, `d4123d0 test(09-04)...` present | PASS |
| No new debt markers introduced in modified files | `grep -n "TODO\|FIXME\|XXX\|TBD\|PLACEHOLDER\|HACK" app/events.py app/__init__.py tests/test_events.py` | (no matches) | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| CAT-01 | 09-02 | View service catalog listing | SATISFIED | `catalog_list()` + `catalog.html` table/empty-state |
| CAT-02 | 09-01, 09-02 | Onboard a service via form, persists to MongoDB | SATISFIED | `ServiceForm` + `catalog.register_service()` + `catalog_new()` POST path |
| CAT-03 | 09-01, 09-02 | Server-side validation (CSRF-protected), re-render with field errors | SATISFIED | CSRF-enabled test + invalid-submit re-render test both pass |
| CAT-04 | 09-02 | Service detail page: registration + related events | SATISFIED | `catalog_detail()` + `detail.html`, events display now correctly time-stamped |
| CAT-05 | 09-02 | Deregister after confirmation | SATISFIED | `catalog_delete_confirm()` (zero-JS) + `catalog_delete()` POST |
| FEED-01 | 09-01 (helper), 09-02 (route), **09-04 (gap closure)** | Activity/events feed, newest-first, persisted MongoDB collection, real relative-time display | **SATISFIED (gap closed)** | Feed route/template/data flow real and wired; relative-time element now renders correctly against real (naive-decoding) MongoDB reads — CR-01 fixed and regression-tested |
| FEED-02 | 09-01, 09-02 | platform_started / service_registered / service_deregistered all write events | SATISFIED | `emit_platform_started_once()`, both catalog routes call `events.record_event()` on success |
| FEED-03 | 09-01 | TTL-bounded events collection | SATISFIED | TTL index test + `EVENTS_TTL_SECONDS` config plumbed through chart ConfigMap |
| DEP-03 | 09-03 | In-cluster MongoDB via mirrored mongo:7 manifests, field-guide-api untouched | SATISFIED | Chart artifacts re-confirmed present; `helm lint`/`git status` clean this session |

No orphaned requirements — all 9 IDs from REQUIREMENTS.md Phase 9 rows (CAT-01..05, FEED-01..03, DEP-03) are claimed across the four plans' frontmatter (09-01 through 09-04).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `charts/launchpad/values.yaml:72` | — | `mongoUri` hardcodes hostname+credentials instead of composing via `launchpad.mongodb.fullname`/`mongodb.auth.*` (WR-01, carried over from prior code review) | Warning | Two-value desync risk on password rotation or non-default release name; does not block default-path functionality. Correctly left untouched — 09-04's plan explicitly scoped out WR-01..WR-05 |
| `apps/launchpad/app/templates/detail.html:12` | 12 | `repo_url` rendered as raw href with no scheme re-check at render boundary (WR-02, carried over) | Warning | Stored-XSS vector only if a document bypasses `ServiceForm`; form itself enforces scheme today |
| `apps/launchpad/app/config.py:55` | 55 | `EVENTS_TTL_SECONDS` int() parse at import time, no try/except (WR-03, carried over) | Warning | Malformed env var crash-loops gunicorn at boot; breaks never-raise discipline used elsewhere |
| `apps/launchpad/app/templates/partials/event_row.html:19-24` | 19-24 | Catch-all `{% else %}` labels any unrecognized event type as "Platform started" (WR-04, carried over) | Warning | Silently mislabels data if a future event type is introduced |
| `charts/launchpad/templates/mongodb/pvc.yaml`, `values.yaml:59` | — | `mongodb.persistence.enabled` flag declared but never read by any template (WR-05, carried over) | Warning | Dead config knob |

The prior BLOCKER-level finding (CR-01: broad `except Exception` masking the naive/aware `TypeError`) is now resolved — the exception path is still present (by design, for None/garbage inputs) but the naive-datetime case that used to trigger it is intercepted upstream by the new normalization guard, confirmed via direct reproduction. No new anti-patterns introduced by the gap-closure changes (checked `events.py`, `__init__.py`, `test_events.py` for TODO/FIXME/XXX/TBD/PLACEHOLDER/HACK — none found). The 5 pre-existing WARNING-level findings (WR-01..WR-05) are unchanged and were correctly out of scope for this gap-closure plan per its own stated constraints.

### Human Verification Required

None — all success criteria and the CR-01 gap closure are independently confirmable by direct code inspection, test execution, and interpreter-level reproduction. No visual/UX/real-time judgment call remains open.

### Gaps Summary

All 6 literal roadmap Success Criteria remain verified true, and the sole open gap from the prior verification pass (CR-01: `events._relative_time()` silently rendering "unknown" for every event once read from real in-cluster MongoDB, because PyMongo decodes BSON dates as timezone-naive and the naive/aware subtraction raised a swallowed `TypeError`) is now closed.

Verification of the closure was performed independently, not by trusting 09-04-SUMMARY.md's claims:
- Read the actual diff in `app/events.py` (lines 126-131) and `app/__init__.py` (lines 49-55) — both fix layers present exactly as the gap-closure plan specified (defensive normalization guard + `tz_aware=True` at the driver).
- Re-ran the full test suite independently (not copy-pasting the SUMMARY's reported numbers): 128 passed, 100.00% coverage, matching the SUMMARY's claim.
- Ran a direct interpreter reproduction of the exact failure mode documented in the original gap (naive `datetime.utcnow()` input) and confirmed it now returns `"just now"` / `"2 minutes ago"` instead of `"unknown"`.
- Confirmed the never-raise discipline is unbroken: `None` and non-datetime garbage inputs still correctly degrade to `"unknown"`.
- Confirmed no regressions: `git status --short` clean, `helm lint` still 0 failures, no new debt markers in modified files, WR-01..WR-05 warnings correctly left untouched per the gap-closure plan's explicit scope constraint.

Phase 9 goal is achieved: developers can register, view, and deregister services through the dashboard, and every platform action writes to a bounded events feed backed by its own in-cluster MongoDB — including a correctly rendering relative-time display now that the timezone-naive/aware datetime defect is fixed.

---

_Verified: 2026-07-13_
_Verifier: Claude (gsd-verifier)_
