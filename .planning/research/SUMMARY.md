# Project Research Summary

**Project:** k8s-launchpad
**Domain:** Local Kubernetes Internal Developer Platform -- Foundation (PRD-1)
**Researched:** 2026-07-04
**Confidence:** HIGH

## Executive Summary

k8s-launchpad PRD-1 is a local Kubernetes IDP foundation: a Flask REST API containerized with Docker, deployed via Helm onto a kind cluster, backed by MongoDB, and managed through a Makefile developer CLI. The project runs entirely on a Windows/WSL2 host with Git Bash as the shell environment, which introduces a distinct class of platform-specific pitfalls that must be addressed at the repo scaffold stage before any other work begins. Research confirms the stack is mature, all library versions are verified against official sources, and the architectural patterns (app factory, local registry, generic Helm values) are well-established in the Kubernetes community.

The recommended approach is to build in strict dependency order: scaffold the repo (.gitignore + .gitattributes first commit), then bootstrap the kind cluster with a local OCI registry, then build the Flask app using the application factory pattern, containerize it with a multi-stage python:3.11-slim Dockerfile, package it in a Helm chart with plain MongoDB manifests (Bitnami is no longer free since Aug 2025), and wire everything together through Makefile targets. The /health and /metrics endpoints are first-class deliverables, not afterthoughts -- they represent forward-compatibility seams for PRD-2 (ArgoCD), PRD-3 (dashboard), and PRD-4 (Prometheus/Grafana).

The key risks are platform-specific: CRLF line endings in shell scripts break silently in WSL2, MSYS path mangling corrupts docker -v flags in Git Bash, the Bitnami MongoDB chart pulls fail on fresh clusters post-August 2025, and the kind local registry requires explicit containerd mirror configuration on each node -- docker push succeeding while pods still show ImagePullBackOff is the most common wasted-hour failure for this stack. All of these have known, documented mitigations that must be implemented in the first two phases.

## Key Findings

### Recommended Stack

All versions verified against PyPI, GitHub releases, and official docs as of 2026-07-04. Python 3.11 is locked by the developer existing stack; all chosen libraries are compatible. Flask 3.x with Flask-PyMongo 3.0.1 and PyMongo 4.13.2 is the correct synchronous Flask+MongoDB combination. Gunicorn 26.0.0 is the production WSGI server (1 worker per pod). prometheus-flask-exporter 0.23.2 auto-instruments all routes with zero configuration. For the local cluster, kind v0.32.0 with a registry:3 container on port 5001 is the canonical 2025/2026 setup per official kind docs.

Critical stack decision -- MongoDB: Bitnami MongoDB Helm chart moved behind a Broadcom commercial paywall effective August 28, 2025. Do not use it. The correct approach is plain Kubernetes manifests (mongodb-deployment.yaml, mongodb-service.yaml, mongodb-pvc.yaml, mongodb-secret.yaml) using the official mongo:7 Docker Hub image, embedded directly inside charts/field-guide-api/templates/. This keeps MongoDB in-chart, deletable with helm uninstall, and readable by portfolio reviewers.

**Core technologies:**
- Python 3.11 + Flask 3.1.3: Runtime and framework -- app factory pattern required for testability
- Flask-PyMongo 3.0.1 + PyMongo 4.13.2: MongoDB driver -- handles app-context teardown and connection pooling
- gunicorn 26.0.0: WSGI server in container -- 1 worker, graceful SIGTERM handling for Kubernetes
- prometheus-flask-exporter 0.23.2: /metrics endpoint -- zero-config auto-instrumentation, PRD-4 seam
- kind v0.32.0 + registry:3: Local cluster + OCI registry -- localhost:5001, containerd mirror config required
- Helm 4.2.2 (or 3.21.2): Chart packaging -- chart format is identical; prefer Helm 4 for fresh installs
- mongo:7 (official Docker Hub): In-cluster database -- plain Deployment manifests, not Bitnami

### Expected Features

