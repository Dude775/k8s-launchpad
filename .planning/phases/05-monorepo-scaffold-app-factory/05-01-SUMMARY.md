---
phase: 05-monorepo-scaffold-app-factory
plan: 01
subsystem: api
tags: [flask, kubernetes-client, app-factory, prometheus, pytest]

# Dependency graph
requires:
  - phase: 01-04 (v1.0 field-guide-api)
    provides: proven Flask app-factory / config / extensions / Dockerfile / pytest.ini patterns to copy-and-adapt
provides:
  - "apps/launchpad/ — second, independent Flask workload with its own create_app factory"
  - "app.k8s.get_k8s_clients() — lazy K8s client accessor, (None,None) disabled signal, D-05/D-07 contract"
  - "GET /health plain 200 stub, evolvable in place for Phase 7"
  - "launchpad test harness at 100% coverage, no cluster/kubeconfig required"
affects: [06-ui-shell, 07-status-api, 08-helm-chart-diagnostics]

# Tech tracking
tech-stack:
  added: [kubernetes==36.0.2]
  patterns:
    - "Deferred blueprint imports inside create_app() (mirrors field-guide-api)"
    - "Lazy, exception-narrow K8s client accessor — never called at import time or in create_app()"
    - "Per-app .venv + pythonpath=. + cd-into-app-dir isolation to avoid app package name collision between apps/field-guide-api and apps/launchpad"

key-files:
  created:
    - apps/launchpad/app/__init__.py
    - apps/launchpad/app/config.py
    - apps/launchpad/app/extensions.py
    - apps/launchpad/app/k8s.py
    - apps/launchpad/app/routes/__init__.py
    - apps/launchpad/app/routes/health.py
    - apps/launchpad/wsgi.py
    - apps/launchpad/requirements.txt
    - apps/launchpad/requirements-dev.txt
    - apps/launchpad/Dockerfile
    - apps/launchpad/.dockerignore
    - apps/launchpad/.env.example
    - apps/launchpad/pytest.ini
    - apps/launchpad/tests/__init__.py
    - apps/launchpad/tests/conftest.py
    - apps/launchpad/tests/test_factory.py
    - apps/launchpad/tests/test_health.py
    - apps/launchpad/tests/test_k8s.py
  modified: []

key-decisions:
  - "D-01..D-10 implemented exactly as locked in 05-CONTEXT.md — no deviations from the decision set"
  - "test_k8s.py's disabled-path test redirects HOME/USERPROFILE to tmp_path to stay hermetic against this dev machine's real ~/.kube/config left over from the kind cluster (RESEARCH Pitfall 2) — confirmed necessary during Task 2 verification, not merely theoretical"

patterns-established:
  - "Lazy K8s client pattern (app/k8s.py): try in-cluster config, then kubeconfig, then (None, None); catch ConfigException narrowly per loader, never bare except Exception"
  - "Every app-package test suite must isolate HOME/USERPROFILE when testing kubeconfig-absence to avoid false positives/negatives from a developer machine's real kubeconfig"

requirements-completed: [APP-01, APP-02]

# Metrics
duration: 24min
completed: 2026-07-08
---

# Phase 5 Plan 1: Launchpad App Factory + Lazy K8s Client Summary

**New `apps/launchpad/` Flask workload with a factory that wires prometheus metrics only (no Mongo), a lazy `get_k8s_clients()` accessor with in-cluster-then-kubeconfig fallback to `(None, None)`, a plain `GET /health` stub, and a 100%-coverage pytest harness that runs with no live cluster.**

## Performance

- **Duration:** 24 min
- **Started:** 2026-07-08T09:02:18Z (approx, per STATE.md session start)
- **Completed:** 2026-07-08T09:26:18Z
- **Tasks:** 2 of 3 (Task 1 was a pre-approved checkpoint; Task 2 and Task 3 executed by this agent)
- **Files modified:** 18

## Accomplishments
- Stood up `apps/launchpad/` as a fully independent Flask app — own `create_app`, `Config`, `extensions.py`, `Dockerfile`, `requirements.txt`/`requirements-dev.txt` — mirroring the proven v1.0 `field-guide-api` structure with Mongo wiring deliberately stripped (D-02).
- Implemented `app/k8s.py`'s `get_k8s_clients()` exactly per D-05: in-cluster config first, then kubeconfig, then `(None, None)`, catching `ConfigException` narrowly per loader (never `except Exception`).
- `GET /health` returns a plain `200 {"status": "ok"}` with no Mongo check (D-04), same route name Phase 7 will evolve in place.
- Built a `tests/conftest.py` with `k8s_disabled`, `k8s_enabled`, and `mock_requests_get` fixtures, plus `test_factory.py`, `test_health.py`, `test_k8s.py` — 13 tests, 100% line coverage of `app/`, `--cov-fail-under=100` gate passing.

## Task Commits

Each task was committed atomically:

1. **Task 2: Create the launchpad app package + support files** - `f50ba9d` (feat)
2. **Task 3: Create the test harness at 100% coverage** - `652eb0e` (test)

**Plan metadata:** (pending — see final commit below)

_Note: Task 1 (`checkpoint:human-verify`, package legitimacy for `kubernetes==36.0.2`) was already approved by the reviewer at the orchestrator level before this agent started; no code changes were required for Task 1 itself._

