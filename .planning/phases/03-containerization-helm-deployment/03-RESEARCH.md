# Phase 3: Containerization + Helm Deployment - Research

**Researched:** 2026-07-05
**Domain:** Docker multi-stage builds (Flask/gunicorn), Helm chart authoring, in-cluster MongoDB (plain mongo:7 manifests), kind local-registry deploy loop
**Confidence:** HIGH

## Summary

Phase 3 turns the Phase 1 Flask app into a container image pushed to the Phase 2 local registry, and deploys it plus MongoDB to the kind cluster via a single hand-written Helm chart. Every external interface point was live-verified in this research session: the exact `MONGO_URI` auth pattern was tested against a real `mongo:7` container with the project's own PyMongo 4.13.2 (both STATE.md research flags are now **CLEARED** — see "Resolved Research Flags"), the installed Helm CLI was probed (v4.2.1 — charts must stay Helm-3-compatible `apiVersion: v2`, which Helm 4 fully supports), and the Helm 4 `helm create` scaffold was generated and inspected (verdict: hand-write the chart; the scaffold ships hpa/httproute/ingress/serviceaccount cruft that is explicitly out of scope).

The critical design decisions this research settles: (1) the working connection string is `mongodb://root:<pass>@<release>-mongodb:27017/fieldguide?authSource=admin` — without `?authSource=admin` PyMongo authenticates against `fieldguide` and fails with `AuthenticationFailed` (live-tested); the database name MUST stay in the URI path because Flask-PyMongo derives `mongo.db` from it (live-verified). (2) App exposure should be `kubectl port-forward`, not NodePort — NodePort on kind requires `extraPortMappings` in the kind config, which would force re-creating the Phase 2 live-verified cluster. (3) MongoDB ships as chart templates (Deployment + Service + PVC + Secret) using `mongo:7` — a plain Deployment-owned PVC (not StatefulSet volumeClaimTemplates) so `helm uninstall` removes everything cleanly, satisfying success criterion 4. (4) gunicorn runs exactly 1 worker (+ threads) — multiple workers silently break prometheus-flask-exporter metrics.

**Primary recommendation:** Multi-stage `python:3.11-slim` Dockerfile (numeric non-root UID, exec-form gunicorn CMD, `.dockerignore` excluding the 100MB+ Windows `.venv` sitting inside the build context), pushed as `localhost:5001/field-guide-api:dev`, deployed with `helm upgrade --install field-guide charts/field-guide-api` into the default namespace, verified via `helm lint` + port-forward smoke test against `/health` and `/entries`.

## User Constraints (locked decisions — from CLAUDE.md and roadmap; no CONTEXT.md exists)

### Locked Decisions (do NOT re-open)
- Python 3.11 + Flask; MongoDB local containerized via **plain mongo:7 manifests embedded in the chart** (NOT Bitnami — Broadcom paywall since Sep 2025)
- Docker; kind; local registry at `localhost:5001` (wired + live-verified in Phase 2)
- **Helm 3 chart compatibility** — chart is `apiVersion: v2`; installed CLI is Helm 4.2.1, which CLAUDE.md's own alternatives table blesses ("charts work unchanged"). No Helm-4-only chart features.
- **gunicorn from the first Dockerfile write** — Flask dev server never appears in any Dockerfile CMD
- `python:3.11-slim` base (not alpine — musl breaks PyMongo wheels)
- `imagePullPolicy: IfNotPresent` as the values.yaml default (HELM-04)
- values.yaml generic (image.*, service.*, resources, secrets, metrics.enabled, imagePullPolicy) so PRD-3 can template new apps
- Everything local and free; Windows host / Git Bash / WSL2 — all targets must work there
- Many small human-style commits (lowercase, conventional)

### Claude's Discretion
- Chart internal structure (template file layout, helper naming)
- App exposure method (success criteria allow "port-forward or NodePort") — research recommends port-forward
- Container port number, probe configuration, resource requests/limits
- Whether to add `build`/`load`/`deploy` Make targets now or defer wiring to Phase 4 (see Open Questions)

### Deferred Ideas (OUT OF SCOPE)
- Ingress/TLS, RBAC, NetworkPolicies, HPA, MongoDB replicaset/persistence hardening, ArgoCD, dashboards, Prometheus deployment (only the `/metrics` seam exists)

## Project Constraints (from CLAUDE.md)

