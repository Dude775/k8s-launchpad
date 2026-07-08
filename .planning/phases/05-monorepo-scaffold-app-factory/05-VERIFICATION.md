---
phase: 05-monorepo-scaffold-app-factory
verified: 2026-07-08T00:00:00Z
status: passed
score: 9/9 must-haves verified
overrides_applied: 0
---

# Phase 5: Monorepo Scaffold + App Factory Verification Report

**Phase Goal:** The launchpad app loads and its unit tests pass without a live cluster or kubeconfig
**Verified:** 2026-07-08
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `apps/launchpad/` is a separate Flask workload with its own `create_app` factory, requirements, Dockerfile, and conftest mocking K8s + requests | VERIFIED | `apps/launchpad/app/__init__.py` defines `create_app()`; own `requirements.txt`/`requirements-dev.txt` (no Flask-PyMongo/pymongo/mongomock); own `Dockerfile` (multi-stage, non-root UID 10001, gunicorn PID 1); `tests/conftest.py` has `k8s_disabled`/`k8s_enabled` (monkeypatch `app.k8s.get_k8s_clients`) and `mock_requests_get` (monkeypatch `requests.get`) |
| 2 | Importing `app.k8s` with no kubeconfig returns `(None, None)` — no exception at import time or `create_app()` time | VERIFIED | Ran independently (not via pytest): `env -u KUBERNETES_SERVICE_HOST -u KUBERNETES_SERVICE_PORT -u KUBECONFIG HOME=<empty tmp> USERPROFILE=<empty tmp> python -c "import app.k8s; from app import create_app; ...; assert get_k8s_clients()==(None,None)"` → `OK`. `app/k8s.py` catches `ConfigException` narrowly per loader (in-cluster first, then kubeconfig), never `except Exception`, never called at import or in `create_app()` |
| 3 | `GET /health` returns a plain 200 `{"status": "ok"}` with no Mongo check | VERIFIED | `app/routes/health.py` — no Mongo import, no try/except, no 503 branch. Confirmed via direct test client call in the same hermetic script above: `r.status_code==200 and r.get_json()=={"status":"ok"}` |
| 4 | The launchpad test suite passes at 100% coverage with no kind cluster and no kubeconfig present | VERIFIED | Ran `make test-launchpad` myself from repo root (real kind cluster present on this machine, per environment notes): 13 passed, `TOTAL 43 stmts 0 miss 100%`, `--cov-fail-under=100` gate satisfied. `tests/test_k8s.py` isolates `HOME`/`USERPROFILE` to stay hermetic against the real leftover kubeconfig (RESEARCH Pitfall 2), confirmed by direct hermetic run above passing independently of pytest's fixture isolation |
| 5 | `make test-launchpad` creates `.venv`, installs `requirements-dev.txt`, runs pytest, passes at 100% coverage | VERIFIED | Same `make test-launchpad` run — venv already present and reused idempotently, dev deps installed, pytest ran and passed 13/13 at 100% |
| 6 | `make help` lists both apps' targets — field-guide-api's and launchpad's — with no collision | VERIFIED | Ran `make help` myself: all 6 `*-launchpad` targets (`test-launchpad`, `build-launchpad`, `load-launchpad`, `deploy-launchpad`, `port-forward-launchpad`, `smoke-launchpad`) render alongside `test`, `build`, `load`, `deploy`, `up`, etc. — distinct target names, no overlap |
| 7 | build/load/deploy/port-forward/smoke-launchpad are guarded stubs that echo a Phase-8/10 notice and exit 0 | VERIFIED | Ran each myself: all five print the expected notice (`available in Phase 8...` / `available in Phase 10...`) and exit 0. Grepped for `docker\|helm\|kubectl` inside those five recipes — none present, only `@echo` |
| 8 | `LP_IMAGE`, `LP_RELEASE`, `LP_CHART` exist and do not override/shadow field-guide-api's `IMAGE`/`RELEASE`/`CHART` | VERIFIED | `Makefile` lines 10-19: `IMAGE`/`TAG`/`RELEASE`/`CHART` unchanged at `localhost:5001/field-guide-api` / `dev` / `field-guide-api` / `charts/field-guide-api`; `LP_IMAGE`/`LP_TAG`/`LP_RELEASE`/`LP_CHART` are distinct variable names at `localhost:5001/launchpad` / `dev` / `launchpad` / `charts/launchpad` |
| 9 | The existing `up` aggregate target and field-guide-api targets are unchanged; `make test` (field-guide-api) still passes | VERIFIED | `up: cluster-up build load deploy` unchanged (line 85); no `up-all` target exists (grep confirms absence). Ran `make test` myself: 32 passed, 100% coverage, unchanged from pre-phase behavior |