All 11 deliverables are defined in PRD-1. The dependency chain is strict: .gitignore before first commit, app factory before tests, cluster before make load, registry before make deploy, MongoDB before /health/ready.

**Must have (table stakes) -- PRD-1 blocked without these:**
- GET /entries, GET /entries/:id, POST /entries with MongoDB backend
- /health/live (200 always) and /health/ready (200 if MongoDB up, 503 if down) as separate routes
- /metrics returning Prometheus text format (request count + latency at minimum)
- conftest.py with app/client fixtures; MongoDB mocked; make test passes
- python:3.11-slim Dockerfile, non-root user, gunicorn CMD, .dockerignore
- make cluster-up idempotent: creates kind cluster + registry:3, patches each node hosts.toml
- Helm chart: Deployment + Service + ConfigMap + probes + imagePullPolicy: IfNotPresent
- MongoDB via plain manifests: standalone, auth enabled, PVC
- Makefile: cluster-up, cluster-down, build, push, deploy, test, clean -- all working under WSL2/Git Bash
- README: prerequisites with exact versions, end-to-end quickstart, make targets table
- .gitignore: .env, __pycache__, .venv, kubeconfig -- first commit

**Should have (differentiators -- within PRD-1 if time allows):**
- help target with aligned descriptions (self-documenting Makefile)
- Multi-stage Dockerfile (build tools excluded from runtime)
- Response envelope on GET /entries returning data array with count field
- Structured JSON logging with python-json-logger (feeds PRD-4 Loki seam)
- Checksum annotation on Deployment for ConfigMap changes
- pytest-cov threshold gate (80% minimum, 95% aspirational)

**Defer to v2+ (do not add in PRD-1):**
- Authentication / JWT (PRD-3 scope)
- ArgoCD GitOps (PRD-2 -- infra/argocd/ placeholder directory only)
- Prometheus/Grafana/Loki deployment (PRD-4 -- /metrics endpoint only in PRD-1)
- Ingress controller / MetalLB (PRD-2/3 scope)
- Multi-node kind cluster, HPA, NetworkPolicy, PodDisruptionBudget
- MongoDB replicaset mode (standalone sufficient)

### Architecture Approach

The architecture is a single-app monorepo with clear directory boundaries: apps/field-guide-api/ (Flask source + Dockerfile + tests), charts/field-guide-api/ (Helm chart with embedded MongoDB manifests), infra/kind/ (cluster YAML + registry bootstrap script), scripts/ (shell), and Makefile as the primary developer interface. The Flask app uses the application factory pattern (create_app() in src/__init__.py) with blueprints for entries and health as separate modules. Extensions (PyMongo, prometheus-flask-exporter) are initialized at module level and wired via init_app() inside the factory to prevent circular imports and enable test isolation.

**Major components:**
1. apps/field-guide-api/ -- Flask REST API; app factory; blueprints/entries.py (CRUD) and blueprints/health.py (/health, /metrics)
2. charts/field-guide-api/ -- Helm chart; Deployment + Service + ConfigMap + Secret + MongoDB manifests in templates/
3. infra/kind/ + scripts/kind-with-registry.sh -- Idempotent cluster bootstrap: registry:3 + kind cluster + containerd mirror + network connect + ConfigMap
4. Makefile -- Developer CLI; dependency chain cluster-up then build then push then deploy; SHELL := /bin/bash and MSYS_NO_PATHCONV=1 required
5. Local registry container (kind-registry on localhost:5001) -- Image store; docker push from host, containerd pull from pods via kind Docker network

### Critical Pitfalls

1. **kind containerd mirror not configured** -- docker push localhost:5001/image:tag succeeds but pods get ImagePullBackOff. Fix: run the full kind-with-registry.sh script that writes hosts.toml on each node and connects registry to kind Docker network. Verify with a test image pull from within the cluster.

2. **CRLF line endings in shell scripts** -- Scripts fail with bad interpreter in WSL2/containers. Fix: commit .gitattributes with *.sh text eol=lf, Makefile text eol=lf, *.yaml text eol=lf as the very first commit, before any scripts exist.

