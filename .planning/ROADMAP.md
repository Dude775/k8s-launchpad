# Roadmap: k8s-launchpad (PRD-1 Foundation)

## Overview

PRD-1 builds the foundation of a self-hosted Internal Developer Platform: a Flask field-guide API, containerized with Docker, deployed via Helm onto a local kind cluster, backed by in-cluster MongoDB, and managed through a Makefile developer CLI. The four phases follow hard dependency order — clean repo hygiene first, then the application and its tests, then the cluster and registry, then containerization and Helm deployment, and finally the Makefile wiring that ties every previous artifact into a single-command loop. The milestone is complete when `make cluster-up && make build && make load && make deploy` produces a running, reachable app on a local kind cluster.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Scaffold + App + Tests** - Monorepo layout, Flask field-guide API, and passing test suite — all runnable without a cluster
- [ ] **Phase 2: Cluster Infrastructure** - Idempotent kind cluster with wired local registry
- [ ] **Phase 3: Containerization + Helm Deployment** - App running in-cluster, reachable locally, backed by in-cluster MongoDB
- [ ] **Phase 4: Makefile + Documentation** - Full developer loop wired end-to-end; project is self-documenting

## Phase Details

### Phase 1: Scaffold + App + Tests

**Goal**: The monorepo exists with clean git hygiene (.gitignore/.gitattributes as the first commit), a fully working Flask field-guide API that runs locally, and a pytest suite that passes without a cluster
**Depends on**: Nothing (first phase)
**Requirements**: SCAF-01, SCAF-02, SCAF-03, API-01, API-02, API-03, API-04, API-05, API-06, TEST-01
**Success Criteria** (what must be TRUE):

  1. `.gitignore` and `.gitattributes` are the first commit — no secrets can be accidentally committed and no shell script has CRLF endings
  2. `pytest` (without a running cluster) produces a green suite covering all API endpoints, with MongoDB mocked
  3. The Flask app starts locally and serves GET /entries, GET /entries/:id, and POST /entries backed by MongoDB connection string from env
  4. GET /health returns 200 when MongoDB is reachable and 503 when it is not; GET /metrics returns Prometheus-format text
  5. Directory layout matches the target monorepo structure including placeholder dirs for PRD-2 (`infra/argocd/`) and PRD-4 (`infra/observability/`) seams

**Plans**: 3 plans
Plans:
**Wave 1**

- [x] 01-01-PLAN.md — Scaffold monorepo layout + git hygiene (.gitignore/.gitattributes first, PRD-2/PRD-4 dir seams)

**Wave 2** *(blocked on Wave 1 completion)*

- [ ] 01-02-PLAN.md — Flask field-guide API: app factory, entries CRUD, /health readiness, /metrics seam (env-driven config, gunicorn entrypoint)

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 01-03-PLAN.md — pytest suite with mocked MongoDB covering all endpoints + minimal `make test` target

### Phase 2: Cluster Infrastructure

**Goal**: A local kind cluster with a wired local registry is available as a reusable, idempotent target that cluster pods can pull images from
**Depends on**: Phase 1
**Requirements**: CLUS-01, CLUS-02
**Success Criteria** (what must be TRUE):

  1. `make cluster-up` creates a kind cluster and `registry:3` container from scratch without errors on a fresh or cleaned machine
  2. A test image pushed to `localhost:5001` is pullable from within a cluster pod — containerd mirror and network wiring verified end-to-end
  3. `make cluster-down` tears down the cluster and registry cleanly and can be re-run multiple times without side effects

**Plans**: TBD

### Phase 3: Containerization + Helm Deployment

**Goal**: The field-guide API runs as a gunicorn container in the kind cluster, reachable locally, backed by in-cluster MongoDB deployed via plain mongo:7 manifests inside the Helm chart
**Depends on**: Phase 2
**Requirements**: IMG-01, IMG-02, HELM-01, HELM-02, HELM-03, HELM-04
**Success Criteria** (what must be TRUE):

  1. `docker build` produces a working image; the container runs as a non-root user and is served by gunicorn (not the Flask dev server)
  2. `helm lint` passes; `helm install` deploys both the app and MongoDB to the kind cluster without errors
  3. The deployed app responds at `/health` (200) and returns entries from `/entries` via port-forward or NodePort
  4. MongoDB is running as plain `mongo:7` manifests embedded inside the chart templates; `helm uninstall` removes all resources cleanly
  5. `values.yaml` is generic (image.*, service.*, resources, secrets, metrics.enabled, imagePullPolicy) and structured so PRD-3 can template new apps from it

**Plans**: TBD

### Phase 4: Makefile + Documentation

**Goal**: The complete developer experience is wired — one command sequence launches the full stack from a clean state; the README enables a new developer to reproduce the end-to-end flow without assistance
**Depends on**: Phase 3
**Requirements**: MAKE-01, MAKE-02, DOCS-01
**Success Criteria** (what must be TRUE):

  1. `make cluster-up && make build && make load && make deploy` runs end-to-end without errors in both Git Bash and WSL2
  2. After the make sequence, the deployed app is reachable locally and returns 200 from `/health` and data from `/entries`
  3. A developer new to the project can follow the README (clone → `make cluster-up` → `make deploy` → `curl`) without needing any additional guidance

**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Scaffold + App + Tests | 1/3 | In Progress|  |
| 2. Cluster Infrastructure | 0/TBD | Not started | - |
| 3. Containerization + Helm Deployment | 0/TBD | Not started | - |
| 4. Makefile + Documentation | 0/TBD | Not started | - |