- Tests required (pytest, 95% coverage target) — Phase 3 adds no Python code changes; `make test` must stay green (32 tests, 100% coverage currently)
- No hardcoded secrets — `.env` locally, Kubernetes Secrets in-cluster; never commit real credentials (`.gitignore` already covers `.env`, kubeconfig)
- Makefile: `SHELL := /bin/bash`, `export MSYS_NO_PATHCONV=1` already in place; use `$$` for shell vars in recipes
- Banned: Bitnami MongoDB chart, alpine Python base, Flask dev server in Docker, `registry:2`, Helm `--atomic` flag (removed from `helm install` in Helm 4 — see State of the Art), `git add -A`, CRLF in shell scripts (`.gitattributes` enforces LF for `*.yaml`/`*.sh` already)
- GSD workflow enforcement: all edits go through GSD commands

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Image build (Dockerfile) | Host OS (docker build) | Makefile target | Build context is `apps/field-guide-api/`; BuildKit on Docker 29.6.1 |
| Image distribution | Local registry (`localhost:5001`) | containerd mirror (Phase 2 wiring) | Push from host; nodes pull via `kind-registry:5000` mirror — the interface Phase 2 verified end-to-end |
| Chart packaging/render | Host OS (Helm 4.2.1 CLI) | — | `helm lint` / `helm upgrade --install`; chart stays apiVersion v2 |
| App runtime | Kubernetes Deployment (gunicorn pod) | — | 1 replica, 1 worker; K8s owns scaling/restart |
| MongoDB runtime | Kubernetes Deployment + PVC (mongo:7) | kind default StorageClass (`standard`, local-path) | Chart-owned resources so `helm uninstall` removes them |
| Config injection (non-secret) | ConfigMap → env | values.yaml | MONGO_DBNAME, FLASK_DEBUG |
| Credential injection | Kubernetes Secret → env | values.yaml (dev-only default) | MONGO_URI (contains password), mongo root user/pass |
| Local access | Host OS (`kubectl port-forward`) | — | NodePort would require kind config change + cluster re-create |
| Readiness signaling | App `/health` endpoint (already built) | K8s readinessProbe | 503 when Mongo down (fail-fast 2s server selection already coded) |

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| IMG-01 | Dockerfile builds a small working image (python:3.11-slim base, non-root user) | Multi-stage Dockerfile pattern below; numeric UID (`USER 10001`) so `runAsNonRoot` is kubelet-verifiable; `.dockerignore` mandatory (Windows `.venv` inside build context) |
| IMG-02 | Image serves via gunicorn (graceful SIGTERM), never Flask dev server | Exec-form CMD makes gunicorn PID 1; gunicorn handles TERM as graceful shutdown (default `graceful_timeout` 30s matches K8s grace period); `wsgi:app` entrypoint already exists |
| HELM-01 | Chart deploys app with Deployment, Service, ConfigMap, Secret template, values.yaml; `helm lint` passes | Hand-written chart structure below (helm create scaffold rejected — ships out-of-scope hpa/ingress/httproute); lint verified compatible with installed Helm 4.2.1 |
| HELM-02 | Deployed app reachable locally, returns data from `/health` and entries endpoints | `kubectl port-forward svc/<release>-field-guide-api 8080:80` recommended; NodePort ruled out (needs kind extraPortMappings → cluster re-create) |
| HELM-03 | MongoDB in-cluster via plain mongo:7 manifests embedded in chart | mongodb Deployment/Service/PVC/Secret templates below; MONGO_INITDB_ROOT_* behavior live-verified; readiness `mongosh ping` live-verified auth-free |
| HELM-04 | values.yaml generic (image.*, service.*, resources, secrets, metrics.enabled, imagePullPolicy: IfNotPresent) | Generic values.yaml schema below with `mongodb.enabled` toggle so PRD-3 can stamp DB-less apps from the same shape |
</phase_requirements>

## Resolved Research Flags (from STATE.md Blockers/Concerns)

### Flag 1: MONGO_URI with `?authSource=admin` — RESOLVED (live-tested this session)

Test rig: real `mongo:7` container (`MONGO_INITDB_ROOT_USERNAME=root`, `MONGO_INITDB_ROOT_PASSWORD=devpass`), queried with the project venv's PyMongo 4.13.2 — the exact driver the app ships.

| Test | URI | Result |
|------|-----|--------|
| ping + insert + find | `mongodb://root:devpass@host:27017/fieldguide?authSource=admin` | **PASS** — ping OK, CRUD on `fieldguide` OK, `get_default_database()` = `fieldguide` (Flask-PyMongo `mongo.db` resolves correctly) |
| same URI without `?authSource=admin` | `mongodb://root:devpass@host:27017/fieldguide` | **FAIL as predicted** — `OperationFailure: AuthenticationFailed` (PyMongo auths against `fieldguide`, root lives in `admin`) |
| unauthenticated ping | `mongodb://host:27017/` | **ALLOWED** — `ping` requires no auth → the chart's mongo readinessProbe (`mongosh --eval "db.adminCommand('ping')"`) works with auth enabled |
| wrong password ping | `mongodb://root:WRONG@host:27017/fieldguide?authSource=admin` | **REJECTED** (`OperationFailure`) → app `/health` correctly returns 503 on a misconfigured Secret |

**Canonical URI for the chart's Secret template** `[VERIFIED: live test, PyMongo 4.13.2 vs mongo:7]`:

```
mongodb://{{ .Values.mongodb.auth.username }}:{{ .Values.mongodb.auth.password }}@{{ include "field-guide-api.fullname" . }}-mongodb:27017/{{ .Values.mongodb.auth.database }}?authSource=admin
```

Two non-negotiable properties: the **database name must remain in the URI path** (Flask-PyMongo derives `mongo.db` from it — without it `mongo.db` is `None` and every entries route 500s), and **`?authSource=admin` must be appended** (root user is created in `admin` by the mongo image entrypoint).

### Flag 2: mongomock vs PyMongo 4.13.x — RESOLVED (empirically, Phase 1 + Phase 2 regression)