3. **Bitnami MongoDB chart broken** -- ImagePullBackOff on fresh clusters post-August 2025; docker.io/bitnami/mongodb requires commercial login. Fix: use mongo:7 official image with plain Kubernetes manifests in the Helm chart templates directory.

4. **MSYS path mangling in Git Bash** -- docker -v flags and kubectl cp paths get corrupted. Fix: export MSYS_NO_PATHCONV := 1 at top of Makefile.

5. **MongoDB authSource=admin missing** -- Authentication failed even with correct credentials. Fix: connection string must explicitly include ?authSource=admin -- the root user exists in the admin database, not the app database.

6. **Secrets committed before .gitignore** -- Permanent git history exposure. Fix: .gitignore and .gitattributes as the very first commit.

7. **Flask dev server in Dockerfile CMD** -- 30-second forced pod termination on every rollout. Fix: use gunicorn with 1 worker as the CMD from day one.

## Implications for Roadmap

Based on the build-order dependency chain in ARCHITECTURE.md and the pitfall-to-phase mapping in PITFALLS.md, the natural phase structure follows hard dependencies. Nothing can deploy before the cluster exists; nothing can test Flask before the factory pattern is in place; the Makefile wraps everything.

### Phase 1: Repo Scaffold
**Rationale:** .gitattributes and .gitignore must exist before any other file. CRLF and secret-commit pitfalls are permanent and unrecoverable without git history rewriting. This phase has zero functional output but unblocks all other phases safely.
**Delivers:** .gitignore, .gitattributes, .env.example, README.md skeleton, directory structure (apps/, charts/, infra/, scripts/, docs/), empty placeholder dirs (infra/argocd/, infra/observability/) with .gitkeep
**Avoids:** CRLF pitfall, secrets-in-git pitfall, Docker daemon documentation gap
**Research flag:** Standard pattern -- no deeper research needed

### Phase 2: Cluster Infrastructure
**Rationale:** The kind cluster and local registry are hard prerequisites for image loading and deployment. The containerd mirror configuration is the most time-consuming pitfall; getting it right here prevents repeated debugging in later phases.
**Delivers:** infra/kind/cluster.yaml, scripts/kind-with-registry.sh (idempotent, registry:3, hosts.toml patching, network connect, ConfigMap), make cluster-up, make cluster-down
**Uses:** kind v0.32.0, registry:3, Docker 27.x
**Avoids:** Registry containerd wiring pitfall, kind load + :latest pitfall, Docker daemon split, MSYS path mangling
**Research flag:** Standard pattern -- kind official docs are authoritative; complete script provided in STACK.md research

### Phase 3: Flask Application
**Rationale:** The app factory pattern must be established before writing any routes -- it gates testability. /health and /metrics are PRD-1 deliverables and forward-compatibility seams; they must be built alongside the CRUD endpoints, not bolted on later.
**Delivers:** src/__init__.py (create_app factory), src/config.py, src/extensions.py (PyMongo init), blueprints/entries.py (3 CRUD routes), blueprints/health.py (/health/live, /health/ready, /metrics), requirements.txt, requirements-dev.txt
**Uses:** Flask 3.1.3, Flask-PyMongo 3.0.1, PyMongo 4.13.2, prometheus-flask-exporter 0.23.2, python-dotenv 1.2.2
**Avoids:** Flask dev server pitfall, circular import anti-pattern
**Research flag:** Standard pattern -- Flask app factory is well-documented

### Phase 4: Containerization
**Rationale:** Containerize before writing the Helm chart -- Helm needs a working image in the registry. The multi-stage Dockerfile and non-root user are PRD-1 deliverables, not optional polish.
**Delivers:** Dockerfile (multi-stage, python:3.11-slim, non-root appuser, gunicorn CMD), .dockerignore, make build, make push (to localhost:5001)
**Uses:** python:3.11-slim base (NOT Alpine -- musl libc incompatible with PyMongo wheels), gunicorn 26.0.0
**Avoids:** Alpine base image pitfall, gunicorn multiprocess prometheus collision (use --workers 1 with documentation), imagePullPolicy + latest tag pitfall
**Research flag:** Standard pattern -- Dockerfile best practices well-established