**Score:** 9/9 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/launchpad/app/__init__.py` | `create_app` factory, deferred blueprint import, metrics-only wiring | VERIFIED | Substantive: loads `Config`, applies overrides, `metrics.init_app(app)`, deferred `from app.routes.health import health_bp`, `register_blueprint` |
| `apps/launchpad/app/k8s.py` | Lazy `get_k8s_clients()` | VERIFIED | Substantive: in-cluster→kubeconfig→`(None,None)` fallback, narrow `except ConfigException` per loader |
| `apps/launchpad/app/routes/health.py` | `health_bp` — GET /health plain 200 | VERIFIED | `jsonify({"status": "ok"}), 200`, no Mongo |
| `apps/launchpad/app/config.py` | env-driven Config | VERIFIED | `_env_flag` helper, `DEBUG`/`TESTING` only, no MONGO_* keys |
| `apps/launchpad/app/extensions.py` | metrics singleton | VERIFIED | `PrometheusMetrics.for_app_factory()`, no PyMongo |
| `apps/launchpad/pytest.ini` | 100% coverage gate | VERIFIED | `--cov-fail-under=100`, `pythonpath = .` |
| `apps/launchpad/tests/conftest.py` | app/client fixtures + k8s_disabled/k8s_enabled + mock_requests_get | VERIFIED | All four fixtures present and consumed by tests (no dead fixtures) |
| `apps/launchpad/requirements.txt` | kubernetes==36.0.2, no Flask-PyMongo | VERIFIED | Flask==3.1.3, kubernetes==36.0.2, prometheus-flask-exporter==0.23.2, python-dotenv==1.2.2, gunicorn==26.0.0 |
| `apps/launchpad/Dockerfile` | multi-stage, non-root, gunicorn PID 1 | VERIFIED | python:3.11-slim builder+runtime, UID 10001, exec-form CMD, explicit COPY allowlist |
| `apps/launchpad/.dockerignore` | excludes .venv/tests/__pycache__/.env | VERIFIED | present and correct |
| `Makefile` | LP_* vars + six namespaced launchpad targets | VERIFIED | `test-launchpad` fully functional; five guarded stubs; `.PHONY` extended |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `app/__init__.py` | `app/routes/health.py` | deferred blueprint import + register_blueprint | WIRED | `register_blueprint(health_bp)` confirmed at runtime — `"health" in app.blueprints` asserted in test_factory.py and independently confirmed in my hermetic script |
| `tests/conftest.py` | `app/k8s.py` | `monkeypatch.setattr(k8s_module, 'get_k8s_clients', ...)` | WIRED | `k8s_disabled`/`k8s_enabled` fixtures patch the module attribute; consumed by `test_k8s_disabled_fixture`/`test_k8s_enabled_fixture` |
| `app/k8s.py` | `kubernetes.config.ConfigException` | narrow except per loader | WIRED | Confirmed by reading source; both `except ConfigException` blocks present, no bare `except Exception` |
| `Makefile test-launchpad` | `apps/launchpad/requirements-dev.txt` | cd + venv install + pytest | WIRED | Ran `make test-launchpad` myself — installs deps and runs pytest successfully |
| `Makefile help` | launchpad target `##` comments | existing awk help pattern | WIRED | Ran `make help` myself — all six launchpad targets rendered with descriptions |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| launchpad test suite green at 100% coverage, no cluster dependency | `make test-launchpad` (run from repo root, real kind cluster present) | 13 passed, TOTAL 100% coverage | PASS |
| field-guide-api test suite unaffected | `make test` | 32 passed, TOTAL 100% coverage | PASS |
| hermetic import + create_app + health + lazy k8s client | direct Python one-liner with env unset and HOME/USERPROFILE redirected to empty tmp dir | `OK` — 200 {"status":"ok"}, get_k8s_clients()==(None,None) | PASS |
| `make help` shows both apps' targets, no collision | `make help` | all 6 launchpad + all field-guide-api targets listed distinctly | PASS |
| guarded stubs exit 0, no cluster tooling invoked | `make build-launchpad load-launchpad deploy-launchpad port-forward-launchpad smoke-launchpad` | all five print Phase-8/10 notice, exit 0 | PASS |
| `up` target and `up-all` unchanged | `grep -n 'up:' Makefile`, `grep -n 'up-all' Makefile` | `up: cluster-up build load deploy` present; `up-all` absent | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| APP-01 | 05-01, 05-02 | Separate launchpad Flask app, own Dockerfile/requirements, create_app + env-driven config, Makefile tooling seam | SATISFIED | `apps/launchpad/` fully independent app tree + own Makefile LP_* namespace verified above |
| APP-02 | 05-01 | Lazy K8s client returning disabled signal without kubeconfig | SATISFIED | `get_k8s_clients()` confirmed to return `(None,None)` hermetically, never called at import/create_app time |

