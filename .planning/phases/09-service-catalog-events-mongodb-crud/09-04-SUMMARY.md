---
phase: 09-service-catalog-events-mongodb-crud
plan: 04
subsystem: events
tags: [pymongo, datetime, tz-aware, flask-pymongo, gap-closure]

# Dependency graph
requires:
  - phase: 09-service-catalog-events-mongodb-crud
    provides: events feed (FEED-01/02/03) with _relative_time rendering helper, verified by 09-VERIFICATION.md to have gap CR-01
provides:
  - "_relative_time() naive-datetime normalization guard (tzinfo is None -> replace with UTC)"
  - "mongo.init_app(tz_aware=True) so real PyMongo decodes BSON dates as timezone-aware at the source"
  - "regression tests proving CR-01 is fixed and never-raise discipline is preserved"
affects: [09-service-catalog-events-mongodb-crud, future events/feed work touching timestamps]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Naive-datetime normalization guard inside a try block, ahead of aware-datetime arithmetic, to defend against unmocked driver decode behavior (mongomock vs real PyMongo divergence)"

key-files:
  created: []
  modified:
    - apps/launchpad/app/events.py
    - apps/launchpad/app/__init__.py
    - apps/launchpad/tests/test_events.py

key-decisions:
  - "Applied both fix layers (defensive normalization in _relative_time + tz_aware=True on mongo.init_app) per the plan's pre-recorded Fix Decision — normalization is the only layer mongomock can exercise, tz_aware=True is a cheap correctness fix at the driver decode source"

patterns-established:
  - "When mongomock cannot reproduce real-driver decode behavior (e.g. BSON date timezone handling), add a defensive normalization guard at the consuming function AND fix the source config, so both layers hold independently"

requirements-completed: [FEED-01]

# Metrics
duration: 12min
completed: 2026-07-13
---

# Phase 09 Plan 04: CR-01 naive-datetime relative-time gap closure Summary

**Fixed `_relative_time()` to normalize timezone-naive PyMongo BSON-decoded datetimes to UTC-aware before arithmetic, and set `tz_aware=True` on `mongo.init_app()` so real MongoDB reads decode as aware at the source — closing verification gap CR-01 where the FEED-01 relative-time cell silently rendered "unknown" against real in-cluster MongoDB.**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-07-13T10:57:00Z
- **Completed:** 2026-07-13T11:09:43Z
- **Tasks:** 3 (RED, GREEN, coverage-gate confirmation)
- **Files modified:** 3

## Accomplishments
- Reproduced CR-01 in the test suite: two RED regression tests passing naive `datetime.utcnow()` values to `_relative_time` and asserting real relative-time strings, confirmed failing ("unknown") before the fix
- Fixed `_relative_time()` with a naive-datetime normalization guard (`if ts.tzinfo is None: ts = ts.replace(tzinfo=timezone.utc)`) placed inside the existing try block so the never-raise discipline for None/garbage inputs is untouched
- Added `tz_aware=True` to `mongo.init_app()` so real PyMongo decodes BSON dates as timezone-aware UTC datetimes at the source
- Confirmed full launchpad suite green at 128 tests, 100.00% coverage under `--cov=app --cov-fail-under=100` — no coverage top-up needed, the Task 1 regression tests already exercised the new normalization branch

## Task Commits

Each task was committed atomically:

1. **Task 1: Add regression test for naive-datetime input to _relative_time (RED)** - `d4123d0` (test)
2. **Task 2: Normalize naive datetimes in _relative_time and set tz_aware=True on mongo.init_app (GREEN)** - `8590ac4` (fix)
3. **Task 3: Full-suite + coverage gate confirmation** - no commit (verification-only; zero files changed, gate already met at 100%)

_Note: TDD Task 1/2 pair follows RED -> GREEN; no REFACTOR commit was needed._

## Files Created/Modified
- `apps/launchpad/tests/test_events.py` - Added `test_relative_time_naive_utc_now_returns_just_now` and `test_relative_time_naive_utc_past_returns_real_value`, both asserting real relative-time strings from naive UTC datetimes (CR-01 reproduction + regression guard)
- `apps/launchpad/app/events.py` - `_relative_time()` now normalizes a `tzinfo is None` timestamp to UTC-aware before subtracting from `datetime.now(timezone.utc)`
- `apps/launchpad/app/__init__.py` - `mongo.init_app(...)` now passes `tz_aware=True`, with an inline comment explaining the CR-01 rationale

## Decisions Made
- Followed the plan's pre-recorded Fix Decision exactly: both layers (defensive normalization + `tz_aware=True`), no alternative considered during execution — the plan's rationale (mongomock cannot reproduce BSON-driven naive decode, so only the normalization guard is test-covered; `tz_aware=True` fixes the source cheaply) held up during implementation.

## Deviations from Plan

None - plan executed exactly as written. Task 3 required no test top-up since the Task 1 regression tests already drove 100% coverage on the new normalization branch.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

CR-01 is closed: `_relative_time()` now renders real relative-time strings for naive datetimes (the shape real PyMongo returns), preserving "unknown" only for `None` and genuinely malformed input. `mongo.init_app()` decodes BSON dates as timezone-aware at the source for all future timestamp consumers. Full launchpad suite (128 tests) is green at 100% coverage. No blockers for phase completion; this closes the sole open verification gap from 09-VERIFICATION.md.

---
*Phase: 09-service-catalog-events-mongodb-crud*
*Completed: 2026-07-13*

## Self-Check: PASSED

- FOUND: apps/launchpad/app/events.py
- FOUND: apps/launchpad/app/__init__.py
- FOUND: apps/launchpad/tests/test_events.py
- FOUND: .planning/phases/09-service-catalog-events-mongodb-crud/09-04-SUMMARY.md
- FOUND commit: d4123d0 (test)
- FOUND commit: 8590ac4 (fix)
- FOUND commit: 4835003 (docs: summary)
- Confirmed `tzinfo` guard present in events.py (line 130-131)
- Confirmed `tz_aware=True` present in __init__.py (line 54)
