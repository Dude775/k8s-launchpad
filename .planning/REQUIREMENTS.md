# Requirements: k8s-launchpad (v1.1 — Product Dashboard / PRD-3)

**Defined:** 2026-07-08
**Core Value:** Make k8s-launchpad visible as a product — a Flask-served browser dashboard that presents the platform as a local Internal Developer Platform, demoable to a human reviewer.

## v1 Requirements

Requirements for milestone v1.1 (PRD-3 Product Dashboard). Each maps to a roadmap phase. The dashboard is a new platform app (`apps/launchpad/`) deployed alongside — never replacing — the v1.0 field-guide-api workload.

### Platform App Scaffold

- [x] **APP-01**: New `apps/launchpad/` Flask app exists with a `create_app` app-factory and env-driven config, structured separately from the field-guide-api workload (own Dockerfile, own requirements)
- [x] **APP-02**: The Kubernetes client initializes lazily (never at import time) and returns a disabled signal when no cluster config is available, so the app and its tests load without a kubeconfig

### Dashboard UI

- [ ] **UI-01**: Developer sees a product landing/dashboard page at `/` that presents k8s-launchpad as an Internal Developer Platform
- [ ] **UI-02**: Every page renders inside a consistent UI shell with sidebar navigation and a topbar
- [ ] **UI-03**: The landing page shows platform status cards backed by live data from the status API (not hardcoded values)
- [ ] **UI-04**: Status cards refresh in the browser without a full page reload (htmx polling, ≥10s interval, paused when the tab is hidden)
- [x] **UI-05**: All front-end assets (htmx, CSS) are vendored locally — the dashboard renders fully with no internet/CDN access

### Platform Status

- [ ] **STAT-01**: `GET /api/status` returns real platform status — API health, MongoDB status, app/version info, registered-service count, and a metrics preview
- [ ] **STAT-02**: Platform status reflects field-guide-api reachability over the cluster network and degrades gracefully (no crash, shown as a degraded card) when it is unreachable
- [ ] **STAT-03**: `GET /health` readiness checks only the launchpad pod's own MongoDB — never downstream services — returning 503 when its own DB is unreachable
- [ ] **STAT-04**: `/metrics` exposes Prometheus-format metrics for the dashboard app (PRD-4 scrape seam, parity with field-guide-api)

### Service Catalog

- [ ] **CAT-01**: Developer can view a service catalog listing services registered in MongoDB
- [ ] **CAT-02**: Developer can onboard a new service through a form; the registration persists in MongoDB
- [ ] **CAT-03**: The onboard form validates input server-side (CSRF-protected) and re-renders with field-level errors on invalid input
- [ ] **CAT-04**: Developer can open a service detail page showing the full registration and that service's related events
- [ ] **CAT-05**: Developer can deregister (delete) a service from the catalog after a confirmation step

### Diagnostics

- [ ] **DIAG-01**: Developer sees a diagnostics page with in-app platform checks — MongoDB ping, self-health, and config/version — that runs without a cluster
- [ ] **DIAG-02**: Diagnostics shows read-only Kubernetes state (pods/deployments in the namespace) via an in-cluster ServiceAccount with least-privilege RBAC, degrading gracefully to an "outside cluster" state when no cluster is reachable

### Activity Feed

- [ ] **FEED-01**: Developer sees an activity/events feed of recent platform events (newest first), backed by a persisted MongoDB collection
- [ ] **FEED-02**: Platform actions — platform started, service registered, service deregistered — write events into the feed
- [ ] **FEED-03**: The events collection is bounded by a TTL index so it cannot grow unbounded during extended demo use

### Deployment