mongomock 4.3.0 + PyMongo 4.13.2 is the committed, working combination: the full 32-test suite passes with 100% coverage, re-verified live during 02-02 (`make test` — 32 passed, 0.93s). `requirements-dev.txt` already documents the 4.1.2 → 4.3.0 upgrade rationale (pkg_resources removal). No fallback to monkeypatch needed. Phase 3 adds **no Python code changes**, so the test suite is a pure regression gate (`make test` must stay green).

## Standard Stack

### Core (no new packages — Phase 3 consumes what Phases 1–2 built)

| Component | Version | Purpose | Status |
|-----------|---------|---------|--------|
| python:3.11-slim | latest tag on Docker Hub | Image base (builder + runtime stages) | [VERIFIED: locked in CLAUDE.md; official Docker library image] |
| gunicorn | 26.0.0 (already in requirements.txt) | WSGI server, PID 1 in container | [VERIFIED: requirements.txt pinned; installed in project venv] |
| mongo:7 | 7.x (pulled to host this session) | In-cluster MongoDB | [VERIFIED: `docker pull mongo:7` succeeded; auth behavior live-tested] |
| Helm | 4.2.1 (installed CLI) | lint / install / uninstall | [VERIFIED: `helm version` on this machine] |
| kind | v0.32.0 | Cluster (Phase 2, currently torn down) | [VERIFIED: `kind version`] |
| kubectl | v1.36.1 | port-forward, verification | [VERIFIED: `kubectl version --client`] |
| Docker | 29.6.1 (server) | build + push | [VERIFIED: `docker version`] |

### Supporting

| Item | Purpose | Notes |
|------|---------|-------|
| `.dockerignore` (NEW file) | Exclude `.venv/`, `tests/`, `.pytest_cache/`, `__pycache__/`, `.coverage`, `.env` from build context | **Critical** — a full Windows venv lives at `apps/field-guide-api/.venv/` inside the build context; without .dockerignore every build ships 100MB+ of useless Windows binaries to the daemon |
| kind default StorageClass `standard` | Backs the MongoDB PVC | rancher.io/local-path provisioner, `WaitForFirstConsumer`, reclaim `Delete` — PVC stays Pending until the mongo pod schedules; this is normal, not an error [CITED: kind PVC community docs + kubernetes.io storage-classes] |
| `kind load docker-image mongo:7` (optional) | Pre-seed mongo:7 into the node, bypassing Docker Hub at deploy time | Docker Hub returned transient 525 errors twice this session; preloading makes `helm install` deterministic offline |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-written chart | `helm create` scaffold | Helm 4 scaffold inspected this session: ships hpa.yaml, httproute.yaml, ingress.yaml, serviceaccount.yaml, tests/ — all explicitly out of scope; stripping is more work than writing ~8 small templates. Reuse only its `_helpers.tpl` naming conventions |
| `kubectl port-forward` | NodePort + kind `extraPortMappings` | extraPortMappings live in kind-config.yaml → cluster must be re-created, invalidating Phase 2's live verification; port-forward needs zero cluster changes and works identically on Docker Desktop/Windows |
| Deployment + chart-owned PVC for mongo | StatefulSet | StatefulSet `volumeClaimTemplates` PVCs are NOT deleted by `helm uninstall` → breaks success criterion 4 ("removes all resources cleanly"); single-replica mongo has no need for stable network identity |
| `docker push localhost:5001/...` (make load) | `kind load docker-image` for the app image | `kind load` bypasses the registry — it works, but never exercises the Phase 2 registry wiring that exists precisely for this loop, and PRD-2 (ArgoCD) will need a real registry anyway |
| 1 gunicorn worker + gthread threads | Multiple workers | >1 worker breaks prometheus-flask-exporter (per-process registries return inconsistent scrapes) unless multiprocess mode + PROMETHEUS_MULTIPROC_DIR is configured — needless complexity; K8s replicas are the scaling axis (CLAUDE.md: "1 worker per pod") |

## Package Legitimacy Audit

Phase 3 installs **no** npm/PyPI/Cargo packages (requirements.txt and requirements-dev.txt are unchanged). Consumed artifacts are Docker images only:

| Image | Registry | Official | Verified How | Disposition |
|-------|----------|----------|--------------|-------------|
| `python:3.11-slim` | Docker Hub (library/python) | Yes — Docker official image | Locked in CLAUDE.md; industry-standard base | Approved |
| `mongo:7` | Docker Hub (library/mongo) | Yes — Docker official image | Pulled and run live this session; auth behavior tested | Approved |
| `registry:3`, `kindest/node:v1.36.1` | Docker Hub | Yes | Already audited + live-verified in Phase 2 | Approved (unchanged) |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none
slopcheck not applicable (no language-registry packages; Docker images out of its scope).

## Architecture Patterns

### System Architecture Diagram

