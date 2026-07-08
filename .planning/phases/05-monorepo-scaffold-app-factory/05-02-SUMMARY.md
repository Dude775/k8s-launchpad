---
phase: 05-monorepo-scaffold-app-factory
plan: 02
subsystem: tooling
tags: [makefile, build-orchestration, launchpad, venv, pytest]

# Dependency graph
requires:
  - phase: 05-01 (launchpad app factory)
    provides: apps/launchpad/ tree with requirements-dev.txt + pytest.ini that test-launchpad drives
  - phase: 01-04 (v1.0 field-guide-api Makefile)
    provides: proven test target + venv-resolution idiom + help awk pattern to mirror
provides:
  - "LP_IMAGE/LP_TAG/LP_RELEASE/LP_CHART Makefile variables — namespaced, no shadowing of field-guide-api"
  - "make test-launchpad — fully working target (venv + deps + pytest at 100% coverage)"
  - "build/load/deploy/port-forward/smoke-launchpad — guarded Phase-8/10 stubs (echo + exit 0)"
affects: [08-helm-chart-diagnostics, 10-e2e-smoke]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "LP_ prefix namespacing so launchpad build coordinates never shadow field-guide-api's IMAGE/RELEASE/CHART"
    - "Guarded stub targets (echo a phase-N notice + exit 0) reserve the Makefile seam without invoking docker/helm/kubectl"
    - "test-launchpad is a parametrized copy of test (cd into app dir + per-app .venv + pytest.ini) — not a new pattern"

key-files:
  created: []
  modified:
    - Makefile

key-decisions:
  - "D-08 implemented: LP_* vars + six *-launchpad targets visible in make help; test-launchpad fully works; the other five are guarded exit-0 stubs"
  - "D-09 implemented: launchpad stubs NOT pulled into the up aggregate; no up-all created; v1.0 field-guide-api behavior unchanged"

patterns-established:
  - "Namespace future second-app Makefile targets/vars with an app-specific prefix (LP_) and a -launchpad suffix so make help disambiguates without collision"

requirements-completed: [APP-01]

# Metrics
duration: 8min
completed: 2026-07-08
---

# Phase 5 Plan 2: Launchpad Makefile Targets Summary

**Root `Makefile` gains the `LP_*` build-coordinate namespace and six `*-launchpad` targets — `test-launchpad` fully works (venv + dev deps + pytest at 100% coverage, no cluster needed), while build/load/deploy/port-forward/smoke are guarded Phase-8/10 stubs — without touching the `up` aggregate or any field-guide-api variable or target.**

## Performance

- **Duration:** 8 min
- **Completed:** 2026-07-08
- **Tasks:** 2 of 2 (Task 1 auto Makefile edit; Task 2 blocking human checkpoint — approved)
- **Files modified:** 1 (Makefile)

## Accomplishments
- Added `LP_IMAGE`/`LP_TAG`/`LP_RELEASE`/`LP_CHART` beside the existing `IMAGE`/`TAG`/`RELEASE`/`CHART` — namespaced so they never shadow field-guide-api (D-08).
- Added `test-launchpad`: a working mirror of `test` pointed at `apps/launchpad`, using the same idempotent-venv + `VENV_PY` resolution + `pip install -r requirements-dev.txt` + `pytest` idiom (D-08).
- Added `build-launchpad`, `load-launchpad`, `deploy-launchpad`, `port-forward-launchpad` (Phase 8) and `smoke-launchpad` (Phase 10) as guarded `@echo`-and-exit-0 stubs that invoke no docker/helm/kubectl.
- Extended `.PHONY` and gave every target a `## description` so the existing `help` awk auto-renders both apps' targets with no collision; `up` and `up-all` untouched (D-09).

## Task Commits

1. **Task 1: Add LP_* vars and launchpad targets to the Makefile** - `44bcc5c` (feat)
2. **Task 2: Verify make test-launchpad runs green end-to-end** - blocking human checkpoint, approved (no code change)

## Files Created/Modified
- `Makefile` - added `LP_*` vars, six `*-launchpad` targets, extended `.PHONY`, Phase-5 comment on the targets line.

## Decisions Made
- Stub notice wording maps build/load/deploy/port-forward to Phase 8 and smoke to Phase 10, matching the deferred roadmap ordering.
- Kept `test-launchpad`'s venv creation on the shared `$(PYTHON)` override var (consistent with `test`); on this Windows host the pre-existing `apps/launchpad/.venv` (Python 3.12.10) is reused via the `[ -d .venv ] ||` idempotency guard.

## Deviations from Plan
None. Task 1's automated gate returned `GATE_OK`; Task 2's checkpoint passed on first run.

## Verification
- `make help` lists all six `*-launchpad` targets alongside the field-guide-api targets — no collision.
- `make build-launchpad`, `make port-forward-launchpad`, `make smoke-launchpad` each print a Phase-8/10 notice and exit 0 — no cluster tooling invoked.
- `make test-launchpad` → 13 passed, 100% coverage (`--cov-fail-under=100`), Python 3.12.10 venv, no kind-cluster dependency (passed with a cluster present, proving hermetic isolation).
- `make test` (field-guide-api) → 32 passed, 100% coverage, unchanged.
- `up: cluster-up build load deploy` definition unchanged; `up-all` does not exist; `IMAGE`/`RELEASE`/`CHART` unchanged.

## Issues Encountered
None. (Host note: the default `python`/`python3` on this machine is pyenv global 3.7.4, too old for the pinned deps; the launchpad `.venv` was created with Python 3.12.10 — the same interpreter field-guide-api uses — so both the executor and `make test-launchpad` resolve the correct interpreter via the `.venv`.)

## User Setup Required
None.

## Next Phase Readiness
- The `LP_*` Makefile namespace and the five guarded stubs are in place for Phase 8 (Helm chart + cluster deploy) and Phase 10 (smoke) to fill in place — no rename/restructure needed later (the highest-recovery-cost seam is now established, per roadmap rationale).
- `make test-launchpad` is the working local gate for all subsequent launchpad app work.

---
*Phase: 05-monorepo-scaffold-app-factory*
*Completed: 2026-07-08*
