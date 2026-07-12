# Roadmap: k8s-launchpad

## Milestones

- ✅ **v1.0 Foundation** — Phases 1-4 (shipped 2026-07-07) — [archive](milestones/v1.0-ROADMAP.md)
- 🚧 **v1.1 Product Dashboard** — Phases 5-10 (active)

## Phases

<details>
<summary>✅ v1.0 Foundation (Phases 1-4) — SHIPPED 2026-07-07</summary>

- [x] Phase 1: Scaffold + App + Tests (3/3 plans) — completed 2026-07-04
- [x] Phase 2: Cluster Infrastructure (2/2 plans) — completed 2026-07-05
- [x] Phase 3: Containerization + Helm Deployment (4/4 plans) — completed 2026-07-06
- [x] Phase 4: Makefile + Documentation (3/3 plans) — completed 2026-07-07

Full phase details: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

### v1.1 Product Dashboard (Phases 5-10)

- [x] **Phase 5: Monorepo Scaffold + App Factory** — launchpad Flask app structure and test harness pass without a cluster (completed 2026-07-08)
- [x] **Phase 6: UI Layer — Templates + Static Assets** — browser dashboard shell renders with vendored assets and sidebar navigation
 (completed 2026-07-10)
- [x] **Phase 7: Status API + Field-Guide Integration** — platform status contract defined; /health safe for Kubernetes readinessProbe (completed 2026-07-10)
- [x] **Phase 8: Helm Chart + K8s Diagnostics** — launchpad deploys to kind via Helm with RBAC; diagnostics page shows live cluster state (completed 2026-07-11)
- [x] **Phase 9: Service Catalog + Events / MongoDB CRUD** — developers can register and deregister services; events feed is bounded by TTL
 (completed 2026-07-12)
- [ ] **Phase 10: Makefile Integration + Smoke + Docs** — make up-all delivers both apps; dashboard is demoable to a human reviewer

## Phase Details

