# Project Research Summary

**Project:** k8s-launchpad v1.1 — Product Dashboard
**Domain:** Local IDP Browser Dashboard (Flask + htmx + Kubernetes diagnostics)
**Researched:** 2026-07-08
**Confidence:** HIGH

## Executive Summary

k8s-launchpad v1.1 adds a Flask-served platform dashboard (`apps/launchpad/`) on top of the validated v1.0 foundation without touching any existing code. The approach is a second independent Flask app in the same kind cluster: its own Dockerfile, its own `charts/launchpad/` Helm chart, its own MongoDB instance, and a namespaced `LP_` Makefile variable block that coexists cleanly with the existing `field-guide-api` targets. The UI is Jinja2 + vendored htmx 2.0.10 + vendored Pico.css 2.1.1 — no CDN, no build step, offline-capable. The only new Python dependencies are `kubernetes==33.1.0` (aligned with kind v0.32.0's K8s 1.33.1 node image) and `Flask-WTF==1.3.0` for CSRF on the service registration form.

The recommended build sequence has six phases with strict ordering: scaffold the app structure and establish lazy K8s client initialization before writing any routes (prevents test suite breakage outside a cluster), then build UI layer, status API, Helm chart with RBAC, MongoDB CRUD, and finally Makefile integration. The K8s diagnostics section is the primary technical differentiator — it uses the official `kubernetes` Python client with in-cluster ServiceAccount config, falls back to kubeconfig for local dev, and degrades gracefully when neither is available. The `Role`+`RoleBinding` RBAC scope is deliberately namespace-scoped (not ClusterRole) to follow least-privilege.

The top risks are operational, not architectural. The single gunicorn worker is vulnerable to K8s API calls without explicit `_request_timeout=5` — a hung urllib3 socket blocks all incoming requests including htmx polls. The Makefile must namespace both apps' variables from the first commit or `make deploy` silently targets the wrong Helm release. The `/health` readinessProbe must check only MongoDB; `/api/status` handles downstream checks. Apply these three patterns before writing any routes and the implementation is low-risk.

---

## Key Findings

### Recommended Stack

The v1.0 stack (Flask 3.1.3, Flask-PyMongo 3.0.1, PyMongo 4.13.2, gunicorn 26.0.0, pytest 9.1.1 + pytest-flask 1.3.0, python:3.11-slim multi-stage Dockerfile) carries over **unchanged** into `apps/launchpad/`.

**New additions for v1.1:**

- `kubernetes==33.1.0` — official K8s SIG client; version-aligned with kind v0.32.0 (K8s 1.33.1); sync-only deps (no aiohttp), safe for Flask+gunicorn; graceful two-step fallback: `load_incluster_config()` → `load_kube_config()` → `(None, None)`
- `Flask-WTF==1.3.0` — CSRF on the service registration form; uses existing `SECRET_KEY`; enables `{{ form.hidden_tag() }}` in Jinja2; `CSRFProtect(app)` in factory
- `htmx 2.0.10` — vendored to `static/vendor/htmx.min.js`; 14KB; no npm; covers all v1.1 patterns (polling, POST fragment, OOB swap); do NOT use v4 beta
- `Pico.css 2.1.1` — vendored to `static/vendor/pico.min.css`; 30KB; zero JS; semantic HTML styling; auto dark/light mode; ~80–120 lines custom CSS needed only for sidebar layout shell
- `charts/launchpad/templates/rbac/` — three new Helm templates: ServiceAccount, Role (namespace-scoped), RoleBinding; no equivalent exists in field-guide-api chart

**`apps/launchpad/requirements.txt`:**
```
Flask==3.1.3
Flask-PyMongo==3.0.1
pymongo==4.13.2
gunicorn==26.0.0
prometheus-flask-exporter==0.23.2
python-dotenv==1.2.2
kubernetes==33.1.0
Flask-WTF==1.3.0
WTForms==3.2.2
```

### Expected Features

**Must have (P1 — launch blockers):**
- UI shell with sidebar nav (`base.html` + `{% block content %}`)
- Landing `/` with real status cards backed by `/api/status` (not hardcoded)
- `/api/status` aggregating: MongoDB ping latency, `APP_VERSION`, service count, field-guide-api `/health` reachability
- Service catalog `/catalog` listing MongoDB `services` collection
- Onboard form `/catalog/new` → POST saves to MongoDB + fires `service_registered` event
- Server-side form validation with error re-render
- Diagnostics page: MongoDB ping + self-health + version
- Activity feed: last 20 events from `events` collection, newest-first
- htmx polling on status cards at 30s (`hx-trigger="every 30s"`)
- Graceful K8s degradation: `ConfigException` → "outside cluster" section, not 500
- `apps/launchpad/` with separate Dockerfile + `charts/launchpad/`

**Should have (P2 — within v1.1):**
- K8s pod/deployment status in diagnostics via in-cluster ServiceAccount + RBAC
- Status badge color system applied server-side from health state
- `make port-forward-launchpad`, `make smoke-launchpad`, `make up-all` targets

**Confirmed anti-features (do not build):**
- WebSocket/SSE — htmx 30s polling is sufficient for a status dashboard
- Service dependency graph — requires D3/Cytoscape, out of scope
- npm/Tailwind/Vite build step — violates locked stack
- Authentication — local-only platform, not warranted in v1.1

**MongoDB schemas finalized:**
- `services`: `{name, description, owner, git_repo_url, language, status="registered", registered_at, updated_at}`
- `events`: `{event_type, target, message, ts, severity}`; TTL index on `ts`; always `.sort("ts", -1).limit(20)`

### Architecture Approach

Two isolated Flask apps in a single kind `default` namespace. Each has its own MongoDB pod and PVC — no cross-chart MongoDB sharing — keeping each Helm chart independently installable and uninstallable. Inter-service communication is ClusterIP DNS (`http://field-guide-api` resolves within the same namespace without namespace qualification). The K8s Python client uses a lazy-init factory in `k8s.py` that returns `(None, None)` when no cluster config is available. The Makefile uses `LP_*` variable block and named targets (`build-launchpad`, etc.) without disturbing existing targets.

**Major components:**
1. `apps/launchpad/` — Flask app with `create_app` factory; blueprints: `ui`, `status`, `services`, `events`; mirrors field-guide-api structure exactly
2. `charts/launchpad/` — Helm chart with Deployment, Service, ConfigMap, Secret, MongoDB manifests (`templates/mongodb/`), and `rbac/` subdirectory
3. `apps/launchpad/app/k8s.py` — standalone K8s client module; lazy-init; stores `(CoreV1Api, AppsV1Api)` or `(None, None)`
4. Templates + `static/vendor/` — `base.html` shell with sidebar; htmx.min.js and pico.min.css vendored; `_` prefix convention for fragment-only templates
5. `Makefile` — `LP_IMAGE`, `LP_RELEASE`, `LP_CHART` block + 7 new named targets + `up-all` composite

**Internal module boundary rule:** all routes import `mongo` from `app.extensions`, never from `app.__init__`. Blueprints imported inside `create_app()` after extensions initialize. `k8s.py` is imported by routes only, initialized once in `create_app()`.

### Critical Pitfalls

1. **Makefile variable collision** — adding launchpad targets without namespacing overwrites `$(IMAGE)`, `$(RELEASE)`, `$(CHART)`; `make deploy` silently targets the wrong release. Prevention: `LP_IMAGE`, `LP_RELEASE`, `LP_CHART` from the first commit; only named targets (`build-launchpad`, not a second `build`). Address in Phase 1.

2. **K8s client blocks the single gunicorn worker** — no default timeout in `kubernetes` client; hung urllib3 socket is invisible to gunicorn until 30s worker timeout; crashes every active request including htmx polls. Prevention: always `_request_timeout=5` on every client method; in-process result cache with 10s TTL. Address in Phase 4.

3. **`load_incluster_config()` at import time kills the test suite** — `ConfigException` at import prevents `create_app()` from loading outside a cluster. Prevention: lazy-init inside `get_k8s_client()` factory; routes handle `None` return. Address in Phase 1.

4. **Dashboard `/health` calling downstream services causes readinessProbe cascades** — field-guide-api restart marks launchpad NotReady; recursive if both `/health` endpoints check each other. Prevention: `/health` checks only this pod's MongoDB; `/api/status` handles all downstream checks and is never the readinessProbe target. Address in Phase 3.

5. **Unbounded MongoDB events collection** — no TTL index means progressive slowdown after extended demo use. Prevention: `create_index("ts", expireAfterSeconds=604800)` at startup; all queries `.sort("ts", -1).limit(20)`. Address in Phase 5.

6. **htmx polling + synchronous K8s I/O = worker starvation** — 30s poll on an endpoint that calls the K8s API without timeout; two open browser tabs double the rate. Prevention: poll interval ≥ 10s; visibility guard; K8s result cached in-process. Closely related to Pitfall 2. Address in Phase 3.

---

## Implications for Roadmap

### Phase 1: Monorepo Scaffold + App Factory
**Rationale:** Makefile variable namespace and K8s lazy-init pattern must be established before any code is written. These are the two pitfalls with the highest recovery cost — they corrupt every subsequent artifact if introduced late. Establishing them first also means `make test-launchpad` passes from day one without a live cluster.
**Delivers:** `apps/launchpad/` directory tree, `create_app()` factory, `k8s.py` lazy-init module, `conftest.py` with mocked K8s client and mocked `requests`, `requirements.txt` and `requirements-dev.txt`, `pytest.ini`, `make test-launchpad` passing. Makefile `LP_` variable block and all named target stubs.
**Avoids:** Pitfall 1 (Makefile collision), Pitfall 3 (import-time K8s init)

### Phase 2: UI Layer (Templates + Static Assets)
**Rationale:** UI shell must exist before data-backed routes are built. Template inheritance and htmx wiring established here unblocks all subsequent page routes. Vendoring static assets is a one-time `curl`.
**Delivers:** `base.html` with sidebar/nav, stub page templates, vendored htmx.min.js and pico.min.css, ~100 lines custom CSS for sidebar layout, `flask run` locally renders a degraded-state dashboard.
**Uses:** htmx 2.0.10, Pico.css 2.1.1; `make vendor` Makefile target
**Avoids:** Pitfall 9 (fragment vs full-page confusion) — `HX-Request` detection established in all routes

### Phase 3: Status API + Field-Guide Integration
**Rationale:** `/api/status` and `/health` define the platform contract. The strict `/health` = pod-only scope must be established before the Helm readinessProbe is written in Phase 4. The htmx polling pattern (interval, visibility guard, request timeout) must be correct before any K8s I/O is added.
**Delivers:** `GET /health` (MongoDB ping only), `GET /api/status` (field-guide-api reachability + MongoDB latency + version + service count), `/api/status/fragment` partial for htmx polling at 30s with visibility guard.
**Avoids:** Pitfall 4 (readinessProbe cascade), Pitfall 6 (htmx polling starvation)

### Phase 4: Helm Chart + K8s Diagnostics
**Rationale:** The Helm chart with correct `_helpers.tpl` naming must exist before in-cluster testing. RBAC manifests live in the chart. The `serviceAccountName` must be wired in the Deployment spec — omitting it causes 403 errors that look identical to auth failures.
**Delivers:** `charts/launchpad/` complete (Deployment + Service + ConfigMap + Secret + NOTES.txt + `_helpers.tpl` with `launchpad.*` prefix + `rbac/` with ServiceAccount + Role + RoleBinding). `make build-launchpad load-launchpad deploy-launchpad` produces a Running pod. K8s diagnostics section showing pod list in `/diagnostics`.
**Uses:** `kubernetes==33.1.0`; namespace-scoped Role (not ClusterRole)
**Avoids:** Pitfall 2 (Helm selector collision), Pitfall 2-adjacent (missing `serviceAccountName` in Deployment spec)

### Phase 5: Service Catalog + Events (MongoDB CRUD)
**Rationale:** MongoDB CRUD is the highest-value user-facing feature. With the Helm chart validated and the app factory established, this phase has no blocking dependencies. The TTL index must be created before the first event document is inserted.
**Delivers:** `charts/launchpad/templates/mongodb/` (deployment/service/pvc/secret with `mongoDbName: launchpad`), `GET /catalog`, `POST /catalog/new` with Flask-WTF CSRF + server-side validation + `service_registered` event, `events` collection with TTL index, activity feed showing last 20 events. Data persists across `helm upgrade`.
**Uses:** Flask-WTF 1.3.0, htmx OOB swap for activity feed update on form success
**Avoids:** Pitfall 5 (unbounded events), Pitfall 8 (MongoDB DB name collision — `launchpad` not `fieldguide`), Pitfall 12 (cross-chart MongoDB hostname wiring)

### Phase 6: Makefile Integration + Smoke Test
**Rationale:** `make up-all` is the user-facing proof that the v1.0 build loop pattern generalizes to a second app. Smoke test validates the full round-trip before milestone close.
**Delivers:** `up-all` composite target, `smoke-launchpad` testing `/`, `/health`, `/api/status`, `port-forward-launchpad` on localhost:8081 (distinct from localhost:8080 for field-guide-api), `make help` showing all targets with descriptions.
**Avoids:** Pitfall 10 (port-forward collision)

### Phase Ordering Rationale

- Phase 1 before everything: Makefile variable collisions and K8s import-time failures have the highest recovery cost — establishing them last means reworking every subsequent artifact.
- Phase 2 before Phase 3: Routes built without a base template can't be visually verified. The `HX-Request` fragment detection pattern must exist before status polling is added.
- Phase 3 before Phase 4: The `/health` vs `/api/status` separation must be in code before the Helm `readinessProbe` is written. Reversing this order bakes the wrong probe behavior into the chart.
- Phase 4 before Phase 5: `_helpers.tpl` naming must be finalized before MongoDB manifests are written into the chart. Writing MongoDB CRUD with uncorrected helper names risks the DB name collision pitfall.
- Phase 6 last: Smoke test can only validate the whole stack once everything is in place.

### Research Flags

**Well-documented patterns — skip research-phase during planning:**
- Phase 1: App factory is an exact mirror of `apps/field-guide-api/app/__init__.py` (live codebase); LP_ Makefile pattern fully specified in ARCHITECTURE.md
- Phase 2: Jinja2 template inheritance and htmx vendoring are standard; no unknowns
- Phase 5: Flask-PyMongo CRUD is identical to field-guide-api patterns; schema fully defined in FEATURES.md
- Phase 6: Makefile targets fully specified in ARCHITECTURE.md

**Worth a targeted validation pass during phase planning:**
- Phase 4: The `serviceAccountName` + `load_incluster_config()` interaction has two distinct failure modes (no token = clean `ConfigException` vs wrong ServiceAccount = silent 403 from K8s API). Confirm in-cluster behavior during phase planning.
- Phase 3: The htmx visibility guard conditional syntax (`hx-trigger="every 30s [document.visibilityState !== 'hidden']"`) — verify against htmx 2.0.x docs; fallback is `hx-trigger="load delay:30s"` chained polling.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified against PyPI and official GitHub releases. kubernetes==33.1.0 alignment with K8s 1.33.1 confirmed via client compatibility matrix. |
| Features | HIGH | Feature scope derived from IDP competitor analysis (Backstage, Port, Heroku) + PRD. MongoDB schemas fully specified. MVP clearly bounded. |
| Architecture | HIGH | Derived from live codebase inspection of v1.0 Makefile, `_helpers.tpl`, `conftest.py`, `app/__init__.py`. All integration points documented with failure modes. |
| Pitfalls | HIGH | Derived from v1.0 codebase patterns + verified library docs (kubernetes `_request_timeout`, gunicorn worker timeout, mongomock limitations, htmx polling semantics). |

**Overall confidence:** HIGH

### Gaps to Address

- **mongomock TTL/capped limitation:** Unit tests cannot verify TTL expiry timing. Integration test target (`make test-integration`) against real `mongo:7` recommended for Phase 5. Document gap in `conftest.py`.
- **htmx 2.0.x visibility guard syntax:** Confirm `hx-trigger="every 30s [document.visibilityState !== 'hidden']"` conditional is supported in 2.0.x before Phase 3 planning.
- **`make up-all` idempotency on re-run:** Verify v1.0 `cluster-setup.sh` handles re-runs with two deployed Helm releases gracefully. No code change expected, just verification.

---

## Sources

**Primary (HIGH confidence):**
- `charts/field-guide-api/` (live codebase) — Helm helper patterns, MongoDB manifests, selectorLabels baseline
- `Makefile` (live codebase) — existing variable naming, `MSYS_NO_PATHCONV=1`, `SHELL := /bin/bash`
- `apps/field-guide-api/app/__init__.py` (live codebase) — app factory pattern to replicate
- kubernetes PyPI 33.1.0 — no aiohttp dep, Python ≥3.10, sync deps confirmed
- kubernetes-client/python README — compatibility matrix; client 33.x = K8s 1.33
- Flask-WTF PyPI — version 1.3.0, Flask 3.x compatible, April 2026
- htmx GitHub releases — 2.0.10 current stable; v4 in beta
- Pico.css GitHub releases — v2.1.1, March 2025
- Kubernetes RBAC docs — Role vs ClusterRole, ServiceAccount mounting
- MongoDB TTL Indexes v7.0 — TTL behavior, 60s background cleanup cadence

**Secondary (MEDIUM confidence):**
- htmx hx-trigger docs — polling syntax; HTTP 286 stop-polling; visibility guard
- htmx template fragments essay — fragment vs full-page route design
- kubernetes-client/python timeout-settings.md — `_request_timeout` parameter; no default
- Backstage Descriptor Format — service catalog entry fields
- Heroku Dashboard — activity/events table pattern
- gunicorn worker timeout issue tracker — blocking IO not detected until `--timeout` fires

**Tertiary (LOW confidence):**
- kind v0.32.0 Kubernetes 1.33.1 default node image — inferred from release notes; verify with `kind version` + `kubectl version` after `make cluster-up`
