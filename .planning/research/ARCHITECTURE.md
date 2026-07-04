# Architecture Research

**Domain:** Local Kubernetes Internal Developer Platform — foundation layer (PRD-1)
**Researched:** 2026-07-04
**Confidence:** HIGH (verified against kind official docs, Helm Context7, Flask Context7)

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         DEV MACHINE (host)                           │
│                                                                       │
│  ┌──────────────┐   docker build    ┌───────────────────────────┐   │
│  │ Flask source │ ───────────────►  │    Docker daemon          │   │
│  │ apps/        │                   │    (image store)          │   │
│  └──────────────┘                   └────────────┬──────────────┘   │
│                                                  │ docker push       │
│  ┌──────────────┐   helm install   ┌─────────────▼──────────────┐   │
│  │  Helm chart  │ ──────────────►  │  Local Registry container  │   │
│  │  charts/     │                  │  registry:2 @ :5001        │   │
│  └──────────────┘                  └─────────────┬──────────────┘   │
│                                                  │ Docker network    │
│  ┌──────────────┐   kind create    ┌─────────────▼──────────────┐   │
│  │  infra/kind/ │ ──────────────►  │     kind cluster node      │   │
│  │  cluster.yaml│                  │  (Docker container)        │   │
│  └──────────────┘                  │  containerd pulls from     │   │
│                                    │  localhost:5001 via network │   │
│                                    └──────────┬─────────────────┘   │
└───────────────────────────────────────────────┼─────────────────────┘
                                                │
                              ┌─────────────────▼──────────────────┐
                              │        KIND CLUSTER                  │
                              │  ┌────────────────────────────┐     │
                              │  │   field-guide-api pod       │     │
                              │  │   Flask app :5000           │ ◄── curl
                              │  └──────────────┬─────────────┘     │
                              │                 │ mongodb://          │
                              │                 │ mongodb-svc:27017   │
                              │  ┌──────────────▼─────────────┐     │
                              │  │   MongoDB pod               │     │
                              │  │   Helm dependency :27017    │     │
                              │  └────────────────────────────┘     │
                              └────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `apps/field-guide-api/` | Flask REST API — CRUD for DevOps entries | App factory pattern, blueprints, env-based config |
| `charts/field-guide-api/` | Helm chart packaging the app for K8s | Deployment + Service + ConfigMap + Secret template |
| `infra/kind/` | Cluster definition + registry bootstrap | `cluster.yaml` + `scripts/kind-with-registry.sh` |
| Local registry container | Layer-efficient image store accessible to kind nodes | `registry:2` Docker container on host, port 5001 |
| kind node (containerd) | Pull images from local registry, run pods | Configured via `hosts.toml` to resolve `localhost:5001` |
| MongoDB pod | Persistent data store for entries | Helm dependency (Bitnami MongoDB chart) or standalone manifest |
| `Makefile` | Developer interface — orchestrates all above | `.PHONY` targets with explicit dependency chains |

## Recommended Project Structure

```
k8s-launchpad/
├── apps/
│   └── field-guide-api/
│       ├── src/
│       │   ├── __init__.py        # create_app() factory — entry point
│       │   ├── config.py          # Config classes reading from env vars
│       │   ├── extensions.py      # PyMongo (and future) extension init
│       │   └── blueprints/
│       │       ├── entries.py     # GET /entries, GET /entries/<id>, POST /entries
│       │       └── health.py      # GET /health, GET /metrics
│       ├── tests/
│       │   ├── conftest.py        # create_app(test_config=...) fixture
│       │   └── test_entries.py    # unit tests for blueprint routes
│       ├── Dockerfile
│       └── requirements.txt
├── charts/
│   └── field-guide-api/
│       ├── Chart.yaml             # name, version, appVersion; lists MongoDB dep
│       ├── values.yaml            # generic seam — every configurable knob here
│       ├── charts/                # vendored Helm dependencies (mongodb)
│       └── templates/
│           ├── deployment.yaml
│           ├── service.yaml
│           ├── configmap.yaml
│           └── secret.yaml        # template only — real values from values.yaml
├── infra/
│   ├── kind/
│   │   └── cluster.yaml           # kind Cluster config with containerd patch
│   ├── argocd/                    # empty — reserved for PRD-2
│   └── observability/             # empty — reserved for PRD-4
├── scripts/
│   └── kind-with-registry.sh      # idempotent: create registry + cluster + connect
├── docs/
│   └── local-setup.md             # clone → make cluster-up → make deploy → curl
├── Makefile                        # primary developer interface
├── .env.example
├── .gitignore
└── README.md
```

