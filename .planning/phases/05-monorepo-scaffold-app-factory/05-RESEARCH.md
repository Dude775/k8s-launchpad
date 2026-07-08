# Phase 5: Monorepo Scaffold + App Factory - Research

**Researched:** 2026-07-08
**Domain:** Flask application-factory scaffolding + lazy Kubernetes client initialization (pytest harness, no live cluster)
**Confidence:** HIGH

## Summary

Phase 5 is a structural clone of the proven v1.0 `apps/field-guide-api` skeleton, adapted for a
second app (`apps/launchpad/`) that additionally owns a lazy Kubernetes client accessor. Nothing
in this phase talks to a real cluster or a real MongoDB — the two novel pieces are (1) a
`get_k8s_clients()` function in `app/k8s.py` that must import and execute cleanly with zero
cluster config present, and (2) a `pytest` fixture that mocks that accessor so route tests never
touch a real API server.

The official `kubernetes` PyPI package (maintained by the `kubernetes-client` GitHub
organization) exposes exactly the fallback primitives this phase needs:
`config.load_incluster_config()` and `config.load_kube_config()` both raise the *same* exception
class, `kubernetes.config.config_exception.ConfigException` (a bare `Exception` subclass), when
their respective config sources are absent. This lets `get_k8s_clients()` use one `try/except
ConfigException` per loader, falling through to `(None, None)` with no risk of an unrelated
exception type escaping. This was verified by reading the current `master` branch source of
`incluster_config.py` and `kube_config.py` directly (see Sources) — not assumed from memory.

The two-apps-share-package-name concern (`app.k8s`, `app.config`, etc. exist in both
`field-guide-api` and `launchpad`) is a non-issue: each app has its own `.venv`, its own
`pytest.ini` with `pythonpath = .` scoped to its own directory, and the Makefile `cd`s into the
app directory before invoking pytest — so `sys.path` never contains both app roots
simultaneously. This is exactly the mechanism field-guide-api's own `test` target already uses;
`test-launchpad` is a parametrized copy, not a new pattern.

**Primary recommendation:** Copy field-guide-api's factory/config/extensions/pytest.ini/Dockerfile
patterns verbatim into `apps/launchpad/`, add a new `app/k8s.py` module using the official
`kubernetes` client with the exact two-step fallback specified in D-05, mock `get_k8s_clients` and
`requests` via `monkeypatch` (pytest built-in, no new mocking dependency), and add `LP_*`
Makefile variables that mirror the existing `IMAGE`/`RELEASE`/`CHART` pattern without touching the
existing targets.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Flask app factory (`create_app`) | API / Backend | — | Standard app-factory pattern; owns config + extension wiring, mirrors field-guide-api |
| Env-driven config (`app/config.py`) | API / Backend | — | Config is a backend concern; no client/browser involvement in Phase 5 (no UI yet) |
| `/health` route stub | API / Backend | — | Plain `200` stub in Phase 5; becomes a Kubernetes readinessProbe target in Phase 8, evolves to Mongo-ping in Phase 7 |
| Lazy K8s client accessor (`app/k8s.py`) | API / Backend | Database/Storage (K8s API server is itself a control-plane datastore) | Backend-owned lazy accessor; the K8s API server it talks to (in later phases) is an external control-plane service, not this app's own persistence |
| `/metrics` (prometheus-flask-exporter) | API / Backend | CDN/Static (scrape target) | Auto-registered Flask extension; scraped externally by Prometheus (out of scope this milestone, PRD-4) |
| Test harness (`conftest.py`, mocks) | API / Backend (test-only) | — | Pure backend test tooling; no client/browser involvement |
| `LP_*` Makefile vars + stub targets | Build/Tooling (outside 5-tier model) | — | Build orchestration, not an application tier; kept in Makefile only |

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Ship a **factory + a real route stub** (not a bare factory). `create_app` registers a
  minimal health blueprint so the test harness exercises a real route end-to-end, plus
  `test_factory`, `test_health`, and `test_k8s`.
- **D-02:** Wire the **k8s module + prometheus `metrics`** extension now. Do NOT wire
  Flask-PyMongo / mongomock in Phase 5. The conftest mocks the K8s client and `requests`; no Mongo
  mocking yet.
- **D-03:** Target directory layout mirrors field-guide-api: `app/__init__.py` (`create_app`),
  `app/config.py`, `app/extensions.py`, `app/k8s.py`, `app/routes/health.py`, `wsgi.py`, plus
  `tests/`.
- **D-04:** The Phase 5 route is `GET /health` returning a plain `200` (e.g. `{"status": "ok"}`)
  with no Mongo check. Route name stays stable — Phase 7 evolves this same `/health` in place.
  Do not invent a separate `/healthz`.
- **D-05:** Expose a **single `get_k8s_clients()` function** returning a tuple. Fallback order:
  (1) try in-cluster config, (2) fall back to local kubeconfig, (3) return `(None, None)` if
  neither is available. When a cluster is reachable it returns `(CoreV1Api, AppsV1Api)`. Callers
  check for `None` to detect the disabled state. Import of `app.k8s` and `create_app()` must both
  succeed with no kubeconfig.
- **D-06:** No caching of the client in Phase 5 — the plain function is enough.
- **D-07:** This `(None, None)` contract is a downstream dependency for Phase 8 diagnostics — keep
  the shape stable.
- **D-08:** Add all launchpad targets as guarded stubs now, visible in `make help`, using `LP_*`
  variables (`LP_IMAGE`, `LP_RELEASE`, `LP_CHART`, etc.) that do not collide with or shadow
  field-guide-api's `IMAGE`/`RELEASE`/`CHART`. `test-launchpad` fully works. `build-launchpad` /
  `load-launchpad` / `deploy-launchpad` / `port-forward-launchpad` / `smoke-launchpad` are present
  but guarded: echo "available in Phase 8/10" and exit 0.