### Phase 5: Helm Chart + MongoDB
**Rationale:** Helm packaging and MongoDB deployment are coupled -- the chart embeds MongoDB manifests. The Bitnami paywall decision must be implemented here. The values.yaml structure is a PRD-3 seam and must be clean and generic from the start.
**Delivers:** Chart.yaml, values.yaml (image/replicaCount/service/config/secrets/resources), templates/deployment.yaml (livenessProbe, readinessProbe, resource limits), templates/service.yaml, templates/configmap.yaml, templates/secret.yaml, templates/mongodb-*.yaml (4 files), make deploy
**Uses:** Helm 4.2.2, mongo:7 official image (NOT Bitnami), imagePullPolicy: IfNotPresent
**Avoids:** Bitnami paywall pitfall, Helm version/appVersion confusion, hard-coded image coordinates, secrets in values.yaml, missing --wait on helm upgrade
**Research flag:** MongoDB auth (authSource=admin) needs deliberate testing -- pitfall is subtle and environment-specific

### Phase 6: Makefile + Developer Experience
**Rationale:** The Makefile is the developer interface contract. It must work in both WSL2 and Git Bash -- test both explicitly. SHELL := /bin/bash and MSYS_NO_PATHCONV=1 headers are not optional on this dev environment.
**Delivers:** Complete Makefile (SHELL := /bin/bash, MSYS_NO_PATHCONV export, .PHONY declarations, all 9 core targets, help target with descriptions, REGISTRY/APP_NAME/TAG variables, ANSI color, port-forward target)
**Avoids:** Makefile tabs/spaces pitfall, MSYS path mangling, parallel target race conditions
**Research flag:** Standard pattern -- test every target in Git Bash AND WSL2 before marking done

### Phase 7: Tests + Documentation
**Rationale:** Tests validate all previous phases without a running cluster. MongoDB must be mocked. The README is a portfolio deliverable -- end-to-end quickstart with paste-able commands is the core value proposition.
**Delivers:** tests/conftest.py (app + client fixtures, mongomock), tests/test_entries.py (CRUD happy + error paths, /health, /metrics), pytest.ini, make test with 80% coverage gate, complete README.md (prerequisites, quickstart, make targets table, ASCII architecture diagram, repo structure, troubleshooting, PRD roadmap table)
**Uses:** pytest 9.1.1, pytest-flask 1.3.0, pytest-cov 5.x, mongomock
**Avoids:** Integration tests against real MongoDB, committing real .env for reviewers
**Research flag:** Verify mongomock supports PyMongo 4.13.x API before writing tests; fall back to monkeypatch if incompatible

### Phase Ordering Rationale

- Phase 1 must be first: CRLF and secrets pitfalls are unrecoverable -- they poison the entire git history permanently
- Phase 2 before Phase 4: The local registry must exist before any image push
- Phase 3 before Phase 4: Flask app must work locally before containerizing; Dockerfile CMD must match app entry point
- Phase 4 before Phase 5: Helm chart references image coordinates; image must exist in registry before first deploy
- Phase 5 embeds MongoDB: MongoDB manifests live inside the Helm chart -- deployed together in a single helm install
- Phase 6 wraps all phases: Makefile targets call all previous phases artifacts; finalize after all components exist
- Phase 7 validates all phases: Tests cover all endpoints without a running cluster; README documents the completed system

### Research Flags

Phases needing deliberate verification during implementation:
- **Phase 2 (Cluster Infrastructure):** Verify registry wiring with a test image pull from within the cluster BEFORE proceeding to Phase 4. This is the most common wasted-hour pitfall.
- **Phase 5 (Helm + MongoDB):** Test MongoDB auth connection string with ?authSource=admin explicitly. Verify make deploy on a fresh cluster before declaring done.
- **Phase 7 (Tests):** Verify mongomock version supports PyMongo 4.13.x API before writing tests; fall back to monkeypatch if incompatible.