No orphaned requirements — REQUIREMENTS.md maps only APP-01/APP-02 to Phase 5, both are declared in plan frontmatter and satisfied.

### Anti-Patterns Found

None. Scanned all launchpad source files (`app/`, `tests/`, `wsgi.py`, `Dockerfile`, `requirements*.txt`, `pytest.ini`, `.env.example`, `.dockerignore`) for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER` and empty-implementation patterns (`return null`, `return {}`, `return []`, `=> {}`) — zero matches. Git status is clean; no stray `.env`, `.venv`, or kubeconfig staged. Both task commits (`f50ba9d`, `652eb0e` for 05-01; `44bcc5c` for 05-02) exist in history.

### Human Verification Required

None. Both `checkpoint:human-verify` gates in this phase (Task 1 of 05-01: kubernetes==36.0.2 package legitimacy; Task 2 of 05-02: `make test-launchpad` green end-to-end run) were blocking gates already executed and approved during phase execution — and both underlying claims were independently re-verified by this verifier by re-running the actual commands (not by trusting the SUMMARY narrative). No `<human-check>` blocks were found deferred to end-of-phase in either PLAN file.

### Gaps Summary

No gaps. All 4 ROADMAP.md Success Criteria for Phase 5, all `must_haves` truths/artifacts/key_links declared in both plan frontmatters, and both REQUIREMENTS.md acceptance criteria (APP-01, APP-02) are independently confirmed against the actual codebase — not merely asserted by the SUMMARY.md files. Both test suites were re-run by the verifier (not assumed from SUMMARY claims) and both pass. The one documented deviation in 05-01-SUMMARY.md (environment-only: this dev machine's real leftover kubeconfig initially caused the plan's literal verify command to see a live client instead of `(None,None)`) was independently reproduced and confirmed correctly mitigated — the hermetic HOME/USERPROFILE redirection in `tests/test_k8s.py` and in my own direct verification script both return `(None, None)` as required, proving the RESEARCH-anticipated pitfall was genuinely handled in code, not just claimed.

---

*Verified: 2026-07-08*
*Verifier: Claude (gsd-verifier)*