### Phase 5: Monorepo Scaffold + App Factory
**Goal**: The launchpad app loads and its unit tests pass without a live cluster or kubeconfig
**Depends on**: Phase 4 (v1.0 monorepo foundation)
**Requirements**: APP-01, APP-02
**Success Criteria** (what must be TRUE):
  1. `make test-launchpad` runs and all tests pass in Git Bash with no kind cluster running
  2. `apps/launchpad/` exists with a `create_app` factory, separate `requirements.txt`, `Dockerfile`, and a `conftest.py` that mocks the K8s client and `requests`
  3. Importing `app.k8s` with no kubeconfig present returns `(None, None)` — no exception raised at import time or at `create_app()` time
  4. `LP_IMAGE`, `LP_RELEASE`, `LP_CHART` Makefile variables and target stubs exist and do not override or shadow field-guide-api variables (`make help` shows both apps' targets without collision)
**Plans**: 2 plans
  - [x] 05-01-PLAN.md — launchpad Flask app skeleton (factory, config, extensions, lazy app.k8s, /health stub, Dockerfile) + 100%-coverage test harness [APP-01, APP-02]
  - [x] 05-02-PLAN.md — Makefile LP_* vars + six namespaced launchpad targets (test-launchpad works; build/load/deploy/port-forward/smoke guarded stubs) [APP-01]

### Phase 6: UI Layer — Templates + Static Assets
**Goal**: The dashboard shell renders fully in a browser with sidebar navigation and vendored assets, with no internet access required
**Depends on**: Phase 5
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05
**Success Criteria** (what must be TRUE):
  1. A browser pointed at the running launchpad app shows the dashboard at `/` with a visible product landing page presenting k8s-launchpad as an IDP
  2. Every page route (`/`, `/catalog`, `/diagnostics`, `/feed`) renders inside the `base.html` shell — sidebar nav and topbar visible, correct active state per route
  3. `static/vendor/htmx.min.js` and `static/vendor/pico.min.css` are present; the page loads completely with no outbound CDN requests (network disconnected test passes)
  4. Status cards on the landing page show a degraded/unknown state (not a 500 error or empty page) when the backing status API returns no data
  5. An htmx polling attribute is present on the status cards section with an interval of 10 seconds or longer and a visibility guard that pauses polling when the browser tab is hidden
**Plans**: 2 plans
  - [x] 06-01-PLAN.md — vendor htmx 2.0.10 + Pico 2.1.1 offline assets, style.css overrides, asset-presence test (human-verify gate) [UI-05]
  - [x] 06-02-PLAN.md — pages + partials blueprints, base shell + 4 pages + status-cards fragment, htmx polling contract, route tests [UI-01, UI-02, UI-03, UI-04]
**UI hint**: yes

### Phase 7: Status API + Field-Guide Integration
**Goal**: The platform status contract is defined — /health is safe as a Kubernetes readinessProbe and /api/status surfaces real platform data including field-guide-api reachability
**Depends on**: Phase 6
**Requirements**: STAT-01, STAT-02, STAT-03, STAT-04
**Success Criteria** (what must be TRUE):
  1. `GET /health` returns 200 when launchpad's own MongoDB is reachable and 503 when it is not; it never calls field-guide-api regardless of downstream state
  2. `GET /api/status` returns JSON containing `api_health`, `mongo_status`, `app_version`, `service_count`, and `field_guide_reachable`; the `field_guide_reachable` field shows a degraded value (not a crash or 500) when field-guide-api is unreachable
  3. `GET /metrics` returns Prometheus-format text with HTTP request count and duration metrics (parity with field-guide-api `/metrics`)
  4. The status card htmx fragment route returns an HTML partial when the `HX-Request` header is present and a full page otherwise; unit tests confirm this behavior
  5. `make test-launchpad` continues to pass at 100% coverage with all new routes exercised by mocked-requests unit tests
**Plans**: 2 plans
  - [x] 07-01-PLAN.md — Flask-PyMongo wiring + config keys + /health own-Mongo readiness (200/503) + mongomock test harness [STAT-03]
  - [x] 07-02-PLAN.md — get_platform_status() helper + /api/status JSON + HX-Request status-cards fragment + /metrics parity test [STAT-01, STAT-02, STAT-04]

### Phase 8: Helm Chart + K8s Diagnostics
**Goal**: The launchpad deploys to the kind cluster via Helm with correct label namespacing and RBAC; the diagnostics page shows real Kubernetes state inside the cluster and degrades gracefully outside it
**Depends on**: Phase 7
**Requirements**: DEP-01, DEP-02, DIAG-01, DIAG-02
**Success Criteria** (what must be TRUE):
  1. `helm lint charts/launchpad/` passes with no warnings; `_helpers.tpl` uses the `launchpad.*` prefix so installing both charts into the same namespace produces no label selector collision
  2. The chart deploys clean via the manual loop — hand-run `docker build` + `kind load` (or registry push) + `helm install` — and the launchpad pod reaches Running state in the kind cluster (Phase 10 wraps this loop in `make build-launchpad load-launchpad deploy-launchpad` per DEP-04)
  3. The diagnostics page at `/diagnostics` lists pods and deployments from the Kubernetes API when accessed inside the cluster; it shows a static "outside cluster" indicator (not a 500) when run locally without a kubeconfig
  4. The Deployment spec includes `serviceAccountName: launchpad` and the namespace-scoped Role grants only `get`/`list`/`watch` on `pods` and `deployments` (not ClusterRole)
  5. All K8s API calls use `_request_timeout=5` to prevent the single gunicorn worker from stalling on a hung socket
**Plans**: TBD

### Phase 9: Service Catalog + Events / MongoDB CRUD
**Goal**: Developers can register, view, and deregister services through the dashboard; every platform action writes to a bounded events feed backed by its own in-cluster MongoDB
**Depends on**: Phase 8
**Requirements**: CAT-01, CAT-02, CAT-03, CAT-04, CAT-05, FEED-01, FEED-02, FEED-03, DEP-03
**Success Criteria** (what must be TRUE):
  1. `GET /catalog` lists services from MongoDB; `POST /catalog/new` with valid input persists the registration, fires a `service_registered` event, and redirects to the catalog with the new entry visible
  2. Submitting the onboard form with missing or invalid required fields re-renders the form with field-level validation errors and CSRF protection intact — no document is written to MongoDB
  3. `GET /catalog/<id>` shows the full service registration fields and that service's related events
  4. Deregistering a service (after confirmation) removes it from MongoDB and fires a `service_deregistered` event visible in the activity feed
  5. The `events` collection has a TTL index on `ts`; `make test-launchpad` passes (mongomock-backed); the test suite documents that TTL expiry timing is verified live via smoke, not unit tests
  6. The launchpad Helm chart embeds `mongo:7` manifests in `charts/launchpad/templates/mongodb/` using database name `launchpad`; the field-guide-api chart is left untouched
**Plans**: 4 plans (3 original + 1 gap-closure)
  - [x] 09-01-PLAN.md — Flask-WTF + CSRF wiring, catalog.py/events.py never-raise helpers, ServiceForm, config keys, unique+TTL indexes, platform_started guard [CAT-02, CAT-03, FEED-02, FEED-03]
  - [x] 09-02-PLAN.md — catalog CRUD routes + onboard form + detail + zero-JS deregister confirm + /partials/feed 15s polling + shared event-row partial [CAT-01, CAT-02, CAT-03, CAT-04, CAT-05, FEED-01, FEED-02]
  - [x] 09-03-PLAN.md — charts/launchpad mongo:7 manifests mirror + mongodb helpers + SECRET_KEY/EVENTS_TTL_SECONDS rewiring + in-cluster mongoUri (pod flips to Ready) [DEP-03]
  - [ ] 09-04-PLAN.md — gap closure CR-01: normalize naive datetime in _relative_time + tz_aware=True on mongo.init_app + naive-datetime regression test [FEED-01]
**UI hint**: yes

### Phase 10: Makefile Integration + Smoke + Docs
**Goal**: `make up-all` brings both apps up end-to-end in a single command and the dashboard is demoable to a human reviewer via the browser
**Depends on**: Phase 9
**Requirements**: DEP-04, DEP-05, DOCS-01
**Success Criteria** (what must be TRUE):
  1. `make up-all` in Git Bash completes without error, bringing up the kind cluster and deploying both field-guide-api and launchpad
  2. `make smoke-launchpad` returns HTTP 200 for `/`, `/health`, and `/api/status` from `localhost:8081` (field-guide-api remains on `localhost:8080` — no port collision)
  3. `make help` lists all six launchpad targets (`build-launchpad`, `load-launchpad`, `deploy-launchpad`, `port-forward-launchpad`, `smoke-launchpad`, `test-launchpad`) with one-line descriptions, without displacing existing field-guide-api targets
  4. The README headline demo shows `make up-all` then opening `http://localhost:8081` as the primary browser demo flow, with a screenshots plan; the existing Docker/Helm setup docs remain intact
**Plans**: TBD

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Scaffold + App + Tests | v1.0 | 3/3 | Complete | 2026-07-04 |
| 2. Cluster Infrastructure | v1.0 | 2/2 | Complete | 2026-07-05 |
| 3. Containerization + Helm Deployment | v1.0 | 4/4 | Complete | 2026-07-06 |
| 4. Makefile + Documentation | v1.0 | 3/3 | Complete | 2026-07-07 |
| 5. Monorepo Scaffold + App Factory | v1.1 | 2/2 | Complete   | 2026-07-08 |
| 6. UI Layer — Templates + Static Assets | v1.1 | 2/2 | Complete   | 2026-07-10 |
| 7. Status API + Field-Guide Integration | v1.1 | 2/2 | Complete   | 2026-07-10 |
| 8. Helm Chart + K8s Diagnostics | v1.1 | 2/2 | Complete   | 2026-07-11 |
| 9. Service Catalog + Events / MongoDB CRUD | v1.1 | 3/3 | Complete   | 2026-07-12 |
| 10. Makefile Integration + Smoke + Docs | v1.1 | 0/? | Not started | - |