Phases with standard well-documented patterns (straightforward implementation):
- **Phase 1 (Scaffold):** Boilerplate -- .gitattributes and .gitignore patterns are universal
- **Phase 3 (Flask App):** App factory is the Flask canonical pattern; no surprises expected
- **Phase 4 (Containerization):** Multi-stage python:3.11-slim Dockerfile is well-documented
- **Phase 6 (Makefile):** Standard Makefile patterns; WSL2 headers are documented in STACK.md

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified against PyPI and official GitHub releases as of 2026-07-04. Bitnami paywall confirmed via official issue tracker. |
| Features | HIGH | All 11 deliverables mapped to table-stakes/differentiators/anti-features with dependency chain analysis. MVP definition is explicit and complete. |
| Architecture | HIGH | Verified against kind official docs, Flask Context7, Helm Context7. Build order matches hard dependency constraints from ARCHITECTURE.md. |
| Pitfalls | HIGH | 13 pitfalls documented with warning signs, recovery strategies, and phase mapping. Most verified against official issues and community reports. |

**Overall confidence:** HIGH

### Gaps to Address

- **mongomock PyMongo 4.x compatibility:** mongomock library support for PyMongo 4.13.x API should be verified before writing tests in Phase 7. If incompatible, use monkeypatch on the mongo.db object instead.
- **Helm 3 vs Helm 4 binary:** The --atomic flag was renamed to --rollback-on-failure in Helm 4 -- Makefile must not use --atomic for portability across both versions.
- **NodePort vs port-forward:** ARCHITECTURE.md uses NodePort 30080 for local access; FEATURES.md anti-features recommend ClusterIP + port-forward. Reconcile in Phase 5 by making NodePort the default for dev convenience with port-forward documented as alternative.
- **make test MongoDB isolation:** mongomock is the recommended approach; monkeypatch is the fallback. Decide in Phase 7 based on version compatibility check.

## Sources

### Primary (HIGH confidence)
- /pallets/flask (Context7) -- Flask 3.x app factory, blueprints, testing patterns
- /mongodb/docs-pymongo (Context7) -- PyMongo 4.13.2 version confirmation
- /helm/helm-www (Context7) -- Helm chart best practices, values structure, imagePullPolicy
- https://kind.sigs.k8s.io/docs/user/local-registry/ -- canonical registry:3 setup, hosts.toml, ConfigMap pattern
- https://pypi.org/project/Flask/ -- version 3.1.3 (Feb 2026)
- https://pypi.org/project/gunicorn/ -- version 26.0.0 (May 2026)
- https://pypi.org/project/pymongo/ -- version 4.13.2
- https://pypi.org/project/Flask-PyMongo/ -- version 3.0.1, Flask >=3.0 required
- https://pypi.org/project/prometheus-flask-exporter/ -- 0.23.2
- https://github.com/bitnami/charts/issues/35164 -- paywall effective Aug 28 2025
- https://github.com/helm/helm/releases -- Helm 4.2.2 latest
- https://kubernetes.io/docs/concepts/workloads/pods/probes/ -- liveness/readiness probe behavior

### Secondary (MEDIUM confidence)
- https://iximiuz.com/en/posts/kubernetes-kind-load-docker-image/ -- registry preferred over kind load
- https://prometheus.github.io/client_python/multiprocess/ -- PROMETHEUS_MULTIPROC_DIR pattern
- https://testdriven.io/blog/docker-best-practices/ -- multi-stage slim image pattern
- WSL2/MSYS2 CRLF and path conversion -- Microsoft WSL issue tracker and community reports

### Tertiary (LOW confidence)
- kind v0.32.0 version -- inferred from search results; official release page confirms v0.32.0 exists
- mongomock PyMongo 4.x compatibility -- not explicitly verified in research; validate during Phase 7

---
*Research completed: 2026-07-04*
*Ready for roadmap: yes*