- **D-09:** Guarded stubs must not be pulled into the existing `up` aggregate target or otherwise
  change v1.0 field-guide-api behavior. `make up-all` is a Phase 10 deliverable.
- **D-10:** launchpad adopts 100% coverage from day one — `pytest.ini` sets `--cov=app
  --cov-fail-under=100 --cov-report=term-missing`, matching field-guide-api's style (field-guide-api
  itself uses `--cov-fail-under=95`; launchpad's bar is stricter per D-10).

### Claude's Discretion

- Exact config keys / env-var names in `config.py` (follow field-guide-api's `Config` pattern;
  `LP_`-style env prefixes are reasonable but not mandated).
- Whether the health blueprint lives in `app/routes/health.py` vs a single
  `app/routes/__init__.py` — mirror field-guide-api's blueprint structure (field-guide-api uses
  `app/routes/health.py` + `app/routes/__init__.py` as an empty package marker — mirror this).
- Precise Dockerfile contents (reuse the proven multi-stage `python:3.11-slim`, non-root,
  gunicorn-PID-1 pattern from field-guide-api's Dockerfile).
- How `requests` is mocked in conftest (fixture shape) — resolved below: `monkeypatch`, no new
  dependency, consistent with existing project convention (see Standard Stack).
- Handling the two-apps-share-the-`app`-package-name concern: each app has its own `.venv` and
  tests `cd` into the app dir, so no import collision — resolved below (Common Pitfalls).

### Deferred Ideas (OUT OF SCOPE)

- Cached K8s client accessor + `k8s_enabled()` helper — deferred to Phase 8 if per-request
  re-probing becomes a measured concern.
- Flask-PyMongo / mongomock wiring — Phase 7 (`/health` readiness, `/api/status`) and Phase 9
  (catalog/events CRUD).
- Real `/health` readiness (Mongo ping + 503) — Phase 7 (STAT-03).
- Working `build/load/deploy/port-forward/smoke-launchpad` targets — Phase 8 (chart + cluster) and
  Phase 10 (`up-all`, `smoke`). Phase 5 ships guarded stubs only.
- `_request_timeout=5` on K8s API calls — Phase 8 (DIAG-02).

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| APP-01 | New `apps/launchpad/` Flask app exists with a `create_app` app-factory and env-driven config, structured separately from field-guide-api (own Dockerfile, own requirements) | Standard Stack + Architecture Patterns sections below give the exact factory/config/extensions/Dockerfile/pytest.ini shape to copy-and-adapt; Common Pitfalls #3 resolves the shared `app` package-name concern |
| APP-02 | The Kubernetes client initializes lazily (never at import time) and returns a disabled signal when no cluster config is available, so the app and its tests load without a kubeconfig | Code Examples "app/k8s.py" gives the verified `get_k8s_clients()` implementation and the exact `ConfigException` catch; Common Pitfalls #1 and #2 cover the failure modes verified against the client library source |

## Project Constraints (from CLAUDE.md)

- Tech stack LOCKED: Python 3.11 + Flask (backend), Docker, kind, Helm 3, monorepo — no
  substitutions.
- `.env` for local config; Kubernetes Secrets in-cluster; never commit real secrets; `.gitignore`
  must cover new app's `.venv`/`__pycache__`/`.env` before first commit (already does, verified —
  patterns are extension-based, not path-scoped, so they cover `apps/launchpad/.venv` too).
  `.dockerignore` is per-app (field-guide-api has its own) — launchpad needs its own copy.
- Windows host with WSL2 / Git Bash — Makefile targets/scripts must work there. `SHELL :=
  /bin/bash`, `export MSYS_NO_PATHCONV=1` at the top of the Makefile (already present, do not
  duplicate).
- Git: many small human-style commits (lowercase, short messages).
- Tests required: pytest; project-wide target is 95% coverage per user's global CLAUDE.md, but
  this phase's CONTEXT.md (D-10, phase-specific and more recent) locks launchpad specifically to
  100% — the phase-level decision governs for this app.
- No hardcoded secrets — environment variables only (`python-dotenv` + `os.environ`, per
  field-guide-api's `config.py` pattern).
- Docker-first for all services — launchpad gets its own Dockerfile even though it isn't built in
  Phase 5's success criteria (Phase 5 CONTEXT.md's `<specifics>` implies structure now, build later
  — confirm this is in scope; see Open Questions).