## Files Created/Modified
- `apps/launchpad/app/__init__.py` - `create_app()` factory, deferred blueprint import, metrics-only wiring
- `apps/launchpad/app/config.py` - env-driven `Config` (DEBUG/TESTING only, no Mongo keys) + `_env_flag` helper
- `apps/launchpad/app/extensions.py` - `metrics` singleton only (no PyMongo)
- `apps/launchpad/app/k8s.py` - `get_k8s_clients()` lazy accessor, D-05 fallback contract
- `apps/launchpad/app/routes/health.py` - `health_bp`, plain `GET /health` 200 stub
- `apps/launchpad/app/routes/__init__.py` - re-exports `health_bp`
- `apps/launchpad/wsgi.py` - gunicorn entrypoint, reused verbatim
- `apps/launchpad/requirements.txt` - Flask, kubernetes==36.0.2, prometheus-flask-exporter, python-dotenv, gunicorn
- `apps/launchpad/requirements-dev.txt` - pytest, pytest-flask, pytest-cov (no mongomock)
- `apps/launchpad/Dockerfile` - multi-stage python:3.11-slim, non-root UID 10001, gunicorn PID 1, COPY allowlist
- `apps/launchpad/.dockerignore` - excludes `.venv/`, `tests/`, `__pycache__`, `.env`
- `apps/launchpad/.env.example` - `FLASK_DEBUG=` only
- `apps/launchpad/pytest.ini` - `--cov=app --cov-fail-under=100`, `pythonpath = .`
- `apps/launchpad/tests/__init__.py` - empty package marker
- `apps/launchpad/tests/conftest.py` - `app`/`client` fixtures, `k8s_disabled`/`k8s_enabled`/`mock_requests_get`
- `apps/launchpad/tests/test_factory.py` - factory/config/extensions structural tests
- `apps/launchpad/tests/test_health.py` - `GET /health` 200 test
- `apps/launchpad/tests/test_k8s.py` - both `get_k8s_clients()` branches, hermetic HOME/USERPROFILE isolation, fallback-to-kubeconfig branch, fixture-consumption tests

## Decisions Made
- Kept `Config` minimal in Phase 5 (DEBUG/TESTING only) per RESEARCH Open Question #2 recommendation — no `LP_`-prefixed env vars introduced yet since there's nothing launchpad-specific to configure until Phase 7/9 add Mongo.
- Added a third `test_k8s.py` test (`test_get_k8s_clients_falls_back_to_kube_config`) beyond the two RESEARCH examples, plus two fixture-consumption tests (`test_k8s_disabled_fixture`, `test_k8s_enabled_fixture`), to ensure `--cov-fail-under=100` is satisfied without dead fixtures, per the plan's explicit instruction ("if any fixture... is unused by a test, add a minimal test that consumes it").

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking, environment-only] Task 2's literal verify command initially failed on this dev machine due to a real leftover kubeconfig**
- **Found during:** Task 2 verification
- **Issue:** Running the plan's exact Task 2 automated verify command (`assert get_k8s_clients()==(None,None)`) failed because this machine has a real `~/.kube/config` from the Phase 2/3 kind cluster work, so `config.load_kube_config()` succeeded and returned live API client objects instead of `(None, None)`. This is exactly RESEARCH's documented "Pitfall 2" (`load_kube_config()` succeeding accidentally in CI/dev because a stale kubeconfig is present) — not a code defect. The `app/k8s.py` implementation is correct per D-05.
- **Fix:** No code change needed. Verified the fix by re-running the same assertions with `HOME`/`USERPROFILE` redirected to an empty temp directory, which returned `(None, None)` as expected — confirming `get_k8s_clients()` behaves correctly once the environment is hermetic. `tests/test_k8s.py`'s disabled-path test already implements exactly this HOME/USERPROFILE redirection (per RESEARCH Pattern 2/Pitfall 2 guidance), so the automated pytest suite (Task 3) is unaffected and passes cleanly with 100% coverage using the real dev-machine kubeconfig present but ignored.
- **Files modified:** None (verification-only; confirmed existing `tests/test_k8s.py` hermetic isolation already handles this correctly)
- **Verification:** `env -u KUBERNETES_SERVICE_HOST -u KUBECONFIG HOME=<empty-tmp-dir> USERPROFILE=<empty-tmp-dir> python -c "...assert get_k8s_clients()==(None,None)..."` → `OK`. Full `pytest` run (Task 3) passes 13/13 at 100% coverage on this same machine, with its real kubeconfig present, because `test_k8s.py` isolates HOME/USERPROFILE per-test.
- **Committed in:** No separate commit — no code changed; documented here for transparency since the plan's literal verify command output differed from what a clean/CI machine would show.

---

**Total deviations:** 1 (environment-only, no code changes; Rule 3 investigation confirmed no fix was needed)
**Impact on plan:** None on scope or code. Confirms the RESEARCH document's Pitfall 2 was correctly anticipated and already mitigated by the `tests/test_k8s.py` design mandated in the plan's own `<action>` instructions.

## Issues Encountered
None beyond the deviation documented above.

## User Setup Required
None - no external service configuration required. `kubernetes==36.0.2` install was pre-approved by the reviewer (Task 1 checkpoint) before this agent began execution.

## Next Phase Readiness
- `apps/launchpad/` is a fully independent, testable Flask app ready for Phase 6 (UI shell) to build routes/templates on top of.
- `app.k8s.get_k8s_clients()`'s `(None, None)` / `(CoreV1Api, AppsV1Api)` contract is stable and ready for Phase 8 diagnostics to consume directly (D-07).
- `GET /health`'s plain-200 shape is ready for Phase 7 (STAT-03) to evolve in place into a Mongo-ping readiness probe.
- No blockers. Docker build/deploy of `apps/launchpad/` remains untested until Phase 8 (D-08/D-09 guarded-stub scope, as planned) — file-existence only in Phase 5, consistent with RESEARCH's Open Question #1 recommendation.

---
*Phase: 05-monorepo-scaffold-app-factory*
*Completed: 2026-07-08*
