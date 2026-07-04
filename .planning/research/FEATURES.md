# Feature Research

**Domain:** Local Kubernetes Internal Developer Platform — Foundation milestone (PRD-1)
**Researched:** 2026-07-04
**Confidence:** HIGH (all findings verified against official docs, Context7, and multiple sources)

---

## Overview

PRD-1 deliverables are fixed. This document maps each deliverable to three categories:
**table stakes** (missing = deliverable is broken), **differentiators** (portfolio-quality polish worth adding within PRD-1 scope), and **anti-features** (over-engineering to deliberately avoid). Future PRDs (ArgoCD, dashboard, observability stack, AWS) are referenced only as seam callouts — nothing from them belongs here.

---

## Deliverable 1: Flask REST API (field-guide content entries)

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| GET /entries — list all | Basic CRUD read; missing = API is broken | LOW | Return JSON array; empty list is valid |
| GET /entries/:id — single entry | REST convention; 404 on missing ID | LOW | Return 404 JSON body, not empty 200 |
| POST /entries — create entry | Write path required; 201 on success | LOW | Validate required fields; return created object |
| JSON error responses | Clients need parseable errors, not HTML | LOW | `{"error": "..."}` on 400/404/500; no raw tracebacks |
| Application factory pattern (`create_app()`) | Required for testability (different configs per env) | LOW | Without it, pytest cannot swap test config |
| Config from environment variables | Secrets cannot be hardcoded; 12-factor | LOW | `MONGO_URI`, `FLASK_ENV`, `SECRET_KEY` from env |
| Gunicorn as WSGI server in container | Flask dev server is single-threaded, not production-safe | LOW | `CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:create_app()"]` |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Response envelope with metadata | Shows awareness of API design conventions | LOW | `{"data": [...], "count": N}` for list endpoint |
| Input validation with clear error messages | Demonstrates production thinking | LOW | Check required fields (title, content, tags); return which fields are missing |
| Structured JSON logging | Portfolio signal; feeds PRD-4 Loki seam | LOW | `python-json-logger`; log method + path + status on every request |

### Anti-Features

| Feature | Why Requested | Why Avoid in PRD-1 | Alternative |
|---------|---------------|-------------------|-------------|
| Authentication / JWT | "Real APIs have auth" | Adds a full auth subsystem; blocks local testing flow; PRD-3 scope | Leave port open; note in README that auth is PRD-3 |
| API versioning (/v1/entries) | "Best practice" | Premature; only one consumer exists; adds URL complexity | Plain `/entries`; version when breaking change needed |
| Full OpenAPI/Swagger spec | Looks professional | Requires marshmallow or flasgger; doubles schema definitions | Document with curl examples in README |
| Pagination on GET list | "Scalable" | Field-guide has tens of entries, not thousands | Return full list; add pagination when data grows |

---

## Deliverable 2: /health Endpoint

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `GET /health` returns 200 with JSON body | Kubernetes default probe target; missing = pod never passes | LOW | `{"status": "ok"}` minimum |
| Separate `/health/live` and `/health/ready` | Liveness failure = restart; readiness failure = remove from endpoints — conflating them causes restart storms on DB outages | LOW | Use `flask-healthz` or hand-roll two routes |
| Readiness check verifies MongoDB connectivity | Ready means "can serve traffic" — if DB is unreachable, readiness must fail | LOW | Ping MongoDB in readiness check; liveness just returns 200 |
| livenessProbe and readinessProbe in Helm deployment.yaml | Without these, k8s cannot manage the pod lifecycle | LOW | Configure in Helm templates, not in app |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Verbose JSON health body | Shows component-level thinking | LOW | `{"status":"ok","checks":{"mongo":"ok"}}` |
| Startup probe in Helm | Protects slow-starting pods from premature liveness kills | LOW | Set `initialDelaySeconds` on liveness; or add `startupProbe` |

### Anti-Features

| Feature | Why Requested | Why Avoid in PRD-1 | Alternative |
|---------|---------------|-------------------|-------------|
| Health check UI / dashboard | Visible and demonstrable | PRD-3 scope (platform dashboard) | Expose data at `/health`; PRD-3 consumes it |
| Deep dependency graph traversal | "Thorough" | Adds latency to every probe; times out | Check only direct dependency (MongoDB ping) |
| Circuit breakers (tenacity, pybreaker) | "Resilient" | Over-engineering for a local dev cluster; adds state management | Note as future enhancement |