```
Developer host (Windows / Git Bash)                      kind cluster (Docker Desktop)
────────────────────────────────────                     ─────────────────────────────────────────
docker build apps/field-guide-api                        default namespace
  └─> localhost:5001/field-guide-api:dev                 ┌────────────────────────────────────┐
docker push localhost:5001/field-guide-api:dev ──────┐   │ Deployment: field-guide-api        │
                                                     │   │  pod: gunicorn (1 worker, :8000)   │
        kind-registry container (127.0.0.1:5001) <───┘   │  env  <── Secret (MONGO_URI)       │
                │ containerd mirror                      │  env  <── ConfigMap (MONGO_DBNAME) │
                └── kind-registry:5000 ──── image pull ─>│  readiness: GET /health (503⇢gate) │
                                                         │  liveness:  tcpSocket 8000         │
helm upgrade --install field-guide charts/field-guide-api└──────────┬─────────────────────────┘
  │ renders: app Deployment/Service/ConfigMap/Secret                │ Service: ClusterIP :80 → :8000
  │          mongodb Deployment/Service/PVC/Secret                  │
  │                                                       ┌─────────▼──────────────────────────┐
kubectl port-forward svc/...-field-guide-api 8080:80      │ mongo URI: ...-mongodb:27017       │
  │                                                       │ Deployment: mongodb (mongo:7)      │
curl localhost:8080/health   ──> 200 {"mongo":"up"}       │  env <── Secret (MONGO_INITDB_*)   │
curl localhost:8080/entries  ──> []                       │  PVC (standard SC, local-path)     │
                                                          │  readiness: mongosh ping (no auth) │
helm uninstall field-guide  ──> removes ALL of the above  │ Service: ClusterIP :27017          │
(PVC included — chart-owned, not volumeClaimTemplate)     └────────────────────────────────────┘
```

Startup ordering needs no init containers: the app pod starts, `/health` returns 503 (server selection bounded at 2000ms — already coded in `create_app`), readiness gates it out of the Service; once mongo passes its probe, the next app readiness check flips to 200. The system self-converges.

### Recommended Project Structure

```
apps/field-guide-api/
├── Dockerfile                    # NEW — multi-stage, non-root, gunicorn CMD
├── .dockerignore                 # NEW — .venv/, tests/, caches, .env
└── (app/, wsgi.py, requirements.txt — unchanged)

charts/field-guide-api/           # replaces .gitkeep
├── Chart.yaml                    # apiVersion: v2, version 0.1.0
├── values.yaml                   # generic schema (HELM-04)
├── .helmignore
└── templates/
    ├── _helpers.tpl              # name/fullname/labels helpers (standard pattern)
    ├── NOTES.txt                 # port-forward + curl instructions
    ├── deployment.yaml           # app
    ├── service.yaml              # app ClusterIP
    ├── configmap.yaml            # MONGO_DBNAME, FLASK_DEBUG
    ├── secret.yaml               # MONGO_URI (built from mongodb.auth values)
    └── mongodb/
        ├── deployment.yaml       # mongo:7, gated on .Values.mongodb.enabled
        ├── service.yaml          # ClusterIP :27017
        ├── pvc.yaml              # default StorageClass
        └── secret.yaml           # MONGO_INITDB_ROOT_USERNAME/PASSWORD
```

### Pattern 1: Multi-stage Dockerfile (IMG-01, IMG-02)

**What:** Builder installs wheels; runtime copies site-packages; numeric non-root UID; exec-form gunicorn CMD.
**When to use:** This is THE Dockerfile. Follows CLAUDE.md's embedded pattern.

```dockerfile
# Source: CLAUDE.md researched stack pattern + docs.gunicorn.org/en/stable/signals.html
# --- Builder stage ---
FROM python:3.11-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Runtime stage ---
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=builder /install /usr/local
COPY app/ ./app/
COPY wsgi.py .
# Numeric UID so Kubernetes runAsNonRoot is verifiable by the kubelet
RUN groupadd -r -g 10001 app && useradd -r -u 10001 -g app app
USER 10001
EXPOSE 8000
# Exec form (JSON array) — gunicorn becomes PID 1 and receives SIGTERM directly.
# gunicorn treats TERM as graceful shutdown (default graceful_timeout 30s,
# matching Kubernetes' default terminationGracePeriodSeconds 30).
CMD ["gunicorn", "--bind", "0.0.0.0:8000", \
     "--workers", "1", "--threads", "4", \
     "--access-logfile", "-", "--error-logfile", "-", \
     "wsgi:app"]
```

Key choices, each load-bearing:
- **Exec-form CMD** — shell form would make `/bin/sh` PID 1 and swallow SIGTERM; pods would hit the 30s force-kill on every rollout `[CITED: docs.gunicorn.org/en/stable/signals.html — "TERM: Graceful shutdown"]`
- **`--workers 1 --threads 4`** — one process keeps prometheus-flask-exporter correct (no multiprocess registry); threads keep `/health` responsive while a request holds the worker
- **`USER 10001` numeric** — a named `USER app` cannot be validated by `runAsNonRoot: true` in the pod securityContext (kubelet needs a numeric UID) `[ASSUMED — standard Kubernetes behavior, K8s docs pod-security]`
- **`--access-logfile -`** — logs to stdout for `kubectl logs` (and PRD-4 Loki later)

### Pattern 2: `.dockerignore` (mandatory, not optional)

```
.venv/
.pytest_cache/
__pycache__/
**/__pycache__/
*.pyc
.coverage
.env
tests/
```

`apps/field-guide-api/.venv/` is a fully-populated Windows venv (site-packages with .pyd binaries) sitting inside the build context. Without this file, every `docker build` transfers it to the daemon and any broad `COPY . .` would bake Windows binaries into a Linux image. The Dockerfile above also defends by COPYing only `app/` and `wsgi.py` explicitly.

### Pattern 3: Generic values.yaml (HELM-04 / PRD-3 seam)