### Structure Rationale

- **`apps/` prefix:** Mirrors the multi-app IDP pattern; PRD-3 will add `apps/platform-dashboard/`. Signals each directory is a deployable unit.
- **`src/` inside the app:** Separates importable Python package from Docker/test artifacts; `pytest` discovers tests cleanly without importing Docker build context.
- **`blueprints/` not `routes/`:** Flask naming convention; keeps `entries` and `health` concerns fully isolated — health blueprint has zero MongoDB dependency.
- **`infra/` subdirectories reserved:** `argocd/` and `observability/` exist as empty dirs (with `.gitkeep`) so directory layout signals future intent to reviewers.
- **`scripts/` for shell, `Makefile` for targets:** Shell handles multi-step stateful operations (registry bootstrap); Makefile provides the CLI contract. Separation keeps Makefile readable.

## Architectural Patterns

### Pattern 1: App Factory (Flask)

**What:** `create_app()` function instantiates and configures the Flask app. Extensions and blueprints are registered inside the factory, never at module level.

**When to use:** Always with Flask. Required for testing (create multiple app instances with different configs), required for the extensions (PyMongo) to work correctly without circular imports.

**Trade-offs:** Slightly more setup than a flat `app.py`; pays off immediately when writing pytest fixtures.

**Example:**
```python
# src/__init__.py
from flask import Flask
from .extensions import mongo
from .blueprints.entries import entries_bp
from .blueprints.health import health_bp

def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_object("src.config.Config")
    if test_config:
        app.config.update(test_config)

    mongo.init_app(app)

    app.register_blueprint(entries_bp, url_prefix="/api")
    app.register_blueprint(health_bp)

    return app

# src/config.py
import os

class Config:
    MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/fieldguide")
    LOG_LEVEL  = os.environ.get("LOG_LEVEL", "INFO")
```

### Pattern 2: Local Registry (preferred over `kind load`)

**What:** A `registry:2` Docker container runs on the host. kind nodes are configured via `hosts.toml` to resolve `localhost:5001` through the Docker network to the registry container. The workflow is `docker build → docker push localhost:5001/app:tag → Helm deploy`.

**When to use:** PRD-1 and beyond. Preferred over `kind load docker-image` for this project.

**Why preferred over `kind load`:**
- `imagePullPolicy: Always` works correctly — mirrors production pull behavior
- Incremental pushes skip already-uploaded layers (faster iteration after first push)
- ArgoCD (PRD-2) and the platform dashboard (PRD-3) both assume a registry exists; building the habit now eliminates a future migration
- `kind load` has a known footgun: if the image is tagged `latest`, K8s defaults to `imagePullPolicy: Always` and the cluster tries to pull from Docker Hub, failing silently

**Trade-offs:** One extra component to bootstrap (the registry container). Mitigated by the idempotent `kind-with-registry.sh` script.

**Example (infra/kind/cluster.yaml):**
```yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
containerdConfigPatches:
- |-
  [plugins."io.containerd.grpc.v1.cri".registry]
    config_path = "/etc/containerd/certs.d"
```