---

## Deliverable 3: /metrics Endpoint (Prometheus Format)

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `GET /metrics` returns Prometheus text format | PRD-4 Prometheus scrapes this; missing seam = PRD-4 blocked | LOW | Install `prometheus-flask-exporter`; auto-registers endpoint |
| HTTP request count by route and status | Core RED metric (Rate); auto-provided by library | LOW | `flask_http_request_total{method,endpoint,http_status}` |
| HTTP request latency histogram | Core RED metric (Duration); auto-provided by library | LOW | `flask_http_request_duration_seconds` |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Custom app info metric | Shows build-time metadata; helps identify running version | LOW | `Info("app_info", "Field Guide API", {"version": APP_VERSION})` |
| Custom entries_total counter | Domain-specific metric; demonstrates awareness of business metrics | LOW | Increment on successful POST /entries |

### Anti-Features

| Feature | Why Requested | Why Avoid in PRD-1 | Alternative |
|---------|---------------|-------------------|-------------|
| Prometheus server deployed in-cluster | Observability | PRD-4 scope; deploying now wastes resources and adds complexity | Expose /metrics endpoint only; PRD-4 adds the scraper |
| Grafana dashboards | Visual output | PRD-4 scope | `/metrics` output satisfies the seam requirement |
| Alerting rules (PrometheusRule CRDs) | "Production complete" | Requires Prometheus Operator; PRD-4 scope | No alerting in PRD-1 |
| Metrics auth / TLS on /metrics | Security | Adds complexity with no local benefit; no external exposure | Document as future hardening |

---

## Deliverable 4: pytest Tests

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `conftest.py` with `app` and `client` fixtures | Flask testing requires test client from factory; missing = no isolation | LOW | `app.config["TESTING"] = True`; yield-based setup/teardown |
| Tests for all three API endpoints | Coverage of all PRD-1 requirements | LOW | 1 test per happy path (200/201) + 1 per error path (404/400) |
| Test for `/health` returning 200 | Health endpoint is a deliverable | LOW | One assertion; very fast |
| Test for `/metrics` returning 200 | Verify exporter is wired; confirms seam | LOW | Assert `b"flask_http"` in response.data |
| MongoDB mocked or faked in unit tests | Tests must not require a running cluster | MEDIUM | Use `mongomock` library or `monkeypatch`; no real Mongo in unit tests |
| `make test` runs pytest | Automation contract; missing = tests are optional | LOW | `pytest apps/field-guide-api/tests/ -v --cov` |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| `pytest-cov` with minimum threshold | Shows 95%+ coverage gate discipline | LOW | `--cov-fail-under=80` for foundation (90+ is aspirational) |
| Parametrized tests for error cases | Shows pytest fluency; compact test surface | LOW | `@pytest.mark.parametrize` for missing fields on POST |
| `pytest.ini` or `pyproject.toml` config | Standardizes test discovery path and options | LOW | `testpaths = tests`, `addopts = -v` |

### Anti-Features

| Feature | Why Requested | Why Avoid in PRD-1 | Alternative |
|---------|---------------|-------------------|-------------|
| Integration tests against real MongoDB | "Real coverage" | Requires running cluster or docker-compose; slows `make test` | Unit tests with mocks; note integration path in README |
| k8s end-to-end tests (kubectl + curl) | "Full stack validation" | Requires cluster to be running; not portable; PRD-2+ scope | `make deploy` smoke test (curl in Makefile) is sufficient |
| Load / performance tests (Locust) | Benchmark data | No baseline to measure against; PRD-4 scope | Defer until observability stack exists |

---