```yaml
# Source: HELM-04 requirement schema + standard Helm conventions
replicaCount: 1

image:
  repository: localhost:5001/field-guide-api
  tag: dev
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 80
  targetPort: 8000

resources:
  requests: { cpu: 50m, memory: 128Mi }
  limits: { cpu: 250m, memory: 256Mi }

metrics:
  enabled: true            # PRD-4 scrape seam (annotations / future ServiceMonitor)

config:
  mongoDbName: fieldguide
  flaskDebug: ""           # empty = disabled (app's _env_flag logic)

# Secret-backed values. LOCAL DEV DEFAULTS ONLY — override with --set for anything real.
mongodb:
  enabled: true            # PRD-3: DB-less apps set false; app Secret then uses externalUri
  image: mongo:7
  auth:
    username: root
    password: fieldguide-dev-password   # local kind only; never a real credential
    database: fieldguide
  persistence:
    enabled: true
    size: 1Gi
    storageClass: ""       # empty = cluster default ("standard" on kind)
```

`mongodb.enabled` + generic `image.*/service.*/resources/metrics.enabled` is the exact seam PRD-3 needs to stamp new apps. The dev-default password is acceptable under the project's security constraints (local-only cluster, loopback-only registry, never a real credential) but the values.yaml comment must say so explicitly.

### Pattern 4: Secret template building MONGO_URI (live-verified URI shape)

```yaml
# templates/secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: {{ include "field-guide-api.fullname" . }}
  labels: {{- include "field-guide-api.labels" . | nindent 4 }}
type: Opaque
stringData:
  MONGO_URI: "mongodb://{{ .Values.mongodb.auth.username }}:{{ .Values.mongodb.auth.password }}@{{ include "field-guide-api.fullname" . }}-mongodb:27017/{{ .Values.mongodb.auth.database }}?authSource=admin"
```

`stringData` (not `data`) avoids error-prone manual base64. The hostname must match the mongodb Service name exactly — define both from the same helper.

### Pattern 5: Probes (app + mongo)

```yaml
# App container (templates/deployment.yaml)
readinessProbe:
  httpGet: { path: /health, port: 8000 }
  initialDelaySeconds: 5
  periodSeconds: 5
livenessProbe:
  tcpSocket: { port: 8000 }
  initialDelaySeconds: 10
  periodSeconds: 10
```

**Do NOT use `/health` as the liveness probe.** `/health` couples to MongoDB (returns 503 when Mongo is down); as a liveness probe it would restart healthy app pods during any Mongo outage, masking the real failure. Liveness = "is gunicorn accepting connections" (tcpSocket); readiness = "can I serve traffic" (`/health`). This honors API-05's intent (liveness = process up, readiness = Mongo connectivity) given the single implemented endpoint.

```yaml
# Mongo container (templates/mongodb/deployment.yaml)
readinessProbe:
  exec:
    command: ["mongosh", "--quiet", "--eval", "db.adminCommand('ping')"]
  initialDelaySeconds: 10
  periodSeconds: 10
```

Live-verified: `ping` requires no authentication, so this probe works with `--auth` enabled (mongo:7 bundles `mongosh`).

### Pattern 6: Deploy / verify command sequence (planner's verification steps)

```bash
# Prereq: cluster is currently DOWN — run make cluster-up first (idempotent, self-verifying)
make cluster-up

# Build + push (the Phase 2-verified registry loop)
docker build -t localhost:5001/field-guide-api:dev apps/field-guide-api
docker push localhost:5001/field-guide-api:dev

# Optional: pre-seed mongo:7 into the node (dodges Docker Hub flakiness seen this session)
kind load docker-image mongo:7

# Lint gate (HELM-01)
helm lint charts/field-guide-api

# Deploy — upgrade --install is idempotent; NO --atomic (removed in Helm 4 install)
helm upgrade --install field-guide charts/field-guide-api --wait --timeout 180s

# Smoke test (HELM-02) — run port-forward in background, curl, kill
kubectl port-forward svc/field-guide-field-guide-api 8080:80 &
curl -fsS localhost:8080/health          # expect 200 {"status":"ok","mongo":"up"}
curl -fsS localhost:8080/entries         # expect [] (or POST one, GET it back)
curl -fsS localhost:8080/metrics | head  # metrics seam alive

# Clean removal (success criterion 4)
helm uninstall field-guide
kubectl get pvc,deploy,svc,secret,configmap -l app.kubernetes.io/instance=field-guide  # expect empty
```

Note the release-name/fullname interaction: with release `field-guide` and chart `field-guide-api`, the standard fullname helper produces `field-guide-field-guide-api`. If that reads badly, either name the release `field-guide-api` (fullname collapses to `field-guide-api` when release name contains chart name — standard helper behavior) or set `fullnameOverride`. Planner's choice; be consistent in NOTES.txt.

### Anti-Patterns to Avoid