**Example (scripts/kind-with-registry.sh — key steps):**
```bash
# 1. Start registry if not running
docker run -d --restart=always -p "127.0.0.1:5001:5000" --name kind-registry registry:2

# 2. Create cluster
kind create cluster --name k8s-launchpad --config infra/kind/cluster.yaml

# 3. Configure containerd on each node to resolve localhost:5001
for node in $(kind get nodes --name k8s-launchpad); do
  docker exec "$node" mkdir -p /etc/containerd/certs.d/localhost:5001
  printf '[host."http://kind-registry:5000"]\n' | \
    docker exec -i "$node" tee /etc/containerd/certs.d/localhost:5001/hosts.toml
done

# 4. Connect registry to kind network
docker network connect kind kind-registry 2>/dev/null || true
```

### Pattern 3: Generic Helm values.yaml (PRD-3 seam)

**What:** All configurable knobs for the app are in `values.yaml` with clear grouping. Templates reference `.Values.*` — no hard-coded strings in templates. When PRD-3 onboards a new app, it forks or overrides this values file; it does not touch templates.

**When to use:** Any chart that will be re-used or templated across multiple app instances.

**Trade-offs:** Slightly more verbose values file up front; eliminates chart-per-app sprawl later.

**Example (charts/field-guide-api/values.yaml):**
```yaml
# --- image ---
image:
  repository: localhost:5001/field-guide-api
  tag: "0.1.0"
  pullPolicy: IfNotPresent    # use Always when registry is running

# --- scaling ---
replicaCount: 1

# --- networking ---
service:
  type: NodePort
  port: 5000
  nodePort: 30080             # fixed port for curl convenience during dev

# --- config (non-secret, injected as ConfigMap) ---
config:
  logLevel: INFO

# --- secrets (injected as K8s Secret) ---
secrets:
  mongoUri: ""                # override at deploy time; never hardcode

# --- MongoDB dependency ---
mongodb:
  enabled: true
  auth:
    enabled: false            # disabled for local dev; PRD-4 enables TLS/auth

# --- PRD-4 seam ---
metrics:
  enabled: true               # app already exposes /metrics; scraping config added in PRD-4

# --- resource limits (PRD-4 tuning) ---
resources: {}

# --- ingress (disabled until PRD-2/3) ---
ingress:
  enabled: false
```

## Data Flow

### Build and Load Flow

```
Developer runs: make deploy
      │
      ▼
docker build -t localhost:5001/field-guide-api:0.1.0 apps/field-guide-api/
      │ (reads Dockerfile in apps/field-guide-api/)
      ▼
Docker daemon caches image layers locally
      │
      ▼
docker push localhost:5001/field-guide-api:0.1.0
      │ (pushes only new/changed layers)
      ▼
Local registry container (127.0.0.1:5001) stores layers
      │
      ▼
helm upgrade --install field-guide-api charts/field-guide-api/ --set image.tag=0.1.0
      │ (renders templates against values.yaml)
      ▼
Kubernetes Deployment created in kind cluster
      │
      ▼
kubelet (containerd) on kind node pulls from localhost:5001/field-guide-api:0.1.0
      │ (resolved via hosts.toml → http://kind-registry:5000)
      ▼
Pod scheduled and running
```

### Request Flow (app pod → MongoDB)

```
curl http://localhost:30080/api/entries
      │ (NodePort on kind node exposed to host)
      ▼
field-guide-api pod :5000
      │ Flask blueprint: GET /api/entries
      ▼
PyMongo connection pool
      │ MONGO_URI = mongodb://mongodb-svc:27017/fieldguide
      │ (K8s Service DNS: <svc-name>.<namespace>.svc.cluster.local)
      ▼
MongoDB Service (ClusterIP, port 27017)
      │
      ▼
MongoDB pod (Helm dependency)
      │ returns cursor
      ◄─────────────────────────────── JSON response
```

### Key Data Flows