## Deliverable 5: Dockerfile

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `python:3.11-slim` base image | Slim = smaller attack surface and pull time; explicit version = reproducible | LOW | Do NOT use `latest` or `alpine` (C-extension compatibility issues with pymongo) |
| `COPY requirements.txt` before `COPY src/` | Layer caching: dep install only re-runs when requirements change | LOW | Critical for fast rebuilds during development |
| Non-root user in container | Security baseline; rootless = standard k8s best practice | LOW | `RUN useradd -m appuser && USER appuser` |
| `EXPOSE 5000` | Documents the port; required for port-forward and service targeting | LOW | Must match gunicorn bind and Service targetPort |
| Gunicorn as CMD | Flask dev server is not safe for container use | LOW | `gunicorn --workers 2 --bind 0.0.0.0:5000 "app:create_app()"` |
| `.dockerignore` | Without it, `.git/`, `.venv/`, `__pycache__` are sent to build context, bloating image | LOW | Mirror `.gitignore` entries |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Multi-stage build (builder + runtime) | ~50-87% image size reduction; build tools not in runtime layer | MEDIUM | Stage 1: install deps; Stage 2: copy site-packages + app |
| `HEALTHCHECK` instruction | Docker daemon can self-report container health without k8s | LOW | `HEALTHCHECK CMD curl -f http://localhost:5000/health || exit 1` |
| Pinned dependency versions in requirements.txt | Reproducible builds; no surprise upgrades | LOW | `flask==3.1.x`, `pymongo==4.x.x`, exact pins |

### Anti-Features

| Feature | Why Requested | Why Avoid in PRD-1 | Alternative |
|---------|---------------|-------------------|-------------|
| Alpine base image | Smallest possible image | pymongo requires libssl/libcrypt C extensions; Alpine build is fragile and adds debugging pain | `python:3.11-slim` is the correct choice |
| Running as root | "Simpler" | Security anti-pattern; any container escape = host root access | Add non-root user — 2 lines |
| Flask dev server in production | "Works" | Single-threaded, reloader enabled, not safe; k8s will probe it and it will misbehave | Always use gunicorn or uvicorn |

---

## Deliverable 6: kind Cluster + Local Registry

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `kind-config.yaml` with containerd registry config | Without this, kind nodes cannot resolve `localhost:5001` | LOW | `configPatches` pointing containerd to `/etc/containerd/certs.d` |
| Local Docker registry on port 5001 | Images loaded via `kind load` are node-specific; registry is portable | LOW | `docker run -d --name kind-registry -p 5001:5000 registry:2` |
| `hosts.toml` on each node mapping `localhost:5001` → registry | Solves localhost network namespace isolation between host and containerd | LOW | Script runs `docker exec` on each node after creation |
| Registry container joins kind Docker network | Node-to-registry communication requires shared network | LOW | `docker network connect kind kind-registry` |
| `kube-public/local-registry-hosting` ConfigMap | Documents registry to tools and scripts | LOW | Community convention; tooling reads it |
| `make cluster-up` and `make cluster-down` | Automation contract | LOW | cluster-down should also remove registry container |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Named cluster (`--name k8s-launchpad`) | Avoids collision with other kind clusters; explicit context | LOW | `kubectl config use-context kind-k8s-launchpad` |
| Idempotent cluster-up script | Running `make cluster-up` twice should not error | LOW | Check `kind get clusters` before creating |

### Anti-Features

| Feature | Why Requested | Why Avoid in PRD-1 | Alternative |
|---------|---------------|-------------------|-------------|
| Multi-node cluster (control-plane + workers) | "Realistic" | Adds resource overhead with no local benefit; scheduling complexity | Single-node kind cluster is sufficient for PRD-1 |
| MetalLB for LoadBalancer services | "Real cluster feel" | Requires extra CRDs and IP pool config; PRD-2 scope | Use `kubectl port-forward` for local access |
| Ingress controller (nginx) | Route-based access | PRD-2/3 scope; over-engineering for one app | ClusterIP + port-forward is sufficient |

---