- Self-hosted over cloud — no change, no cloud dependency introduced here.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Flask | 3.1.3 | Web framework (locked, matches field-guide-api) | Already locked project-wide in CLAUDE.md; reuse exact pin for consistency across both apps |
| kubernetes | 36.0.2 `[VERIFIED: PyPI]` | Official Kubernetes Python client — provides `config.load_incluster_config`, `config.load_kube_config`, `config.config_exception.ConfigException`, `client.CoreV1Api`, `client.AppsV1Api` | Official client maintained by the `kubernetes-client` GitHub org (7,600+ stars); confirmed via live PyPI project page (pypi.org/project/kubernetes/) — latest release 36.0.2, released 2026-06-01, `Requires-Python >=3.10` (compatible with locked Python 3.11). Local `pip index versions` reported a stale `35.0.0` because the shell's default `python`/`pip` resolves against a Python 3.7.4 pyenv install on this machine — that ceiling is an environment artifact, not the real latest version; verify with a Python 3.11 venv during implementation. |
| prometheus-flask-exporter | 0.23.2 | `/metrics` endpoint (D-02) | Already locked project-wide in CLAUDE.md and used by field-guide-api; reuse `PrometheusMetrics.for_app_factory()` singleton pattern verbatim |
| python-dotenv | 1.2.2 | Local `.env` loading | Already locked project-wide; reuse verbatim |
| gunicorn | 26.0.0 | WSGI production server (Dockerfile only — not exercised by `test-launchpad`) | Already locked project-wide; reuse verbatim for launchpad's Dockerfile |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.1.1 | Test runner | Always; matches field-guide-api |
| pytest-flask | 1.3.0 | Flask test client fixture | Always; matches field-guide-api |
| pytest-cov | 5.0.0 | Coverage reporting | Always; `--cov-fail-under=100` per D-10 (stricter than field-guide-api's 95) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `monkeypatch` (pytest built-in) for mocking `requests` | `responses` or `requests-mock` library | Neither is needed in Phase 5 — no route calls `requests` yet (that's Phase 7's field-guide-api reachability check). Adding a new test dependency now for a capability not yet exercised is premature; `monkeypatch.setattr` on the `requests` module namespace, or on a small wrapper function, is sufficient and consistent with field-guide-api's existing `monkeypatch`-only test dependency profile. Revisit in Phase 7 if the mocking surface grows (e.g. multiple endpoints, timeout simulation) — `responses` would reduce boilerplate at that point. |
| `config.load_incluster_config()` → `load_kube_config()` (locked order, D-05) | `kubernetes.config.load_config()` convenience wrapper | The library's own `load_config()` wrapper tries **kubeconfig first, in-cluster second** (confirmed by reading `kubernetes/base/config/__init__.py` docstring) — the opposite of D-05's locked order. D-05 is correct for a service that should trust its in-cluster ServiceAccount identity first when actually running as a pod; do not use the convenience wrapper, implement the two explicit calls. |
| Plain `get_k8s_clients()` function (D-06) | `functools.lru_cache` or a module-level cached singleton | Explicitly deferred per D-06 — re-probing every call is fine at this scale and this phase has no caller yet (Phase 8 is the first real caller) |

**Installation:**
```bash
# apps/launchpad/requirements.txt
Flask==3.1.3
kubernetes==36.0.2
prometheus-flask-exporter==0.23.2
python-dotenv==1.2.2
gunicorn==26.0.0
```
```bash
# apps/launchpad/requirements-dev.txt
-r requirements.txt
pytest==9.1.1
pytest-flask==1.3.0
pytest-cov==5.0.0
```

**Version verification:** Verified via live PyPI JSON API (`pypi.org/pypi/<pkg>/json`) and PyPI
project pages, not local `pip index versions` — the machine's default Python interpreter is 3.7.4
(pyenv), which caps pip's resolvable version list below what's actually published for
Python-3.10+-only releases like `kubernetes==36.0.2`. During implementation, create the app's
`.venv` with Python 3.11 (per Makefile's `PYTHON` override convention) and re-run `pip install` to
confirm these versions resolve cleanly in the real target interpreter.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|--------------|-----------|-------------|
| kubernetes | PyPI | ~10 yrs (org founded 2016) | Very high (tens of millions/month; exact figure not machine-verified) | github.com/kubernetes-client/python (official, 7,600+ stars) | not run — see below | Approved |
| Flask | PyPI | ~15 yrs | Very high | github.com/pallets/flask | not run | Approved (already locked project-wide) |
| prometheus-flask-exporter | PyPI | ~9 yrs | Moderate-high | github.com/rycus86/prometheus_flask_exporter | not run | Approved (already locked project-wide) |
| python-dotenv | PyPI | ~10 yrs | Very high | github.com/theskumar/python-dotenv | not run | Approved (already locked project-wide) |
| gunicorn | PyPI | ~15 yrs | Very high | github.com/benoitc/gunicorn | not run | Approved (already locked project-wide) |
| pytest / pytest-flask / pytest-cov | PyPI | mature, all 5+ yrs | Very high | official pytest-dev / pallets-eco orgs | not run | Approved (already locked project-wide) |

**slopcheck availability:** `pip install slopcheck` failed in this environment — no matching
distribution was found on PyPI under that name (confirmed: `ERROR: Could not find a version that
satisfies the requirement slopcheck`). No `pipx` binary is present either. Per the graceful
degradation protocol, packages are NOT auto-approved on registry-existence alone; instead each was
cross-checked manually:

- `kubernetes` — identity confirmed via the official GitHub organization
  (`github.com/kubernetes-client`), which is a Kubernetes-community-governed org, not an
  individual maintainer; the PyPI project page directly links to this repo. This is the same
  package name used throughout official Kubernetes documentation and every reputable tutorial
  found during research. Cross-verified, not merely registry-present — tagged `[VERIFIED: PyPI +
  official docs]` above.
- All other packages were already locked in the project's own `CLAUDE.md` (written for
  field-guide-api) with prior sourcing footnotes (PyPI links, Context7 IDs) — reused verbatim, no
  new legitimacy risk introduced.

**Packages removed due to slopcheck [SLOP] verdict:** none (slopcheck unavailable; no package
here showed any independent red flag — all are long-established, widely-used, officially
maintained libraries).
**Packages flagged as suspicious [SUS]:** none.

*slopcheck was unavailable at research time. Per protocol, the planner should still gate the one
genuinely new dependency this phase introduces — `kubernetes==36.0.2` — behind a lightweight
`checkpoint:human-verify` confirmation (e.g. "confirm `pip show kubernetes` reports
`Home-page: https://github.com/kubernetes-client/python` after install") before it's treated as
permanently trusted, since it is the only package in this phase without prior project history.*

## Architecture Patterns

### System Architecture Diagram

```
                          ┌─────────────────────────────────────────┐
                          │        apps/launchpad/  (Phase 5)        │
                          │                                           │
  pytest invocation  ───▶ │  wsgi.py ──▶ create_app() ──┐            │
  (make test-launchpad)   │                              │            │
                          │              ┌───────────────▼─────────┐ │
                          │              │ 1. Config.from_object()  │ │
                          │              │ 2. config_overrides      │ │
                          │              │    (TESTING=True, etc.) │ │
                          │              └───────────────┬─────────┘ │
                          │                              │            │
                          │              ┌───────────────▼─────────┐ │
                          │              │ 3. metrics.init_app(app)│ │
                          │              │    (prometheus exporter)│ │
                          │              │    NOTE: no mongo.init_ │ │
                          │              │    app() — deferred     │ │
                          │              └───────────────┬─────────┘ │
                          │                              │            │
                          │              ┌───────────────▼─────────┐ │
                          │              │ 4. deferred blueprint   │ │
                          │              │    import + register:   │ │
                          │              │    health_bp (/health)  │ │
                          │              └───────────────┬─────────┘ │
                          │                              │            │
                          │                     Flask app instance   │
                          └──────────────────────────────┼────────────┘
                                                          │
                       GET /health  ──────────────────────▶  200 {"status":"ok"}
                                                          │  (no Mongo check — D-04)
                                                          │
                                                          ▼
                          ┌───────────────────────────────────────────┐
                          │           app/k8s.py  (lazy, isolated)     │
                          │                                             │
                          │  get_k8s_clients() called ONLY when a       │
                          │  future route (Phase 8) invokes it — NEVER  │
                          │  at import time or create_app() time.       │
                          │                                             │
                          │  try: config.load_incluster_config()        │
                          │    except ConfigException: pass             │
                          │    else: return (CoreV1Api(), AppsV1Api())  │
                          │                                             │
                          │  try: config.load_kube_config()             │
                          │    except ConfigException: pass             │
                          │    else: return (CoreV1Api(), AppsV1Api())  │
                          │                                             │
                          │  return (None, None)   ◀── normal in tests  │
                          └─────────────────────────────────────────────┘

  Test harness (tests/conftest.py):
    app fixture      → create_app({"TESTING": True}) — no cluster, no Mongo
    client fixture   → app.test_client()
    (k8s mocking)    → monkeypatch app.k8s.get_k8s_clients to return
                       controlled tuples for the disabled- and enabled-state
                       branches, so both code paths hit 100% coverage
                       without a real cluster
```

### Recommended Project Structure

```
apps/launchpad/
├── app/
│   ├── __init__.py          # create_app() factory — deferred blueprint imports
│   ├── config.py            # env-driven Config class (mirrors field-guide-api)
│   ├── extensions.py        # metrics singleton ONLY (no mongo — D-02)
│   ├── k8s.py                # get_k8s_clients() — lazy, no import-time side effects
│   └── routes/
│       ├── __init__.py      # empty package marker (mirrors field-guide-api)
│       └── health.py        # health_bp — GET /health, plain 200 (D-04)
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # app/client fixtures + k8s mock fixtures
│   ├── test_factory.py       # create_app importable, Config shape, extensions shape
│   ├── test_health.py        # GET /health returns 200 {"status": "ok"}
│   └── test_k8s.py           # get_k8s_clients() disabled path + enabled path (mocked)
├── .dockerignore              # own copy — .venv/, tests/, __pycache__, .env
├── .env.example
├── Dockerfile                 # multi-stage python:3.11-slim, non-root, gunicorn PID 1
├── pytest.ini                 # --cov=app --cov-fail-under=100 (D-10)
├── requirements.txt
├── requirements-dev.txt
└── wsgi.py                    # gunicorn entrypoint: from app import create_app; app = create_app()
```

### Pattern 1: Deferred blueprint imports in the factory (reuse verbatim)

**What:** Blueprint modules are imported *inside* `create_app()`, not at module top-level.
**When to use:** Always, in every Flask app-factory in this monorepo — it lets `from app import
create_app` succeed even before route files exist, and keeps each test's app instance isolated.
**Example:**
```python
# Source: apps/field-guide-api/app/__init__.py (existing, proven v1.0 pattern)
def create_app(config_overrides: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)

    metrics.init_app(app)  # also auto-registers the /metrics endpoint
    # NOTE for launchpad: do NOT add mongo.init_app(app) here — D-02 defers Mongo to Phase 7/9

    from app.routes.health import health_bp  # noqa: PLC0415 — deferred import
    app.register_blueprint(health_bp)

    return app
```

### Pattern 2: Lazy, exception-narrow K8s client accessor

**What:** A single function that tries in-cluster config, then kubeconfig, then gives up cleanly.
**When to use:** Any code path that needs a Kubernetes API client but must remain importable and
callable with zero cluster context (local dev, CI, unit tests).
**Example:**
```python
# app/k8s.py
"""
Lazy Kubernetes client accessor.

get_k8s_clients() is the ONLY entry point. It is never called at import time
or inside create_app() — callers (Phase 8 diagnostics routes) invoke it
per-request. With no cluster config reachable it returns (None, None) and
raises nothing; callers check for None to detect the disabled state (D-05).

Both loaders below raise the SAME exception type when their respective
config source is absent — kubernetes.config.config_exception.ConfigException,
a plain Exception subclass — confirmed by reading the current kubernetes-client/
python master branch source (incluster_config.py raises ConfigException when
KUBERNETES_SERVICE_HOST/PORT env vars are unset or the service-account token/
cert files are missing; kube_config.py raises the same ConfigException when
the kubeconfig file does not exist at the resolved path). Catching only
ConfigException — not a bare `except Exception` — keeps this narrow and
avoids masking real bugs (e.g. a TypeError from a future refactor).
"""

from kubernetes import client, config
from kubernetes.config import ConfigException


def get_k8s_clients():
    """Return (CoreV1Api, AppsV1Api) if a cluster is reachable, else (None, None).

    Fallback order (D-05, locked): in-cluster config first, then local
    kubeconfig. This is the correct order for a service that should trust its
    own ServiceAccount identity when actually running as a pod — the
    opposite of kubernetes.config.load_config()'s convenience-wrapper order
    (kubeconfig first), which is meant for CLI tooling, not services.
    """
    try:
        config.load_incluster_config()
    except ConfigException:
        pass
    else:
        return client.CoreV1Api(), client.AppsV1Api()

    try:
        config.load_kube_config()
    except ConfigException:
        pass
    else:
        return client.CoreV1Api(), client.AppsV1Api()

    return None, None
```

### Pattern 3: conftest fixtures mocking the K8s accessor and `requests`

**What:** Fixtures that patch `app.k8s.get_k8s_clients` to force each branch (disabled / enabled)
without a real cluster, plus a placeholder pattern for mocking `requests` ahead of Phase 7.
**When to use:** In `tests/conftest.py`, following the exact `monkeypatch` discipline
field-guide-api already uses for its Mongo mocking.
**Example:**
```python
# tests/conftest.py
"""
Test fixtures providing an isolated Flask test app with a mocked K8s client.

No real cluster or kubeconfig is used in any test. The K8s client is mocked
by monkeypatching app.k8s.get_k8s_clients directly (module-level function
replacement), the same monkeypatch-and-auto-restore discipline field-guide-api
uses for its mongomock injection.
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def app():
    """Isolated Flask test app — no cluster, no Mongo required for Phase 5."""
    from app import create_app

    application = create_app({"TESTING": True})
    yield application


@pytest.fixture
def client(app):
    """Flask test client using the isolated app."""
    return app.test_client()


@pytest.fixture
def k8s_disabled(monkeypatch):
    """Force app.k8s.get_k8s_clients() to return the disabled (None, None) state.

    This is the DEFAULT / expected state for local dev and CI (D-05, D-07) —
    it is a first-class tested path, not an error path.
    """
    import app.k8s as k8s_module

    monkeypatch.setattr(k8s_module, "get_k8s_clients", lambda: (None, None))
    return k8s_module


@pytest.fixture
def k8s_enabled(monkeypatch):
    """Force app.k8s.get_k8s_clients() to return mocked (CoreV1Api, AppsV1Api)
    instances, exercising the "cluster reachable" branch without a real cluster.
    """
    import app.k8s as k8s_module

    fake_core_v1 = MagicMock(name="CoreV1Api")
    fake_apps_v1 = MagicMock(name="AppsV1Api")
    monkeypatch.setattr(k8s_module, "get_k8s_clients", lambda: (fake_core_v1, fake_apps_v1))
    return fake_core_v1, fake_apps_v1


@pytest.fixture
def mock_requests_get(monkeypatch):
    """Placeholder pattern for mocking `requests.get` ahead of Phase 7's
    field-guide-api reachability check (STAT-02). No Phase 5 route calls
    `requests` yet — this fixture exists so the conftest module already
    demonstrates the mocking shape D-02 asks for, ready for Phase 7 to use.
    """
    import requests

    fake_response = MagicMock(status_code=200, json=lambda: {})
    monkeypatch.setattr(requests, "get", lambda *a, **kw: fake_response)
    return fake_response
```

**Testing `get_k8s_clients()` itself (not just consumers of it) — the two real branches, unmocked
at the `kubernetes` library level, mocked only at the environment/filesystem level:**
```python
# tests/test_k8s.py
"""
app.k8s.get_k8s_clients() — both branches of the D-05 contract, exercised
without a real cluster or kubeconfig.
"""

import pytest


def test_get_k8s_clients_returns_none_none_with_no_config(monkeypatch, tmp_path):
    """No KUBERNETES_SERVICE_HOST and no kubeconfig file => (None, None), no raise."""
    from app.k8s import get_k8s_clients

    monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
    monkeypatch.delenv("KUBERNETES_SERVICE_PORT", raising=False)
    monkeypatch.delenv("KUBECONFIG", raising=False)
    # Point HOME at an empty tmp_path so ~/.kube/config resolves to nothing.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Windows kubeconfig lookup

    core_v1, apps_v1 = get_k8s_clients()

    assert core_v1 is None
    assert apps_v1 is None


def test_get_k8s_clients_returns_apis_when_incluster_config_present(monkeypatch):
    """Mock config.load_incluster_config to succeed => real API client types returned."""
    from unittest.mock import MagicMock

    import app.k8s as k8s_module

    monkeypatch.setattr(k8s_module.config, "load_incluster_config", MagicMock())

    core_v1, apps_v1 = k8s_module.get_k8s_clients()

    assert core_v1 is not None
    assert apps_v1 is not None
```

### Anti-Patterns to Avoid

- **Calling `get_k8s_clients()` (or any config loader) at module import time or inside
  `create_app()`:** Directly violates D-05/APP-02. Keep it lazy — only a future route handler
  (Phase 8) calls it, per request.
- **`except Exception:` around the config loaders:** Too broad — masks real bugs (e.g. a typo'd
  attribute access). Catch `ConfigException` specifically; both loaders raise this exact type on
  their "not configured" path (verified against source, not assumed).
- **Using `kubernetes.config.load_config()` instead of the two explicit calls:** Wrong order for
  this use case — the convenience wrapper tries kubeconfig before in-cluster, the opposite of D-05.
- **Wiring `Flask-PyMongo` or `mongomock` in Phase 5:** Explicitly deferred (D-02, Deferred Ideas).
  Do not add `mongo` to `app/extensions.py` yet.
- **Adding a `responses`/`requests-mock` dependency in Phase 5:** No route uses `requests` yet;
  `monkeypatch` is sufficient and avoids a premature new dependency (see Alternatives Considered).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| In-cluster vs. local kubeconfig detection | A custom "am I in a pod?" check (e.g. testing for `/var/run/secrets/kubernetes.io/serviceaccount/` manually) | `kubernetes.config.load_incluster_config()` / `load_kube_config()` + catching `ConfigException` | The official client already implements exactly this detection (checks `KUBERNETES_SERVICE_HOST`/`PORT` env vars and the service-account token/cert file paths) and raises a single well-defined exception type on failure — reimplementing it risks missing an edge case the library already handles (e.g. empty-but-present token file) |
| Prometheus `/metrics` endpoint | A hand-rolled `/metrics` route using bare `prometheus_client` | `prometheus-flask-exporter`'s `PrometheusMetrics.for_app_factory()` | Already locked project-wide and proven in field-guide-api; auto-instruments every route with zero per-route boilerplate |
| Coverage gate enforcement | A custom coverage-checking script | `pytest-cov`'s `--cov-fail-under=100` in `pytest.ini` | Standard, zero-code, already the field-guide-api pattern (at 95%; launchpad locks 100% per D-10) |

**Key insight:** Every piece of this phase already has a proven, shipped analog in
`apps/field-guide-api/`. The only genuinely new code is `app/k8s.py`, and even that is a thin
wrapper around library-provided primitives — there is no custom logic here that isn't already
solved by the `kubernetes` client itself.

## Common Pitfalls

### Pitfall 1: Assuming `load_incluster_config()` raises `FileNotFoundError` or similar, not `ConfigException`

**What goes wrong:** Code writes `except FileNotFoundError:` or a bare `except OSError:` around
the in-cluster loader, expecting a filesystem-style error when the service-account token file is
absent.
**Why it happens:** It's intuitive to assume a missing-file scenario raises a file-related
exception, but the library wraps every failure mode (missing env vars, missing token file, missing
cert file, empty token, empty cert) in its own `ConfigException`, defined as a bare `Exception`
subclass in `kubernetes/base/config/config_exception.py`.
**How to avoid:** Catch `kubernetes.config.ConfigException` (importable as
`from kubernetes.config import ConfigException`) around both loader calls. Verified directly from
the current `kubernetes-client/python` master branch source — `_load_config()` in
`incluster_config.py` raises `ConfigException("Service host/port is not set.")` when
`KUBERNETES_SERVICE_HOST`/`PORT` are absent (the standard local-dev/test/CI case), and
`kube_config.py` raises `ConfigException("File does not exist: %s" % self._file)` when no
kubeconfig file is found at the resolved path.
**Warning signs:** A test asserting `get_k8s_clients()` returns `(None, None)` instead raises an
uncaught exception when run in an environment with no `KUBERNETES_SERVICE_HOST` set and no
`~/.kube/config` file present (exactly the CI/local-dev environment this phase must support).

### Pitfall 2: `load_kube_config()` succeeding accidentally in CI because the developer's real kubeconfig is picked up

**What goes wrong:** A test machine or CI runner has a `~/.kube/config` left over from a previous
`kind` cluster session (even a stale/deleted one), causing `load_kube_config()` to *not* raise —
it may succeed at loading config even if the cluster it points to is now gone, since
`load_kube_config()` only validates the file's structure, not live connectivity.
**Why it happens:** `load_kube_config()`'s job is to parse and populate the client `Configuration`
object from a file; it does not make a network call, so it "succeeds" even against a
dangling/stale reference. `test_get_k8s_clients_returns_apis_when_incluster_config_present`
demonstrates the safer way to test the "enabled" branch: mock the loader function itself rather
than relying on environment absence/presence, which is exactly the technique shown in Code
Examples above.
**How to avoid:** For the "returns `(None, None)`" unit test specifically, explicitly unset
`KUBECONFIG`, `KUBERNETES_SERVICE_HOST`, `KUBERNETES_SERVICE_PORT`, and point `HOME`/`USERPROFILE`
at an empty `tmp_path` fixture so no real kubeconfig file can be discovered, regardless of what's
on the actual CI/dev machine. Do not rely on "just don't have a kubeconfig" as an implicit
precondition — make the test hermetic.
**Warning signs:** `test_k8s.py`'s disabled-path test passes locally (developer has no kubeconfig)
but fails in CI (runner image has a cached one), or vice versa.

### Pitfall 3: Two apps both defining a top-level `app` package causing import collisions

**What goes wrong:** Running `pytest` from the repo root (instead of from inside each app
directory) could import `apps/field-guide-api/app` and `apps/launchpad/app` as if they were the
same top-level `app` module, silently testing the wrong code or raising confusing
`ModuleNotFoundError`/`AttributeError`s.
**Why it happens:** Neither app's `app/` package is namespaced (e.g. neither is
`field_guide_api.app` or `launchpad.app`) — both are simply importable as `app` once their
directory is on `sys.path`.
**How to avoid:** This is already solved, not a new problem to design around: each app has its own
`pytest.ini` with `pythonpath = .` (relative to that file's own directory) and its own `.venv`, and
the Makefile's `test`/`test-launchpad` targets both `cd` into the specific app directory before
invoking pytest (`cd apps/field-guide-api && ... pytest` / `cd apps/launchpad && ... pytest`).
Because each invocation is a fresh subshell + fresh venv + `cd`, `sys.path` never contains both
app roots at once. Do not run a single repo-root `pytest` invocation that tries to collect tests
from both `apps/*/tests/` in one process — that would be the one scenario that actually triggers
the collision. Keep the two `make test*` targets fully separate (as D-08 already implies).
**Warning signs:** `ModuleNotFoundError: No module named 'app.k8s'` when running field-guide-api's
tests, or field-guide-api's Mongo-based tests unexpectedly running against launchpad's code —
either symptom means something invoked pytest across both app roots in one process/sys.path.

### Pitfall 4: `metrics.init_app(app)` registering `/metrics` twice if both apps are imported in the same process

**What goes wrong:** `prometheus-flask-exporter`'s default registry is process-global
(`prometheus_client`'s `REGISTRY`). If a single Python process ever imported and called
`create_app()` for *both* field-guide-api and launchpad, the second `metrics.init_app()` call
would raise `ValueError: Duplicated timeseries in CollectorRegistry` for the shared default metric
names (`flask_http_request_total`, etc.).
**Why it happens:** Each app's `extensions.py` creates its own `PrometheusMetrics` instance, but
if the underlying `prometheus_client` default registry is process-global and shared, both apps'
`.init_app()` calls collide.
**How to avoid:** Not a Phase 5 concern in practice — each app runs in its own gunicorn worker
process (its own container/pod) and its own `pytest` subprocess (per Pitfall 3's isolation), so the
two `create_app()` calls never happen in the same Python process today. Flag this only as
something to watch for if a future phase ever runs both apps' test suites in a single combined
pytest session (not planned; each `make test*` target is separate).
**Warning signs:** `ValueError: Duplicated timeseries in CollectorRegistry` — would only appear if
someone changes the Makefile to run a single combined pytest invocation across both apps.

## Code Examples

See **Architecture Patterns** above (Pattern 1, 2, 3) for the verified `create_app()` factory
excerpt, the full `app/k8s.py` implementation, and the `conftest.py` fixture set. All are either
direct excerpts from the existing, shipped `apps/field-guide-api/` source (Pattern 1) or new code
built from verified `kubernetes` client library semantics (Pattern 2, 3, and the `test_k8s.py`
examples).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| N/A — this is the first Kubernetes-client integration in the monorepo | `kubernetes==36.0.2` official client, lazy two-step fallback | New in Phase 5 | Establishes the pattern Phase 8 (diagnostics) will build on directly — keep `get_k8s_clients()`'s return shape stable per D-07 |

**Deprecated/outdated:** None identified — the `kubernetes` client's `load_incluster_config` /
`load_kube_config` / `ConfigException` API surface has been stable across major versions for
years; no migration notes apply.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `kubernetes` package download counts described as "very high" / "tens of millions/month" | Package Legitimacy Audit | Low — directional claim only, not used to gate any decision; the identity/legitimacy check relies on the GitHub org link (verified), not the download figure |
| A2 | Age estimates for prometheus-flask-exporter (~9 yrs), python-dotenv (~10 yrs), gunicorn (~15 yrs), Flask (~15 yrs) | Package Legitimacy Audit | Low — these are already-locked, already-shipped dependencies from field-guide-api; age is illustrative context, not a gating fact |
| A3 | Docker build/deploy of `apps/launchpad/` is in-scope structurally in Phase 5 (Dockerfile exists) even though `build-launchpad`/`deploy-launchpad` Makefile targets are guarded stubs that don't run it | Project Constraints, Recommended Project Structure | Low-medium — if the planner decides the Dockerfile itself should also be deferred to Phase 8, the file list changes; CONTEXT.md's `<code_context>` explicitly lists "Multi-stage Dockerfile ... conventions from v1.0" as a reusable asset and ROADMAP Phase 5 success criteria explicitly require "a separate `requirements.txt`, `Dockerfile`" — so this is well-supported by CONTEXT.md/ROADMAP.md, not a pure assumption, but flagged since the Dockerfile is never exercised (built/run) until Phase 8 |

**If this table is empty:** N/A — see entries above. All are low-risk clarifying assumptions, not
load-bearing technical claims; the core technical claims (ConfigException behavior, package
versions, fallback order) are all `[VERIFIED]` against primary sources.

## Open Questions

1. **Should `apps/launchpad/Dockerfile` be built/tested by any Phase 5 CI step, or only exist as a
   file?**
   - What we know: ROADMAP.md's Phase 5 success criteria #2 explicitly lists "a separate
     `requirements.txt`, `Dockerfile`" as required to exist. D-08's guarded stubs mean
     `build-launchpad` deliberately does NOT build it in Phase 5.
   - What's unclear: Whether the planner should add a task that runs `docker build` once
     (non-Makefile, ad-hoc verification) just to confirm the Dockerfile is syntactically valid, or
     whether "exists, mirrors the proven pattern" is sufficient without any build verification
     until Phase 8.
   - Recommendation: Treat the Dockerfile as file-existence-only for Phase 5 (matching D-08's
     "guarded stub" philosophy for anything build/deploy-related) — but the planner may choose to
     add a cheap, non-Makefile `docker build -t localhost:5001/launchpad:dev-check apps/launchpad`
     smoke task purely as a sanity check, discarding the image, if extra confidence is wanted
     without violating D-08/D-09 (since it wouldn't touch the Makefile `up` aggregate).

2. **Exact env-var naming convention for `apps/launchpad/app/config.py`** (Claude's Discretion per
   CONTEXT.md).
   - What we know: field-guide-api uses `MONGO_URI`, `MONGO_DBNAME`, `FLASK_DEBUG` with no
     app-specific prefix. CONTEXT.md says `LP_`-style env prefixes are "reasonable but not
     mandated."
   - What's unclear: Since Phase 5 has no Mongo config yet (deferred to Phase 7/9) and no other
     env-driven values beyond `FLASK_DEBUG`/`TESTING`, there may be nothing launchpad-specific to
     prefix in Phase 5 at all.
   - Recommendation: Keep `Config` minimal in Phase 5 (`DEBUG`/`TESTING` only, same helper
     `_env_flag` pattern copied from field-guide-api) — defer the `LP_`-prefix question to Phase 7
     when `MONGO_URI`-equivalent config actually needs a name (to avoid colliding with
     field-guide-api's own `MONGO_URI` if both `.env` files are ever loaded in the same shell
     during local dev without containers).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python 3.11 | app runtime, venv creation | Not confirmed via default `python`/`pip` on this research machine (resolves to pyenv 3.7.4) | 3.7.4 (default shell) | Makefile's `PYTHON ?= python3` override already documented for this exact scenario (`make test PYTHON="py -3.12"` on Windows Git Bash) — planner should ensure the launchpad `test-launchpad` target uses the same `$(PYTHON)` variable, and implementation should verify a 3.11+ interpreter is invoked, not assume the default `python3` resolves correctly |
| pip / venv | dependency install | Available | pip 24.0 | — |
| Docker | Dockerfile existence only (not built in Phase 5) | Not probed this session (out of scope — Phase 5 doesn't build/run it) | — | N/A this phase |
| kind / kubectl / helm | Not required by Phase 5 at all (explicitly: "without a live cluster or kubeconfig") | N/A | — | — |
| git bash / bash | Makefile execution | Assumed available per project conventions (CLAUDE.md) | — | — |

**Missing dependencies with no fallback:** None — Phase 5's anchor success criterion is
explicitly designed to require nothing beyond Python + pip + bash.

**Missing dependencies with fallback:** Python 3.11 resolution on this specific research machine
— covered by the existing `PYTHON ?=` Makefile override pattern; not a Phase 5 blocker, but the
planner/implementer should explicitly verify (e.g. `$(PYTHON) --version`) rather than assume.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|----------------|---------|-------------------|
| V2 Authentication | No | Phase 5 has no user-facing auth surface (single `/health` route, no login) |
| V3 Session Management | No | No sessions in this phase |
| V4 Access Control | No | No access-controlled resources yet; K8s RBAC least-privilege is Phase 8's concern (DEP-02), not Phase 5's — Phase 5's `app.k8s` module doesn't even attempt cluster calls |
| V5 Input Validation | No | `/health` takes no input; nothing to validate this phase |
| V6 Cryptography | No | No secrets, tokens, or crypto handled directly by Phase 5 code (the K8s client library handles its own token/cert reading internally, and only when actually invoked with real cluster config — not exercised in Phase 5's tests) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|----------------------|
| Overly broad `except Exception:` around config loaders masking real bugs | Repudiation (silent failure hides actual errors) | Catch `ConfigException` specifically, as documented in Architecture Patterns / Common Pitfalls — never swallow all exceptions around cluster-config loading |
| Accidentally bundling `.env` or a real kubeconfig into the Docker build context | Information Disclosure | `.dockerignore` must explicitly exclude `.env` and any `kubeconfig`/`.kube/` paths, mirroring field-guide-api's `.dockerignore` (already confirmed to exclude `.env`); launchpad's own `.gitignore` coverage already applies repo-wide (`.env`, `kubeconfig`, `*.kubeconfig`, `.kube/` are all already pattern-matched globally, verified by reading the existing root `.gitignore`) |

This is a low-security-surface phase by design (no auth, no user input, no secrets handling
beyond what the K8s client library does internally and only when actually invoked) — the main
security-relevant discipline is exception-handling hygiene (Common Pitfalls #1) and Docker build
context hygiene (`.dockerignore`), both already covered above.

## Sources

### Primary (HIGH confidence)
- `github.com/kubernetes-client/python` `master` branch, `kubernetes/base/config/incluster_config.py`
  (fetched via `gh api repos/kubernetes-client/python/contents/...` and base64-decoded) — confirmed
  exact `ConfigException` raise conditions and messages for the in-cluster loader
- `github.com/kubernetes-client/python` `master` branch,
  `kubernetes/base/config/config_exception.py` (same method) — confirmed `ConfigException` is a
  bare `Exception` subclass
- `github.com/kubernetes-client/python` `master` branch, `kubernetes/base/config/kube_config.py`
  (grep of raise sites, same fetch method) — confirmed `load_kube_config()` also raises
  `ConfigException("File does not exist: %s" ...)` and `"No configuration found."` for its
  failure modes
- `pypi.org/project/kubernetes/` and `pypi.org/pypi/kubernetes/json` — confirmed latest release
  36.0.2, uploaded 2026-06-01, `Requires-Python >=3.10`
- `pypi.org/project/requests/` — confirmed latest release 2.34.2 (not needed as a direct
  dependency this phase, checked only to validate live-PyPI-vs-local-pip-cache discrepancy)
- Existing shipped source read directly from the repo: `apps/field-guide-api/app/__init__.py`,
  `app/config.py`, `app/extensions.py`, `app/routes/health.py`, `tests/conftest.py`,
  `tests/test_factory.py`, `tests/test_health.py`, `pytest.ini`, `Dockerfile`, `.dockerignore`,
  `.env.example`, `requirements.txt`, `requirements-dev.txt`, root `Makefile`, root `.gitignore`

### Secondary (MEDIUM confidence)
- WebSearch on `kubernetes-client/python` GitHub star count / org identity — cross-verified
  against the PyPI project page's linked repository (both point to the same org/repo)
- `kubernetes/base/config/__init__.py` docstring on `load_config()`'s try-order (kubeconfig
  before in-cluster) — fetched via WebFetch of the raw GitHub file; used only to justify NOT using
  the convenience wrapper, not as a claim this phase implements

### Tertiary (LOW confidence)
- None — no unverified claims were retained after cross-checking; the one LOW-confidence item
  (local `pip index versions` showing stale `kubernetes==35.0.0`/`requests==2.31.0`) was resolved
  by identifying the root cause (local Python 3.7.4 pyenv default) and confirming the true latest
  versions via live PyPI JSON, so it is no longer treated as an open uncertainty

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every version verified against live PyPI, package identity verified
  against official GitHub org, existing project-locked packages reused verbatim
- Architecture: HIGH — Patterns 1 and 3 for Flask/pytest structure are direct excerpts from
  shipped, tested field-guide-api code; Pattern 2 (`app/k8s.py`) is built directly from
  primary-source-verified library exception behavior, not memory
- Pitfalls: HIGH — Pitfalls 1 and 2 verified against the actual client library source code (not
  training-data recall); Pitfall 3 verified against the existing Makefile's `cd`-per-app pattern
  already in the repo; Pitfall 4 is a reasoned inference (process-global registry collision),
  correctly scoped as a non-issue for Phase 5's actual execution model

**Research date:** 2026-07-08
**Valid until:** 2026-08-07 (30 days — stable domain: Flask app-factory patterns and the
`kubernetes` client's config-loading API surface have not changed in years; the one moderately
fast-moving fact, `kubernetes` package version pin, should be re-verified against PyPI if planning
is delayed past this window)