1. **Secrets flow:** `.env` on dev machine → `helm upgrade --set secrets.mongoUri=$MONGO_URI` → K8s Secret → mounted as env var in pod. Secret value never in Git.
2. **Config flow:** `values.yaml` → ConfigMap template → pod env vars (LOG_LEVEL, etc.). ConfigMap is version-controlled and safe to commit.
3. **Health check flow:** `GET /health` returns `{"status": "ok"}` + checks MongoDB reachability. Kubernetes liveness/readiness probes use this endpoint.
4. **Metrics flow (seam):** `GET /metrics` exposes Prometheus-format counters. Pod annotation `prometheus.io/scrape: "true"` is set in values.yaml now; actual Prometheus scraping added in PRD-4.

## Build Order (Component Dependencies)

The build order follows hard dependency chains. Each step requires the previous to be complete.

```
Step 1: kind cluster + local registry      (infra/kind/ + scripts/)
        ↓  cluster must exist before images can be loaded
Step 2: Docker image build                  (apps/field-guide-api/Dockerfile)
        ↓  image must exist in registry before Helm references it
Step 3: docker push to local registry      (localhost:5001/...)
        ↓  registry must have image before Helm deploy pulls it
Step 4: Helm install/upgrade               (charts/field-guide-api/)
        ↓  Helm release creates Deployment + MongoDB dep
Step 5: Pods running, app reachable        (curl localhost:30080)
```

**Makefile target chain implementing this order:**

```makefile
TAG     ?= 0.1.0
CLUSTER  = k8s-launchpad
APP      = field-guide-api
REGISTRY = localhost:5001

.PHONY: cluster-up cluster-down build push deploy undeploy test clean all

cluster-up:
	scripts/kind-with-registry.sh

cluster-down:
	kind delete cluster --name $(CLUSTER)

build:
	docker build -t $(REGISTRY)/$(APP):$(TAG) apps/$(APP)/

push: build
	docker push $(REGISTRY)/$(APP):$(TAG)

deploy: push
	helm upgrade --install $(APP) charts/$(APP)/ \
	  --set image.tag=$(TAG) \
	  --set secrets.mongoUri="$(MONGO_URI)" \
	  --wait

undeploy:
	helm uninstall $(APP) --ignore-not-found

test:
	cd apps/$(APP) && python -m pytest tests/ -v --tb=short

clean: undeploy cluster-down

all: cluster-up deploy
```

**Key Makefile decisions:**
- `push: build` — push always re-builds; no stale image risk
- `deploy: push` — deploy always pushes first; `make deploy` is safe to run repeatedly
- `--wait` on helm upgrade — target returns only when pods are Ready; avoids race conditions in automation
- `TAG ?= 0.1.0` — overridable: `make deploy TAG=0.2.0` for version bumps without editing the file
- Never use `latest` tag — avoids `imagePullPolicy: Always` footgun (see Pattern 2)

## Anti-Patterns

### Anti-Pattern 1: Using `latest` tag with `kind load`

**What people do:** `docker build -t myapp:latest . && kind load docker-image myapp:latest`

**Why it's wrong:** Kubernetes defaults `imagePullPolicy: Always` for `latest`-tagged images. The kind node will try to pull from Docker Hub/registry, fail, and the pod stays in `ImagePullBackOff`. The image is in the node's containerd store but Kubernetes ignores it.

**Do this instead:** Use explicit version tags (`0.1.0`, `dev-abc123`) or set `imagePullPolicy: Never` explicitly. Better yet: use the local registry approach — `imagePullPolicy: Always` then works correctly because the registry is reachable.

### Anti-Pattern 2: Importing Flask app object at module level

**What people do:** `from myapp import app` at the top of extension files or blueprints.

**Why it's wrong:** Creates circular imports. Blueprint files import from `app`, `app` imports blueprints — Python cannot resolve the cycle.