## Deliverable 7: Helm Chart

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `Chart.yaml` with name, version, appVersion | Metadata required by Helm; missing = `helm install` fails | LOW | `apiVersion: v2`; semantic version |
| `values.yaml` with image, service, replicaCount, env section | Values must be externalisable for PRD-3 templating seam | LOW | Flat where possible; camelCase keys |
| `templates/deployment.yaml` | Core workload | LOW | Use `helm create` as starting point, prune unused |
| `templates/service.yaml` (ClusterIP) | App must be reachable inside cluster; port-forward needs a Service | LOW | ClusterIP only; no LoadBalancer |
| `templates/configmap.yaml` | Non-secret config (FLASK_ENV, LOG_LEVEL) | LOW | Reference in deployment env section |
| `templates/secret-template.yaml` (documented but not committed with real values) | Teaches the pattern; MONGO_URI must not be hardcoded | LOW | Either placeholder values or `helm install --set` instructions in README |
| `templates/_helpers.tpl` | Name and label helpers; without them, labels are inconsistent | LOW | `helm create` generates this; keep it |
| livenessProbe and readinessProbe in deployment | Without probes, k8s cannot manage pod health | LOW | Wire to `/health/live` and `/health/ready` |
| `imagePullPolicy: IfNotPresent` in values.yaml | Without this, k8s tries to pull `latest` from Docker Hub and fails | LOW | Critical for local registry workflow |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Checksum annotation on deployment for ConfigMap | Triggers rolling update when ConfigMap changes | LOW | `checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}` |
| `resources.requests` and `resources.limits` in values.yaml | Shows awareness of k8s resource management; required for real clusters | LOW | Small defaults (cpu: 100m, memory: 128Mi) |
| `values.schema.json` (minimal) | Validates values types at install time; strong portfolio signal | MEDIUM | Only validate the 5-6 most important fields |

### Anti-Features