- **`helm create` scaffold as-is:** ships hpa/httproute/ingress/serviceaccount/tests — all out of scope; hand-write instead
- **StatefulSet for mongo:** its PVCs survive `helm uninstall` → fails success criterion 4
- **`--atomic` on `helm install`:** flag binding removed in Helm 4 — the command errors (deprecated-but-working only on `upgrade`)
- **`/health` as livenessProbe:** restart-loops the app during Mongo outages
- **Shell-form CMD / `python -m flask run`:** breaks SIGTERM handling / violates IMG-02
- **Multiple gunicorn workers:** silently corrupts `/metrics` (per-process registries)
- **`data:` with hand-base64'd secrets:** use `stringData:`
- **Baking MONGO_URI into the image or ConfigMap:** it contains the password — Secret only
- **`imagePullPolicy: Always` as the values default:** violates HELM-04's locked `IfNotPresent`; also breaks offline deploys of preloaded images

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WSGI serving + signal handling | Custom Flask runner / dev server | gunicorn 26.0.0 (already pinned) | TERM/QUIT/HUP semantics, worker lifecycle, K8s-grade graceful shutdown |
| Mongo auth bootstrap | Custom init scripts/Jobs creating users | mongo:7 image `MONGO_INITDB_ROOT_*` env (live-verified) | Image entrypoint creates root in `admin` and enables `--auth` atomically on first init |
| Secret base64 encoding | Manual `base64` in templates | `stringData:` field | API server encodes; eliminates whitespace/newline bugs |
| Chart label plumbing | Ad-hoc labels per template | Standard `_helpers.tpl` (name/fullname/labels/selectorLabels) | `app.kubernetes.io/*` conventions; selector immutability safety; PRD-3 templating depends on this discipline |
| Readiness gating / startup ordering | initContainers with `until nc` loops | readinessProbe + bounded serverSelectionTimeoutMS (already coded) | K8s-native convergence; app already fails fast in 2s |
| Metrics endpoint | Custom /metrics route | prometheus-flask-exporter (already wired) | Auto-instrumented; only constraint is workers=1 |

**Key insight:** Phase 3 writes zero new Python. Every hard problem (auth bootstrap, graceful shutdown, secret encoding, ordering) has a platform-native answer; the phase is pure packaging.

## Common Pitfalls

### Pitfall 1: Missing `?authSource=admin` in MONGO_URI
**What goes wrong:** App deploys, `/health` returns 503 forever, entries routes fail with `AuthenticationFailed`.
**Why it happens:** PyMongo defaults authSource to the URI-path database (`fieldguide`); mongo:7's root user exists only in `admin`. Live-reproduced this session.
**How to avoid:** Use the canonical URI from Pattern 4 verbatim.
**Warning signs:** `kubectl logs` show `OperationFailure: Authentication failed`; readiness never passes.