- [ ] **DEP-01**: `charts/launchpad/` Helm chart deploys the dashboard (Deployment, Service, ConfigMap, Secret, values.yaml); `helm lint` passes and its `_helpers.tpl` naming does not collide with field-guide-api selectors
- [ ] **DEP-02**: The chart provisions a ServiceAccount + namespace-scoped Role + RoleBinding granting read-only access to pods/deployments, with `serviceAccountName` wired into the Deployment spec
- [ ] **DEP-03**: Launchpad runs its own in-cluster MongoDB (own database) via `mongo:7` manifests embedded in its chart; the field-guide-api chart is left untouched
- [ ] **DEP-04**: The Makefile has namespaced launchpad targets (`build-launchpad`, `load-launchpad`, `deploy-launchpad`, `port-forward-launchpad`, `smoke-launchpad`, `test-launchpad`) using `LP_` variables that do not collide with the field-guide-api targets, and launchpad port-forwards on a distinct local port
- [ ] **DEP-05**: `make up-all` brings up the cluster and both apps end-to-end, and `make smoke-launchpad` verifies the dashboard reachable (200 on `/`, `/health`, `/api/status`)

### Documentation

- [ ] **DOCS-01**: README documents the browser demo flow (`make up-all` → open the dashboard) as the headline demo, with a screenshots plan, while preserving the existing Docker/Helm setup docs

## v2 Requirements

Deferred to later PRDs. Tracked but not in this milestone's roadmap.

### GitOps (PRD-2)

- **GITOPS-01**: ArgoCD syncs deployments from Git

### Platform Layer (PRD-3, later tranche)

- **PLAT-01**: Onboard form triggers a real build/deploy pipeline (registrations currently persist only)

### Observability & Security (PRD-4)

- **OBS-01**: Prometheus/Grafana/Loki deployed and scraping `/metrics`
- **OBS-02**: Trivy vulnerability scanning

### Cloud (final PRD)

- **CLOUD-01**: AWS/EKS/Terraform deployment

## Out of Scope

Explicitly excluded from v1.1. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Real deployment pipeline behind the onboard form | v1.1 stores registrations only; wiring to actual builds/deploys is a later PRD (PLAT-01) |
| ArgoCD / GitOps | PRD-2; only the `infra/argocd/` directory seam exists |
| Prometheus/Grafana/Loki/Trivy deployment | PRD-4; dashboard exposes `/metrics` now as a seam |
| AWS / EKS / Terraform / any cloud | Final PRD; everything stays local and free |
| React / Vue / Vite / npm build step | Locked: Flask-first, server-rendered Jinja2 + vendored htmx only |
| WebSocket / SSE live updates | htmx polling is sufficient for a local status dashboard |
| Service dependency graph / topology viz | Requires D3/Cytoscape; over-engineering at this scale |
| Authentication / multi-user | Local single-user platform; not warranted in v1.1 |
| Edit an existing service registration | Deferred; v1.1 supports register, view, and deregister only |
| Sharing one MongoDB instance across both apps | Separate per-chart Mongo keeps each chart independently installable/uninstallable |

## Traceability

Which phases cover which requirements. Phase assignments populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| APP-01 | Phase 5 | Complete |
| APP-02 | Phase 5 | Complete |
| UI-01 | Phase 6 | Pending |
| UI-02 | Phase 6 | Pending |
| UI-03 | Phase 6 | Pending |
| UI-04 | Phase 6 | Pending |
| UI-05 | Phase 6 | Complete |
| STAT-01 | Phase 7 | Pending |
| STAT-02 | Phase 7 | Pending |
| STAT-03 | Phase 7 | Pending |
| STAT-04 | Phase 7 | Pending |
| CAT-01 | Phase 9 | Pending |
| CAT-02 | Phase 9 | Pending |
| CAT-03 | Phase 9 | Pending |
| CAT-04 | Phase 9 | Pending |
| CAT-05 | Phase 9 | Pending |
| DIAG-01 | Phase 8 | Pending |
| DIAG-02 | Phase 8 | Pending |
| FEED-01 | Phase 9 | Pending |
| FEED-02 | Phase 9 | Pending |
| FEED-03 | Phase 9 | Pending |
| DEP-01 | Phase 8 | Pending |
| DEP-02 | Phase 8 | Pending |
| DEP-03 | Phase 9 | Pending |
| DEP-04 | Phase 10 | Pending |
| DEP-05 | Phase 10 | Pending |
| DOCS-01 | Phase 10 | Pending |

**Coverage:**
- v1 requirements: 27 total
- Mapped to phases: 27
- Unmapped: 0 ✓

---
*Requirements defined: 2026-07-08*
*Last updated: 2026-07-08 — traceability populated by roadmapper*