| Feature | Why Requested | Why Avoid in PRD-1 | Alternative |
|---------|---------------|-------------------|-------------|
| Ingress resource | "Real access pattern" | Requires ingress controller (not installed); PRD-2/3 scope | ClusterIP + port-forward |
| RBAC (ServiceAccount, Role, RoleBinding) | "Production hardening" | No RBAC-gated API calls in PRD-1; adds 3 extra templates with zero current function | Add when app needs k8s API access |
| HorizontalPodAutoscaler | "Scalable" | Requires metrics-server; single replica is fine locally | `replicaCount: 1` in values.yaml |
| NetworkPolicy | "Secure networking" | Requires CNI that supports it (kind's default does not); adds confusion | Document as PRD-4 hardening |
| PodDisruptionBudget | "HA pattern" | Meaningless with replicaCount: 1 | Irrelevant until multi-replica |

---

## Deliverable 8: MongoDB In-Cluster

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Bitnami mongodb Helm dependency in `Chart.yaml` | Standard, maintained chart; community-verified | LOW | `helm dependency update` fetches it into `charts/` |
| Standalone mode (architecture: standalone) | Simplest viable setup; replicaset = 3x resource overhead for no local benefit | LOW | Set in `values.yaml` under `mongodb:` key |
| Authentication enabled with credentials from Secret | No auth = security anti-pattern even locally; teaches the pattern | LOW | `auth.rootPassword` via Helm --set or values override |
| PersistentVolumeClaim (default StorageClass) | Without persistence, data is lost on pod restart | LOW | kind has a default StorageClass; default PVC works |
| Readiness probe verifies MongoDB is reachable | App readiness check needs MongoDB responding | LOW | Flask `/health/ready` pings Mongo; only works if Mongo is actually ready |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Separate `values-mongo.yaml` or documented `values.yaml` override block | Makes MongoDB config explicit and reviewable | LOW | `mongodb.auth.rootPassword` documented in README with `--set` override |
| Init container or startup check in app deployment | Prevents app starting before MongoDB is ready | MEDIUM | Simple `initContainers` with mongo ping or rely on readinessProbe failure cycling |

### Anti-Features

| Feature | Why Requested | Why Avoid in PRD-1 | Alternative |
|---------|---------------|-------------------|-------------|
| ReplicaSet mode (3 replicas) | "Production-like" | 3x RAM/CPU for a local dev cluster; requires persistent volumes for each | Standalone; document replicaset as production upgrade path |
| MongoDB metrics sidecar (metrics.enabled: true) | Observability | PRD-4 scope; requires Prometheus ServiceMonitor CRD not installed yet | false in PRD-1; PRD-4 enables it |
| MongoDB Atlas / external | "No infra to manage" | Violates local-and-free constraint; network dependency | In-cluster only |
| Backup / Velero | "Data safety" | Field-guide data is synthetic; local cluster is disposable | Document as production concern in README |

---

## Deliverable 9: Makefile

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `cluster-up` target | Core workflow entry point | LOW | Creates kind cluster + registry; idempotent |
| `cluster-down` target | Cleanup; without it, kind clusters accumulate | LOW | Deletes cluster + registry container |
| `build` target | Builds Docker image | LOW | `docker build -t $(REGISTRY)/$(APP_NAME):$(TAG) .` |
| `load` target | Pushes image into cluster | LOW | `docker push localhost:5001/$(APP_NAME):$(TAG)` to local registry |
| `deploy` target | `helm upgrade --install` with correct values | LOW | Must work after `make build && make load` |
| `test` target | `pytest` in correct directory | LOW | Must work without running cluster |
| `clean` target | Removes built images and temp files | LOW | `docker rmi`, delete coverage artifacts |
| `.PHONY` declaration for all targets | Without `.PHONY`, Make treats targets as file names | LOW | `$(MAKEFILE_LIST)` trick or explicit list |
| Top-level variables (REGISTRY, APP_NAME, TAG) | Single source of truth for image coordinates | LOW | `REGISTRY ?= localhost:5001`; allow env override |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| `help` target with aligned descriptions | Self-documenting; strong portfolio signal | LOW | Parse `##` comments on targets with `grep + awk` pattern |
| `check-deps` target | Fails fast if kind/helm/kubectl/docker not installed | LOW | `which kind && which helm && which kubectl` |
| ANSI color in output | Readability; common in well-maintained CLIs | LOW | `GREEN=\033[0;32m`, `NC=\033[0m` |
| `port-forward` target | Convenience for local curl testing | LOW | `kubectl port-forward svc/field-guide-api 5000:80` |

### Anti-Features

| Feature | Why Requested | Why Avoid in PRD-1 | Alternative |
|---------|---------------|-------------------|-------------|
| Parallel target execution (`-j`) | Speed | Race conditions between cluster-up and deploy; debugging nightmare | Sequential targets are correct here |
| Platform detection (OS-specific branches) | WSL2 compatibility | Adds complex `ifeq ($(OS), Windows_NT)` branches that are hard to maintain | Document WSL2 requirement in README; assume Bash |
| GitHub Actions integration in Makefile | "CI-ready" | CI is a separate file (`.github/workflows/`); conflating them adds coupling | Makefile calls tools; CI calls Makefile targets |
| `make all` as default target | Convention | Ambiguous for infra projects; running everything in sequence can break things | Explicit `help` as default target |

---

## Deliverable 10: README

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Prerequisites with exact versions | Without this, "clone and run" fails silently | LOW | kind v0.x+, kubectl v1.x+, helm v3.x+, Docker, make, Python 3.11 |
| End-to-end quickstart: clone → cluster-up → build → load → deploy → curl | The Core Value of the project; if not in README, portfolio value is unclear | LOW | Paste-able commands, no ambiguity |
| Make targets reference table | Developers read Makefiles but also README; duplication is acceptable here | LOW | Two-column: target + description |
| Architecture overview (even ASCII) | Shows structural thinking; expected in any platform project | LOW | Box diagram: Makefile → kind → k8s → Helm → Flask app → MongoDB |
| Repo structure diagram | Monorepo layout is non-obvious to reviewers | LOW | `tree -L 3` output, annotated |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Curl examples with expected output | Removes ambiguity about what "working" looks like | LOW | `curl localhost:5000/entries` → `{"data": [], "count": 0}` |
| Troubleshooting section | Shows operational maturity | LOW | Top 3 failure modes: registry not connected, imagePullPolicy wrong, MongoDB not ready |
| PRD roadmap table | Contextualises PRD-1 within the larger project | LOW | PRD-1 (foundation) → PRD-2 (GitOps) → PRD-3 (dashboard) → PRD-4 (observability) → AWS |

### Anti-Features

| Feature | Why Requested | Why Avoid in PRD-1 | Alternative |
|---------|---------------|-------------------|-------------|
| MkDocs / DocSite | Professional look | Heavy; no hosting in PRD-1; README is sufficient for local portfolio | README.md is correct scope |
| CHANGELOG.md | "Open source convention" | Over-engineering for a portfolio project; git log is the changelog | Skip; add if open-sourcing later |
| CONTRIBUTING.md | "Community project" | No contributors other than the author in PRD-1 | Skip |

---

## Deliverable 11: .gitignore

### Table Stakes

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| `.env` | Secrets cannot be committed; this is the most critical line | LOW | Must be in place BEFORE first meaningful commit |
| `__pycache__/`, `*.pyc`, `*.pyo` | Python bytecode; pollutes repo | LOW | Standard Python ignore |
| `.venv/`, `venv/` | Virtual environment; large, not portable | LOW | Standard Python ignore |
| `kubeconfig`, `*.kubeconfig` | k8s credentials; sensitive | LOW | kind creates kubeconfig; must not be committed |
| `*.egg-info/`, `dist/`, `build/` | Python packaging artifacts | LOW | Standard Python ignore |
| `.coverage`, `htmlcov/` | Test artifacts; large, not source | LOW | Generated by pytest-cov |

### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| IDE patterns (`.idea/`, `.vscode/`) | Keeps repo clean for all editors | LOW | Personal preference but professional signal |
| `charts/*/charts/` and `charts/*/tmpcharts/` | Helm dependency artifacts should not be committed | LOW | `helm dependency update` regenerates them; re-fetching is cheap |
| `*.log` | Log files from gunicorn or pytest | LOW | Obvious but easily forgotten |

### Anti-Features

| Feature | Why Requested | Why Avoid in PRD-1 | Alternative |
|---------|---------------|-------------------|-------------|
| Committing any real .env file | "Convenience for reviewers" | Real credentials in git history are permanent and searchable | `.env.example` with placeholder values committed instead |
| Over-broad ignores (`*`) | "Simple" | Prevents tracking intentional files; debugging `git add` becomes a nightmare | Be explicit and documented |

---

## Feature Dependencies

```
.gitignore
    └──must exist before──> first meaningful commit

Flask app (create_app factory)
    └──required by──> pytest (test client isolation)
    └──required by──> /health readiness check (app context)
    └──required by──> /metrics (exporter wired at factory time)

/health/ready
    └──requires──> MongoDB connection (readiness checks DB)
    └──configured in──> Helm deployment.yaml readinessProbe

/metrics
    └──requires──> prometheus-flask-exporter installed and wired
    └──seam for──> PRD-4 Prometheus scraper (do not deploy scraper now)

Dockerfile
    └──required by──> `make build`

`make build`
    └──required by──> `make load`

`make cluster-up` (kind + registry)
    └──required by──> `make load` (registry must exist)
    └──required by──> `make deploy` (cluster must exist)

`make load`
    └──required by──> `make deploy` (image must be in registry)

MongoDB Helm dependency
    └──required by──> `make deploy` (chart must resolve dependency)
    └──required by──> /health/ready (app pings Mongo)

Helm chart (values.yaml structure)
    └──seam for──> PRD-3 app templating (do not add PRD-3 logic now)

`infra/argocd/` directory (empty, placeholder)
    └──seam for──> PRD-2 GitOps (do not configure ArgoCD now)

`infra/observability/` directory (empty, placeholder)
    └──seam for──> PRD-4 Prometheus/Grafana/Loki (do not deploy now)
```

### Dependency Notes

- **pytest requires app factory**: `create_app(test_config={"TESTING": True})` is the only safe way to swap MongoDB URI for test isolation. Without factory pattern, tests hit production config.
- **`make load` requires cluster-up first**: The local registry container must be running and connected to the kind network before pushing images.
- **/health/ready requires MongoDB**: Kubernetes will cycle readiness failures until MongoDB pod is Ready; this is expected and correct behavior — not a bug to work around.
- **Helm chart values.yaml is a seam**: PRD-3 will template new apps by copying this chart's `values.yaml` structure. Keep it clean and documented now.

---

## MVP Definition

### Launch With (PRD-1 complete)

Every item below must be true for PRD-1 to be complete:

- [ ] Flask API: GET /entries, GET /entries/:id, POST /entries — working with MongoDB
- [ ] /health/live (200) and /health/ready (200 when Mongo up, 503 when Mongo down)
- [ ] /metrics returns Prometheus text with at least request count and latency
- [ ] pytest suite: all endpoints tested, MongoDB mocked, `make test` passes
- [ ] Dockerfile: python:3.11-slim, non-root user, gunicorn, .dockerignore present
- [ ] kind cluster + local registry: `make cluster-up` is idempotent and leaves a working cluster
- [ ] Helm chart: Deployment + Service + ConfigMap + values.yaml + probes + imagePullPolicy: IfNotPresent
- [ ] MongoDB via Helm dependency: standalone mode, auth enabled, PVC
- [ ] Makefile: cluster-up, cluster-down, build, load, deploy, test, clean — all working under WSL2/Git Bash
- [ ] README: prerequisites, quickstart commands, make targets table, repo structure
- [ ] .gitignore: .env, __pycache__, .venv, kubeconfig — committed before any other file

### Add After Validation (within PRD-1, if time allows)

- [ ] Differentiator: `help` target with aligned descriptions
- [ ] Differentiator: multi-stage Dockerfile
- [ ] Differentiator: response envelope on GET /entries
- [ ] Differentiator: structured JSON logging
- [ ] Differentiator: checksum annotation in Helm deployment

### Future Consideration (PRD-2 and beyond)

- [ ] ArgoCD GitOps (PRD-2) — `infra/argocd/` placeholder only in PRD-1
- [ ] Ingress controller + routing (PRD-2/3)
- [ ] Platform dashboard + repo onboarding (PRD-3)
- [ ] Prometheus/Grafana/Loki/Trivy deployment (PRD-4)
- [ ] RBAC / NetworkPolicy (PRD-4 hardening)
- [ ] AWS/EKS (final PRD)

---

## Feature Prioritization Matrix

| Feature | Portfolio Value | Implementation Cost | Priority |
|---------|----------------|---------------------|----------|
| App factory + 3 CRUD endpoints | HIGH | LOW | P1 |
| /health/live + /health/ready (separate) | HIGH | LOW | P1 |
| /metrics with prometheus-flask-exporter | HIGH | LOW | P1 |
| pytest with mocked MongoDB | HIGH | MEDIUM | P1 |
| Dockerfile (slim, non-root, gunicorn) | HIGH | LOW | P1 |
| kind cluster + local registry script | HIGH | LOW | P1 |
| Helm chart with probes + imagePullPolicy | HIGH | LOW | P1 |
| MongoDB Helm dependency (standalone) | HIGH | LOW | P1 |
| Makefile 7 core targets | HIGH | LOW | P1 |
| README quickstart | HIGH | LOW | P1 |
| .gitignore (before first commit) | HIGH | LOW | P1 |
| help target in Makefile | MEDIUM | LOW | P2 |
| Multi-stage Dockerfile | MEDIUM | MEDIUM | P2 |
| Structured JSON logging | MEDIUM | LOW | P2 |
| Response envelope on GET list | MEDIUM | LOW | P2 |
| Checksum annotation in Helm | MEDIUM | LOW | P2 |
| values.schema.json (minimal) | MEDIUM | MEDIUM | P2 |
| pytest-cov threshold gate | MEDIUM | LOW | P2 |
| port-forward Makefile target | LOW | LOW | P3 |
| HEALTHCHECK in Dockerfile | LOW | LOW | P3 |
| init container for MongoDB readiness | LOW | MEDIUM | P3 |

---

## Sources

- [flask-healthz — liveness/readiness for Flask](https://github.com/fedora-infra/flask-healthz/)
- [Kubernetes Liveness, Readiness, and Startup Probes](https://kubernetes.io/docs/concepts/workloads/pods/probes/)
- [prometheus-flask-exporter](https://pypi.org/project/prometheus-flask-exporter/)
- [Flask Testing — official docs](https://flask.palletsprojects.com/en/stable/testing/)
- [Helm Chart Best Practices — official](https://helm.sh/docs/chart_best_practices/)
- [Helm Values Best Practices](https://helm.sh/docs/chart_best_practices/values/)
- [kind Local Registry — official](https://kind.sigs.k8s.io/docs/user/local-registry/)
- [Bitnami MongoDB Helm chart](https://github.com/bitnami/charts/tree/main/bitnami/mongodb)
- [Docker Best Practices for Python — TestDriven.io](https://testdriven.io/blog/docker-best-practices/)
- [Helm Chart Best Practices 2026](https://techstackguide.com/helm-charts-best-practices/)

---
*Feature research for: k8s-launchpad PRD-1 (local Kubernetes IDP foundation)*
*Researched: 2026-07-04*
