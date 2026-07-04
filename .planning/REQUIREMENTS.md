# Requirements: k8s-launchpad (PRD-1 Foundation)

**Defined:** 2026-07-04
**Core Value:** `make cluster-up && make build && make load && make deploy` produces a running, reachable app on a local kind cluster — the full local build-to-deploy loop works end to end.

## v1 Requirements

Requirements for PRD-1 (foundation milestone). Each maps to roadmap phases.

### Repo Scaffold

- [ ] **SCAF-01**: Monorepo layout exists (`apps/field-guide-api/`, `charts/field-guide-api/`, `infra/kind/`, `scripts/`, `docs/`) with room left for `infra/argocd/` (PRD-2) and `infra/observability/` (PRD-4)
- [ ] **SCAF-02**: `.gitignore` covers `.env`, `__pycache__`, `.venv`, `*.pyc`, kubeconfig — in place before the first meaningful commit
- [ ] **SCAF-03**: `.gitattributes` enforces LF line endings so shell scripts work inside containers and on WSL2/Git Bash

### Field-Guide API

- [ ] **API-01**: Developer can GET a list of field-guide entries (markdown-based DevOps knowledge) via REST
- [ ] **API-02**: Developer can GET a single entry by id
- [ ] **API-03**: Developer can POST a new entry
- [ ] **API-04**: Entries persist in MongoDB (containerized; app reads connection string from env / Kubernetes Secret)
- [ ] **API-05**: `/health` liveness returns 200 when the process is up; readiness reflects MongoDB connectivity (503 when DB unreachable)
- [ ] **API-06**: `/metrics` exposes Prometheus-format metrics (request count, latency) — scrape seam for PRD-4

### Testing

- [ ] **TEST-01**: pytest unit tests cover all API endpoints and pass via `make test` without a running cluster (app factory + test config / mocked MongoDB)

### Containerization

- [ ] **IMG-01**: Dockerfile builds a small working image (python:3.11-slim base, non-root user)
- [ ] **IMG-02**: Image serves via gunicorn (graceful SIGTERM handling), never the Flask dev server

### Cluster Infrastructure

- [ ] **CLUS-01**: `make cluster-up` creates a kind cluster with a wired local registry (containerd mirror config on every node, registry on kind network)
- [ ] **CLUS-02**: `make cluster-down` tears down cluster and registry cleanly and is safe to re-run

### Helm Deployment

- [ ] **HELM-01**: Helm chart deploys the app with Deployment, Service, ConfigMap, Secret template, and values.yaml; `helm lint` passes
- [ ] **HELM-02**: Deployed app is reachable locally (port-forward or NodePort) and returns data from `/health` and field-guide endpoints
- [ ] **HELM-03**: MongoDB runs in-cluster via plain `mongo:7` official-image manifests embedded in the chart (NOT Bitnami — paywalled since 2025)
- [ ] **HELM-04**: values.yaml is generic (image.*, service.*, resources, secrets, `metrics.enabled`, `imagePullPolicy: IfNotPresent`) so PRD-3 can template new apps from it

### Developer Experience

- [ ] **MAKE-01**: Makefile targets `cluster-up`, `cluster-down`, `build`, `load`, `deploy`, `test`, `clean` all work under WSL2 and Git Bash (`MSYS_NO_PATHCONV` handled)
- [ ] **MAKE-02**: Full loop `make cluster-up && make build && make load && make deploy` results in a running app reachable locally

### Documentation

- [ ] **DOCS-01**: README documents end-to-end local setup: clone → make cluster-up → make deploy → curl, including prerequisites (Docker, kind, Helm, make on Windows)

## v2 Requirements

Deferred to later PRDs. Tracked but not in current roadmap.

### GitOps (PRD-2)

- **GITOPS-01**: ArgoCD syncs deployments from Git

### Platform Layer (PRD-3)

- **PLAT-01**: Web dashboard for registering Git repos; new apps templated from the generic chart

### Observability & Security (PRD-4)

- **OBS-01**: Prometheus/Grafana/Loki deployed and scraping `/metrics`
- **OBS-02**: Trivy vulnerability scanning

### Cloud (final PRD)

- **CLOUD-01**: AWS/EKS/Terraform deployment

## Out of Scope

Explicitly excluded from PRD-1. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| ArgoCD / GitOps | PRD-2; only directory seam (`infra/argocd/` room) built now |
| Platform dashboard / repo onboarding | PRD-3; values.yaml seam built now |
| Prometheus/Grafana/Loki/Trivy deployment | PRD-4; only `/metrics` endpoint seam built now |
| AWS / EKS / Terraform | Final PRD; this milestone is local and free only |
| Ingress controller / TLS | Over-engineering for local foundation; port-forward/NodePort suffices |
| RBAC / NetworkPolicies | Over-engineering for single-user local cluster |
| HPA / autoscaling | No load to scale for; `replicaCount: 1` seam kept in values.yaml |
| MongoDB replicaset / persistence hardening | Standalone `mongo:7` is enough for ephemeral kind clusters |
| Bitnami MongoDB Helm dependency | Broadcom paywall (2025) causes ImagePullBackOff on fresh clusters |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| (populated by roadmap) | | |

**Coverage:**
- v1 requirements: 19 total
- Mapped to phases: 0
- Unmapped: 19 ⚠️ (pending roadmap)

---
*Requirements defined: 2026-07-04*
*Last updated: 2026-07-04 after initial definition*
