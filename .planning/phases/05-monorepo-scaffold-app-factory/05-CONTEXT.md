# Phase 5: Monorepo Scaffold + App Factory - Context

**Gathered:** 2026-07-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Stand up the `apps/launchpad/` Flask application skeleton so it loads and its unit
tests pass **without a live cluster or kubeconfig**. This phase delivers structure
and a test harness only — not UI (Phase 6), not the real status API (Phase 7), not
MongoDB CRUD (Phase 9), not the Helm chart or cluster deploy (Phase 8/10).

Concretely in scope (APP-01, APP-02):
- `apps/launchpad/` as a **separate** Flask workload — own `create_app` factory,
  own `requirements.txt` / `requirements-dev.txt`, own `Dockerfile`, own `.venv`,
  structured independently from `apps/field-guide-api/`.
- A lazy `app.k8s` module: initializing the Kubernetes client **never** happens at
  import time or at `create_app()` time; with no cluster config it returns
  `(None, None)` and raises nothing.
- An isolated `conftest.py` that mocks the K8s client and `requests`.
- Namespaced `LP_*` Makefile variables and launchpad target stubs that do not
  collide with or shadow the field-guide-api targets.

Anchor success criterion: `make test-launchpad` runs green in Git Bash with no kind
cluster running.
</domain>

<decisions>
## Implementation Decisions

### Skeleton scope — how much app to stand up now
- **D-01:** Ship a **factory + a real route stub** (not a bare factory). `create_app`
  registers a minimal health blueprint so the test harness exercises a real route
  end-to-end, plus `test_factory`, `test_health`, and `test_k8s`.
- **D-02:** Wire the **k8s module + prometheus `metrics`** extension now. **Do NOT**
  wire Flask-PyMongo / mongomock in Phase 5 — MongoDB plumbing is deferred to
  Phase 7/9 where it's actually used. The conftest mocks the K8s client and
  `requests`; no Mongo mocking yet.
- **D-03:** Target directory layout mirrors field-guide-api:
  `app/__init__.py` (`create_app`), `app/config.py`, `app/extensions.py`,
  `app/k8s.py`, `app/routes/health.py`, `wsgi.py`, plus `tests/`.