### Pitfall 2: Windows `.venv` in the Docker build context
**What goes wrong:** Builds take minutes transferring context; broad COPY bakes Windows `.pyd` binaries into a Linux image.
**Why it happens:** `apps/field-guide-api/.venv/` exists on disk (gitignored, but Docker doesn't read .gitignore).
**How to avoid:** `.dockerignore` (Pattern 2) committed in the same task as the Dockerfile; COPY only `app/` and `wsgi.py`.
**Warning signs:** "Sending build context" shows tens/hundreds of MB.

### Pitfall 3: Image rebuild not picked up (`IfNotPresent` + same tag)
**What goes wrong:** Fix a bug, rebuild, push, `kubectl rollout restart` — pod still runs the old code.
**Why it happens:** containerd already has `localhost:5001/field-guide-api:dev`; `IfNotPresent` never re-pulls an existing tag.
**How to avoid:** During iteration either bump the tag (`--set image.tag=dev2` / git-sha tags — Phase 4 can wire `git rev-parse --short HEAD`) or one-off `kubectl set image`. Do NOT change the values default (HELM-04 locks IfNotPresent).
**Warning signs:** New code visibly absent after a "successful" rollout.

### Pitfall 4: MONGO_INITDB_* only applies on first init (PVC persistence)
**What goes wrong:** Change `mongodb.auth.password` in values, `helm upgrade` — auth still uses the OLD password; app gets AuthenticationFailed.
**Why it happens:** The mongo image entrypoint creates the root user only when `/data/db` is empty; with a persistent PVC, credentials are frozen at first boot.
**How to avoid:** Treat credentials as fixed for a PVC's lifetime. To rotate locally: `helm uninstall` (removes chart PVC) then reinstall, or delete the PVC explicitly.
**Warning signs:** Auth failures immediately after a credentials-only upgrade.

### Pitfall 5: `--atomic` errors on `helm install` under Helm 4
**What goes wrong:** `helm install --atomic` fails — the flag binding was removed from `install` (kept deprecated only on `upgrade`).
**How to avoid:** Use `--rollback-on-failure` if wanted, or plain `upgrade --install --wait`. CLAUDE.md already bans `--atomic` in the Makefile.
**Warning signs:** `unknown flag: --atomic` `[CITED: github.com/helm/helm/issues/31900]`

### Pitfall 6: Docker Hub transient 525 errors → mongo ImagePullBackOff
**What goes wrong:** `helm install` succeeds but the mongo pod sits in ImagePullBackOff with an oauth-token 525 error.
**Why it happens:** Docker Hub auth flakiness — observed twice live this session from this machine. The mongo image is pulled from Docker Hub directly (not the local registry).
**How to avoid:** `kind load docker-image mongo:7` before install (image already on host), or just wait — kubelet backoff retries and self-heals.
**Warning signs:** `failed to authorize: ... 525` in pod events.

### Pitfall 7: MongoDB PVC Pending "forever" (WaitForFirstConsumer)
**What goes wrong:** `kubectl get pvc` shows Pending; looks like a storage failure.
**Why it happens:** kind's default `standard` StorageClass binds only when a consuming pod schedules — Pending-before-pod is normal.
**How to avoid:** Don't gate verification on PVC status alone; check pod status. Leave `storageClass: ""` (cluster default).
**Warning signs:** Pending PVC + no scheduled pod = fine; Pending PVC + Running pod stuck ContainerCreating = investigate.

### Pitfall 8: Cluster is currently DOWN
**What goes wrong:** Any `helm`/`kubectl` verification step fails with connection refused.
**Why it happens:** Phase 2 verification ended with `make cluster-down` — live-probed this session: no kind clusters, no kind-registry container.
**How to avoid:** Plans must start live verification with `make cluster-up` (idempotent, self-verifying, ~2 min). Use `--context kind-kind` for kubectl consistency with cluster-setup.sh.
**Warning signs:** `The connection to the server ... was refused`.

### Pitfall 9: helm lint/template pass but install fails on name mismatches
**What goes wrong:** App can't resolve mongo because the Service name rendered differently from the hostname baked into the Secret's MONGO_URI.
**Why it happens:** Hand-written charts drift when the mongodb Service name and the URI host are written independently.
**How to avoid:** Single source of truth — one helper (`field-guide-api.mongodb.fullname` or `printf "%s-mongodb"` on the app fullname) used by BOTH the Service metadata.name and the Secret URI. Verify with `helm template | grep -A2 mongodb` before install.
**Warning signs:** `/health` 503 with DNS resolution errors (`ServerSelectionTimeoutError ... Name or service not known`) in app logs.

## Code Examples

Verified command set for the full loop (Pattern 6 above) plus the two templates most likely to be gotten wrong (Patterns 1 and 4). Additional example — app Deployment env wiring:

```yaml
# templates/deployment.yaml (app) — env injection
env:
  - name: MONGO_URI
    valueFrom:
      secretKeyRef:
        name: {{ include "field-guide-api.fullname" . }}
        key: MONGO_URI
  - name: MONGO_DBNAME
    valueFrom:
      configMapKeyRef:
        name: {{ include "field-guide-api.fullname" . }}
        key: MONGO_DBNAME
  - name: FLASK_DEBUG
    valueFrom:
      configMapKeyRef:
        name: {{ include "field-guide-api.fullname" . }}
        key: FLASK_DEBUG
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  allowPrivilegeEscalation: false
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Helm 3 CLI (`--atomic`) | Helm 4.2.1 installed; `--rollback-on-failure`; `--atomic` removed from `install` | Helm 4 GA (Nov 2025) | Never use `--atomic` in scripts; charts stay `apiVersion: v2` (fully compatible) |
| `--wait` polling readiness | Helm 4 `--wait` uses kstatus watcher; failed resources exit immediately instead of waiting for timeout | Helm 4 | Faster, clearer failures on `helm upgrade --install --wait` `[CITED: helm.sh Helm 4 overview + community migration guides]` |
| Bitnami mongodb chart | Plain mongo:7 manifests in own chart | Sep 2025 (Broadcom paywall) | Already locked; this research confirms the manifests are small (4 templates) |
| `helm create` minimal scaffold | Helm 4 scaffold includes httproute.yaml (Gateway API) | Helm 4 | More cruft to delete — reinforces hand-writing the chart |

**Deprecated/outdated:** `--atomic` (install: removed; upgrade: deprecated) — use `--rollback-on-failure`; Bitnami MongoDB chart — paywalled.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Named-user `USER app` is not verifiable by `runAsNonRoot`; numeric UID required | Pattern 1 | Low — numeric UID works either way; worst case the securityContext is redundant |
| A2 | gunicorn default `graceful_timeout` (30s) aligns with K8s default grace period; no tuning needed for this app | Pattern 1 | Low — requests are sub-second; even a mismatch only delays pod termination |
| A3 | `mongo:7` image entrypoint enables `--auth` when MONGO_INITDB_ROOT_* set (behavior confirmed live; the *mechanism* description is from Docker Hub docs knowledge) | Resolved Flags | None practically — behavior was directly observed |
| A4 | kind default StorageClass is named `standard` with local-path provisioner | Supporting stack | Low — chart uses `storageClass: ""` (cluster default), so the name never appears in templates |
| A5 | Helm 4 `--wait` kstatus behavior (from migration guides, not tested live this session) | State of the Art | Low — worst case `--wait` behaves like Helm 3; success criteria don't depend on it |

## Open Questions

1. **Add `build`/`load`/`deploy` Make targets in Phase 3 or defer to Phase 4?**
   - What we know: MAKE-01/02 are Phase 4 requirements, but the existing Makefile comment reserves "Phase 3+: build, load, deploy", and Phase 3 verification will run these commands repeatedly.
   - Recommendation: Add minimal `build`/`load`/`deploy` (and `undeploy`) targets in Phase 3 — they're one-liners wrapping Pattern 6 commands; Phase 4 then only polishes + documents. Planner's discretion; either satisfies Phase 3 success criteria.

2. **Helm release name: `field-guide` vs `field-guide-api`?**
   - What we know: standard fullname helper collapses to `field-guide-api` when the release name equals/contains the chart name; otherwise resources render as `field-guide-field-guide-api`.
   - Recommendation: release name `field-guide-api` for clean resource names (`field-guide-api`, `field-guide-api-mongodb`). Cosmetic; planner decides once and stays consistent.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker daemon | build/push | ✓ | 29.6.1 (server) | — |
| Helm CLI | lint/install | ✓ | 4.2.1 (charts stay v2/Helm-3-compatible) | — |
| kind | cluster | ✓ | v0.32.0 | — |
| kubectl | port-forward/verify | ✓ | v1.36.1 | — |
| kind cluster (running) | live verification | ✗ (torn down after Phase 2) | — | `make cluster-up` (idempotent, verified) |
| kind-registry container | image push | ✗ (removed with cluster) | — | recreated by `make cluster-up` |
| mongo:7 image | in-cluster DB | ✓ (pulled to host this session) | 7.x | `kind load docker-image mongo:7` dodges Hub flakiness |
| python:3.11-slim image | Dockerfile base | not pulled yet | latest | pulled automatically at build (Hub 525s may need a retry) |

**Missing dependencies with no fallback:** none — everything missing is restored by the idempotent `make cluster-up`.

## Security Domain

**security_enforcement:** not set in config.json → treated as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Yes | MongoDB `--auth` via MONGO_INITDB_ROOT_* (mongo image native); root user scoped to a single-tenant local cluster |
| V3 Session Management | No | Stateless REST API |
| V4 Access Control | Partially | ClusterIP services only (no external exposure); access via port-forward; registry stays loopback-bound (Phase 2 verified) |
| V5 Input Validation | Yes (already built) | entries.py validates types, dict-only queries (T-02-03) — unchanged this phase |
| V6 Cryptography | No hand-rolling | K8s Secret (base64 ≠ encryption — acceptable for local kind; documented) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Real credentials committed via values.yaml | Information Disclosure | Only the clearly-labeled dev default (`fieldguide-dev-password`) lives in values.yaml; anything real via `--set`/`-f` override; `.env` already gitignored |
| Container running as root | Elevation of Privilege | `USER 10001` in Dockerfile + `runAsNonRoot: true` + `allowPrivilegeEscalation: false` in pod securityContext (IMG-01) |
| Flask debug mode in container | Information Disclosure / RCE | `FLASK_DEBUG=""` in ConfigMap; app's `_env_flag` treats empty as disabled (already hardened) |
| MONGO_URI (with password) in ConfigMap or image layers | Information Disclosure | URI lives ONLY in the Secret template; never in ConfigMap, Dockerfile ENV, or logs |
| Mongo exposed outside cluster | Elevation of Privilege | ClusterIP only; no NodePort/hostPort on mongo |
| Windows venv binaries baked into image | Tampering/supply chain | `.dockerignore` + explicit COPY allowlist |

## Sources

### Primary (HIGH confidence)
- **Live tests this session** — mongo:7 + PyMongo 4.13.2 auth matrix (4 cases), `helm version`/`docker version`/`kind version`/`kubectl version` probes, `helm create` Helm 4 scaffold generation, cluster/registry state probe, mongo:7 pull
- Project codebase — `app/` factory, `wsgi.py`, `conftest.py` (mongomock strategy), `requirements*.txt` pins, `scripts/cluster-setup.sh` (registry wiring, `--context kind-kind` convention), Makefile, `.gitignore`/`.gitattributes`
- `.planning/phases/02-cluster-infrastructure/02-RESEARCH.md` + `02-02-SUMMARY.md` — registry loop live-verified end-to-end
- CLAUDE.md embedded stack research (Flask/gunicorn/mongo versions, Docker/Helm patterns — already HIGH-confidence sourced)

### Secondary (MEDIUM confidence)
- [helm/helm issue #31900](https://github.com/helm/helm/issues/31900) — `--atomic` removed from `helm install` in Helm 4 (verified via WebSearch cross-reference with migration guides)
- [Helm 4 overview](https://helm.sh/docs/overview/) + community migration guides — v2 chart compatibility, `--wait` kstatus behavior
- [kind PVC / local-path-provisioner](https://mauilion.dev/posts/kind-pvc/) + [kubernetes.io storage classes](https://kubernetes.io/docs/concepts/storage/storage-classes/) — `standard` default SC, WaitForFirstConsumer
- [gunicorn signals](https://docs.gunicorn.org/en/stable/signals.html) — TERM = graceful shutdown (training knowledge consistent with docs; not re-fetched this session)

### Tertiary (LOW confidence)
- prometheus-flask-exporter multiprocess limitation with >1 gunicorn worker (training knowledge; mitigated by prescribing workers=1, which is independently mandated by CLAUDE.md)

## Metadata

**Confidence breakdown:**
- MONGO_URI / auth pattern: HIGH — live-tested with the exact driver version against the exact image
- Docker image pattern: HIGH — follows CLAUDE.md's researched pattern; environment probed
- Helm chart structure: HIGH — Helm 4.2.1 probed live, scaffold inspected, compatibility cross-verified
- Pitfalls: HIGH — 1, 2, 6, 8 directly observed this session; others from official sources
- Probe strategy / securityContext details: MEDIUM — standard K8s practice, not exercised live yet (verified at execution)

**Research date:** 2026-07-05
**Valid until:** 2026-08-05 (Docker/Helm/kind all stable; mongo:7 is an LTS-track tag)
