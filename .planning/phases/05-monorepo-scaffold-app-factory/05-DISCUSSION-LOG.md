# Phase 5: Monorepo Scaffold + App Factory - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-08
**Phase:** 5-Monorepo Scaffold + App Factory
**Areas discussed:** Skeleton scope, k8s contract, Makefile targets, Coverage gate, Skeleton route

---

## Skeleton scope

| Option | Description | Selected |
|--------|-------------|----------|
| Factory + health route | create_app wires a minimal /health blueprint stub; extensions = k8s + metrics; Mongo deferred | ✓ |
| Bare factory only | create_app returns app with no blueprints; tests assert factory builds + k8s no-ops | |
| Factory + metrics + mongo | Wire all three extensions now (k8s, metrics, Flask-PyMongo + mongomock) | |

**User's choice:** Factory + health route
**Notes:** Test harness exercises a real route end-to-end (test_factory, test_health, test_k8s). MongoDB plumbing explicitly deferred to Phase 7/9; conftest mocks K8s client + `requests` only.

---

## k8s contract

| Option | Description | Selected |
|--------|-------------|----------|
| get_k8s_clients() → tuple | Single function: in-cluster → kubeconfig → (None, None); returns (CoreV1Api, AppsV1Api) when available | ✓ |
| Cached accessor + enabled flag | get_k8s_clients() + k8s_enabled(); result cached after first call | |

**User's choice:** get_k8s_clients() → tuple
**Notes:** No caching in Phase 5. `(None, None)` disabled state is the tested normal case locally. Contract is a Phase 8 diagnostics dependency — shape must stay stable. Cached accessor noted as a later optimization.

---

## Makefile targets

| Option | Description | Selected |
|--------|-------------|----------|
| Guarded stubs now | All six LP targets exist + shown in `make help`; test-launchpad works; others echo "Phase 8/10" and exit 0 | ✓ |
| Vars + test only | LP_* vars + working test-launchpad only; build/load/deploy added in Phases 8/10 | |

**User's choice:** Guarded stubs now
**Notes:** LP_IMAGE/LP_RELEASE/LP_CHART must not collide with or shadow field-guide-api's IMAGE/RELEASE/CHART. Stubs must not join the `up` aggregate or change v1.0 behavior.

---

## Coverage gate

| Option | Description | Selected |
|--------|-------------|----------|
| 100% from day one | pytest.ini sets --cov=app --cov-fail-under=100, matching field-guide-api | ✓ |
| High but not 100% | Start at 95% (global target), tighten to 100% in Phase 7 | |

**User's choice:** 100% from day one
**Notes:** Keeps Phase 7's "continues to pass at 100% coverage" criterion true by construction.

---

## Skeleton route

| Option | Description | Selected |
|--------|-------------|----------|
| /health stub, plain 200 | Create /health returning 200 now (no Mongo check); Phase 7 rewrites it in place into the readiness probe | ✓ |
| /healthz liveness + index | Ship neutral /healthz (liveness) and/or GET / index; leave /health for Phase 7 | |

**User's choice:** /health stub, plain 200
**Notes:** One route name, evolved across phases. Phase 7 (STAT-03) adds the Mongo ping + 503 to the same `/health` route.

---

## Claude's Discretion

- Exact config keys / env-var names in config.py (follow field-guide-api Config pattern).
- Blueprint file structure (routes/health.py vs routes/__init__.py) — mirror field-guide-api.
- Dockerfile contents — reuse proven multi-stage python:3.11-slim / non-root / gunicorn pattern.
- Fixture shape for mocking `requests` in conftest.
- Two-apps-share-`app`-package-name handling (separate .venv + cd-into-app-dir) — technical detail.

## Deferred Ideas

- Cached K8s client accessor + k8s_enabled() helper — later optimization (candidate Phase 8).
- Flask-PyMongo / mongomock wiring — Phase 7 (/health readiness, /api/status) and Phase 9 (CRUD).
- Real /health readiness (Mongo ping + 503) — Phase 7 (STAT-03).
- Working build/load/deploy/port-forward/smoke-launchpad targets — Phase 8 (chart) and Phase 10 (up-all).
- `_request_timeout=5` on K8s API calls — Phase 8 (DIAG-02).