**Do this instead:** App factory + `current_app` proxy inside blueprint functions. Extensions are initialized separately (`mongo = PyMongo()` at module level, `mongo.init_app(app)` inside `create_app()`).

### Anti-Pattern 3: Hard-coding image coordinates in Helm templates

**What people do:** `image: mycompany/field-guide-api:0.1.0` directly in `deployment.yaml`.

**Why it's wrong:** PRD-3 templating and CI automation require parameterized image references. Hard-coded values mean editing templates per deployment — templates are code, values are data.

**Do this instead:** `image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"` with defaults in `values.yaml`.

### Anti-Pattern 4: Skipping `--wait` on `helm upgrade` in Makefile

**What people do:** `helm upgrade --install myapp ./charts/myapp/` without `--wait`, then immediately curl the service.

**Why it's wrong:** Helm returns immediately after submitting manifests. Pods are still scheduling/pulling/starting. The next Makefile target or test that hits the endpoint will flap or fail.

**Do this instead:** `helm upgrade --install myapp ./charts/myapp/ --wait --timeout 120s`. Add `--atomic` if you want automatic rollback on failure.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| MongoDB (in-cluster) | Helm dependency (`charts:` stanza in Chart.yaml), accessed via K8s Service DNS | Use Bitnami MongoDB chart as dep for PRD-1; `auth.enabled: false` for local dev simplicity |
| Local registry | `docker push` + containerd `hosts.toml` config on kind nodes | Registry container must be running before `make push`; `kind-with-registry.sh` is idempotent |
| Prometheus (future, PRD-4) | `/metrics` endpoint, pod annotation `prometheus.io/scrape: "true"` | App exposes endpoint now; Prometheus scraping added in PRD-4. No code change needed at PRD-4. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Makefile ↔ scripts/ | Makefile calls `scripts/kind-with-registry.sh` as a shell exec | Script handles idempotency (checks if cluster/registry already exists); Makefile is the contract |
| Helm chart ↔ values.yaml | `.Values.*` object only — no hardcoding in templates | PRD-3 can supply a different values file per app without modifying templates |
| Flask blueprints ↔ extensions | Blueprints import `mongo` from `extensions.py`; never from `__init__.py` | Prevents circular imports; `extensions.py` has no Flask app dependency |
| app pod ↔ MongoDB | `MONGO_URI` env var injected from K8s Secret | Secret is created by Helm from `values.yaml` secret override; never committed |
| app pod ↔ host (dev) | NodePort 30080 exposed on kind node → host | For local curl during development; Ingress or port-forward added later |

## Scaling Considerations

This is a local dev platform; scaling to users is not the concern. The relevant "scaling" is adding more apps to the platform (PRD-3).

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1 app (PRD-1) | Single chart, single values.yaml, single namespace |
| 3-5 apps (PRD-3) | Generic chart template; per-app values override files; App-of-Apps Helm/ArgoCD pattern |
| 10+ apps (post-PRD-4) | Helm library chart extracted from field-guide-api chart; chart museum or OCI registry for chart storage |

## Sources

- kind official local registry docs: https://kind.sigs.k8s.io/docs/user/local-registry/
- kind load vs registry architectural analysis: https://iximiuz.com/en/posts/kubernetes-kind-load-docker-image/
- Flask app factory pattern: https://flask.palletsprojects.com/en/stable/patterns/appfactories/ (via Context7 /pallets/flask)
- Helm chart best practices (imagePullPolicy, values structure): https://helm.sh/docs/chart_best_practices/ (via Context7 /helm/helm-www)
- Generic Helm chart pattern: https://rtfm.co.ua/en/helm-reusable-chart-named-templates-and-a-generic-chart-for-multiple-applications/
- Flask + MongoDB + Docker structure: https://www.digitalocean.com/community/tutorials/how-to-set-up-flask-with-mongodb-and-docker

---
*Architecture research for: local Kubernetes IDP foundation (PRD-1)*
*Researched: 2026-07-04*