### Skeleton route
- **D-04:** The Phase 5 route is **`GET /health` returning a plain `200`** (e.g.
  `{"status": "ok"}`) with **no** Mongo check. Route name stays stable: Phase 7
  (STAT-03) evolves this same `/health` in place into the real readiness probe
  (pings launchpad's own MongoDB, returns 503 when down). Do not invent a separate
  `/healthz` — one route name, evolved across phases.

### app.k8s lazy-init contract
- **D-05:** Expose a **single `get_k8s_clients()` function** returning a tuple.
  Fallback order: (1) try in-cluster config, (2) fall back to local kubeconfig,
  (3) return `(None, None)` if neither is available. When a cluster is reachable it
  returns `(CoreV1Api, AppsV1Api)`. Callers check for `None` to detect the disabled
  state. Import of `app.k8s` and `create_app()` must both succeed with no kubeconfig.
- **D-06:** **No caching** of the client in Phase 5 — the plain function is enough
  for the skeleton. (A cached accessor + `k8s_enabled()` helper was considered and
  is a fine later optimization if per-request re-probing becomes a concern; not
  needed now.)
- **D-07:** This `(None, None)` contract is a **downstream dependency for Phase 8**
  diagnostics — keep the shape stable.

### Makefile launchpad targets
- **D-08:** Add all launchpad targets as **guarded stubs now**, visible in
  `make help`, using `LP_*` variables (`LP_IMAGE`, `LP_RELEASE`, `LP_CHART`, etc.)
  that do not collide with or shadow field-guide-api's `IMAGE`/`RELEASE`/`CHART`.
  - `test-launchpad` — **fully works** in Phase 5 (creates `.venv`, installs
    `requirements-dev.txt`, runs pytest — mirrors the existing `test` target).
  - `build-launchpad` / `load-launchpad` / `deploy-launchpad` /
    `port-forward-launchpad` / `smoke-launchpad` — present but **guarded**: they
    echo a clear "available in Phase 8/10" notice and exit cleanly (exit 0, no
    error), so `make help` lists both apps' targets with no collision and nothing
    breaks.
- **D-09:** Guarded stubs must not be pulled into the existing `up` aggregate target
  or otherwise change v1.0 field-guide-api behavior. `make up-all` is a Phase 10
  deliverable.

### Test / coverage gate
- **D-10:** launchpad adopts **100% coverage from day one** — `pytest.ini` (or
  equivalent) sets `--cov=app --cov-fail-under=100 --cov-report=term-missing`,
  matching field-guide-api. Every skeleton line is tested from the start; this keeps
  Phase 7's "continues to pass at 100% coverage" criterion true by construction.

### Claude's Discretion
- Exact config keys / env-var names in `config.py` (follow field-guide-api's
  `Config` pattern; `LP_`-style env prefixes are reasonable but not mandated).
- Whether the health blueprint lives in `app/routes/health.py` vs a single
  `app/routes/__init__.py` — mirror field-guide-api's blueprint structure.
- Precise Dockerfile contents (reuse the proven multi-stage `python:3.11-slim`,
  non-root, gunicorn-PID-1 pattern from field-guide-api's Dockerfile).
- How `requests` is mocked in conftest (fixture shape) — planner/researcher choice.
- Handling the two-apps-share-the-`app`-package-name concern: each app has its own
  `.venv` and tests `cd` into the app dir, so no import collision — this is a
  technical detail for research/planning, not a user decision.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & roadmap (this phase)
- `.planning/REQUIREMENTS.md` — APP-01 (separate launchpad Flask app, own
  Dockerfile/requirements, `create_app` + env-driven config) and APP-02 (lazy K8s
  client returning a disabled signal without kubeconfig).
- `.planning/ROADMAP.md` §"Phase 5: Monorepo Scaffold + App Factory" — goal and the
  4 success criteria that define DONE.

### Patterns to mirror (v1.0 field-guide-api — proven, shipped)
- `apps/field-guide-api/app/__init__.py` — app-factory with deferred blueprint
  imports and bounded extension init; the launchpad factory mirrors this shape.
- `apps/field-guide-api/app/config.py` — env-driven `Config` class pattern.
- `apps/field-guide-api/app/extensions.py` — extension singletons (`metrics`; mongo
  NOT needed yet in launchpad).
- `apps/field-guide-api/tests/conftest.py` — monkeypatch-based isolation pattern
  (adapt for K8s client + `requests` instead of mongomock).
- `apps/field-guide-api/pytest.ini` — 100% coverage gate to replicate.
- `apps/field-guide-api/Dockerfile` — multi-stage `python:3.11-slim`, non-root,
  gunicorn PID 1 pattern to reuse.
- `Makefile` — existing `test`/`build`/`load`/`deploy`/`up`/`help` targets and
  `IMAGE`/`RELEASE`/`CHART` variables; the `LP_*` targets must sit alongside these
  without collision, and the `help` awk pattern must render both apps' targets.

### Downstream contracts this phase must not break
- `.planning/ROADMAP.md` §"Phase 7" (STAT-03) — `/health` becomes readiness + 503;
  Phase 5's `/health` stub must be evolvable in place (D-04).
- `.planning/ROADMAP.md` §"Phase 8" — diagnostics depends on the `app.k8s`
  `(None, None)` / `(CoreV1Api, AppsV1Api)` contract (D-05, D-07).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `create_app` factory (`apps/field-guide-api/app/__init__.py`): deferred blueprint
  imports mean the module is importable before route files exist — reuse verbatim
  for launchpad.
- Per-app `.venv` + `test` Makefile target (creates venv, installs
  `requirements-dev.txt`, runs pytest): `test-launchpad` is a near-copy pointed at
  `apps/launchpad`.
- conftest monkeypatch isolation: same technique, retargeted to patch the K8s
  client accessor and `requests` rather than the mongo singleton.
- Multi-stage Dockerfile and `helm upgrade --install` deploy conventions from v1.0.

### Established Patterns
- Extensions initialized against the app instance inside `create_app`, with bounded
  timeouts so a single gunicorn worker never blocks (v1.0 used a 2s Mongo
  server-selection timeout; carry the same "fail fast, never hang the worker"
  discipline into K8s calls — Phase 8 formalizes `_request_timeout=5`).
- Makefile: `SHELL := /bin/bash`, `export MSYS_NO_PATHCONV=1`, `##`-comment help
  convention — launchpad targets must follow the same style.
- Git Bash / WSL2 compatibility, LF endings (`.gitattributes`).

### Integration Points
- `Makefile` at repo root — `LP_*` vars + launchpad targets added alongside
  field-guide-api's, no shadowing; `make help` must show both sets.
- `apps/` monorepo dir — new sibling `apps/launchpad/` next to `apps/field-guide-api/`.
- `.gitignore` — must already cover the new app's `.venv`, `__pycache__`, `.env`
  (verify before committing new app files).
</code_context>

<specifics>
## Specific Ideas

- launchpad mirrors field-guide-api's structure deliberately — the platform
  "dogfoods" its own conventions. Prefer copy-and-adapt of the proven v1.0 files
  over inventing new structure.
- `app.k8s` disabled state (`(None, None)`) is a first-class, tested code path — it
  is the normal case when running locally/in tests, not an error.
</specifics>

<deferred>
## Deferred Ideas

- **Cached K8s client accessor + `k8s_enabled()` helper** — considered for D-05/D-06;
  deferred. Add only if per-request config re-probing becomes a measured concern
  (candidate for Phase 8 when diagnostics actually calls the API).
- **Flask-PyMongo / mongomock wiring** — belongs to Phase 7 (`/health` readiness,
  `/api/status`) and Phase 9 (catalog/events CRUD). Not in Phase 5.
- **Real `/health` readiness (Mongo ping + 503)** — Phase 7 (STAT-03).
- **Working `build/load/deploy/port-forward/smoke-launchpad` targets** — Phase 8
  (chart + cluster) and Phase 10 (`up-all`, `smoke`). Phase 5 ships guarded stubs.
- **`_request_timeout=5` on K8s API calls** — Phase 8 (DIAG-02 / success criterion 5).

None of the above are scope creep out of this discussion — they are explicit
later-phase requirements, listed here to keep Phase 5 tight.

</deferred>

---

*Phase: 5-Monorepo Scaffold + App Factory*
*Context gathered: 2026-07-08*
