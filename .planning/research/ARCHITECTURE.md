# Architecture Research

**Domain:** Local Kubernetes Internal Developer Platform — v1.1 Product Dashboard (PRD-3)
**Researched:** 2026-07-08
**Confidence:** HIGH (derived from live codebase inspection + K8s in-cluster config docs)

---

## Standard Architecture

### System Overview — v1.1 (two-app state)

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         DEV MACHINE (host)                                  │
│                                                                              │
│  make build          make build-launchpad                                   │
│  docker build        docker build                                            │
│  apps/field-guide-api/    apps/launchpad/                                   │
│         │                        │                                           │
│         └──────────┬─────────────┘                                          │
│                    ▼                                                          │
│         docker push localhost:5001/...                                       │
│                    │                                                          │
│          ┌─────────▼──────────┐                                             │
│          │  Local Registry     │  registry:3 @ localhost:5001                │
│          └─────────┬──────────┘                                             │
│                    │ Docker network (kind)                                   │
└────────────────────┼────────────────────────────────────────────────────────┘
                     │
        ┌────────────▼────────────────────────────────────────────┐
        │                  KIND CLUSTER (default namespace)         │
        │                                                           │
        │  ┌───────────────────┐    ┌───────────────────────────┐  │
        │  │  field-guide-api   │    │       launchpad            │  │
        │  │  pod :8000         │    │       pod :8000            │  │
        │  │  Flask REST API    │◄───│  HTTP GET /health          │  │
        │  └────────┬──────────┘    │  (ClusterIP DNS)           │  │
        │           │ MONGO_URI      └──────────┬────────────────┘  │
        │           │                           │ MONGO_URI          │
        │  ┌────────▼──────────┐    ┌──────────▼────────────────┐  │
        │  │  field-guide-api   │    │  launchpad-mongodb         │  │
        │  │  -mongodb pod      │    │  pod :27017               │  │
        │  │  mongo:7           │    │  mongo:7                  │  │
        │  └───────────────────┘    └───────────────────────────┘  │
        │                                        │                   │
        │                           ┌────────────▼────────────────┐ │
        │                           │  K8s API server              │ │
        │                           │  https://kubernetes.default  │ │
        │                           │  ◄── launchpad ServiceAccount│ │
        │                           │       (read-only RBAC)       │ │
        │                           └─────────────────────────────┘ │
        └───────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Status |
|-----------|----------------|--------|
| `apps/field-guide-api/` | Flask REST API for DevOps knowledge entries | v1.0 — UNTOUCHED |
| `charts/field-guide-api/` | Helm chart: Deployment + Service + ConfigMap + Secret + MongoDB manifests | v1.0 — UNTOUCHED |
| `apps/launchpad/` | Platform dashboard Flask app: UI shell, status API, service catalog, events feed, K8s diagnostics | NEW in v1.1 |
| `charts/launchpad/` | Helm chart for launchpad: Deployment + Service + ConfigMap + Secret + MongoDB manifests + RBAC manifests | NEW in v1.1 |
| `Makefile` | Developer CLI — add LP_ variable block + launchpad-specific targets + `up-all` composite | MODIFIED in v1.1 |
| `infra/kind/` | Cluster definition + registry bootstrap | v1.0 — UNTOUCHED |
| `scripts/` | Shell scripts (cluster-setup.sh, cluster-teardown.sh) | v1.0 — UNTOUCHED |

---

## Repository Tree: New vs Modified vs Untouched

```
k8s-launchpad/
├── apps/
│   ├── field-guide-api/       ← UNTOUCHED (zero changes)
│   └── launchpad/             ← NEW
│       ├── Dockerfile
│       ├── requirements.txt
│       ├── requirements-dev.txt
│       ├── pytest.ini
│       ├── .env.example
│       ├── .dockerignore
│       ├── wsgi.py
│       ├── app/
│       │   ├── __init__.py    # create_app factory (same pattern as field-guide-api)
│       │   ├── config.py      # Config: MONGO_URI, FIELD_GUIDE_URL, K8S_NAMESPACE
│       │   ├── extensions.py  # mongo (Flask-PyMongo)
│       │   ├── k8s.py         # K8s client init: in-cluster → kubeconfig → None
│       │   └── routes/
│       │       ├── __init__.py
│       │       ├── ui.py      # Jinja2 routes: GET /, /services, /diagnostics
│       │       ├── status.py  # GET /health, GET /api/status
│       │       ├── services.py # GET/POST/DELETE /api/services
│       │       └── events.py  # GET /api/events, POST /api/events
│       ├── app/static/        # vendored htmx.min.js, CSS
│       ├── app/templates/     # Jinja2 HTML: base.html, index.html, services.html, ...
│       └── tests/
│           └── conftest.py    # create_app fixture, mock K8s client, mock requests
│
├── charts/
│   ├── field-guide-api/       ← UNTOUCHED (zero changes — critical constraint)
│   └── launchpad/             ← NEW
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│           ├── _helpers.tpl   # launchpad.fullname, launchpad.mongodb.fullname, etc.
│           ├── deployment.yaml
│           ├── service.yaml
│           ├── configmap.yaml
│           ├── secret.yaml    # MONGO_URI only (same pattern as field-guide-api)
│           ├── NOTES.txt
│           ├── rbac/          ← NEW (no equivalent in field-guide-api chart)
│           │   ├── serviceaccount.yaml
│           │   ├── role.yaml
│           │   └── rolebinding.yaml
│           └── mongodb/       # same pattern as charts/field-guide-api/templates/mongodb/
│               ├── deployment.yaml
│               ├── service.yaml
│               ├── pvc.yaml
│               └── secret.yaml
│
├── infra/                     ← UNTOUCHED
├── scripts/                   ← UNTOUCHED
├── Makefile                   ← MODIFIED (LP_ variable block + 6 new targets)
└── README.md                  ← MODIFIED (dashboard demo flow + screenshot placeholders)
```

---

## Architectural Patterns for v1.1

### Pattern 1: Separate MongoDB per Chart (Ownership Decision)

**What:** Each Helm chart embeds its own MongoDB manifests and owns its own PVC. The launchpad chart deploys a second `mongo:7` pod using the same `templates/mongodb/` subdirectory pattern established in `charts/field-guide-api/`.

**Decision rationale — why not a shared MongoDB instance:**

| Option | What changes | Why rejected |
|--------|-------------|-------------|
| Shared MongoDB (third Helm release) | field-guide-api chart must be modified to `mongodb.enabled=false` + `externalMongoUri=...`; new `charts/mongodb/` release; Makefile deploy ordering becomes three-step with explicit dependency | Breaks the clean v1.0 chart; adds a deploy dependency that complicates `make up-all`; field-guide-api's `externalMongoUri` seam exists for this but using it means the working v1.0 chart is modified |
| Separate MongoDB per chart (CHOSEN) | launchpad gets its own `mongo:7` pod + PVC; databases are `fieldguide` (field-guide-api) and `launchpad` (launchpad); no cross-chart dependency | field-guide-api chart is zero-touch; each chart is independently installable/uninstallable; two pods is acceptable on a local kind cluster |

**Database layout:**
- `field-guide-api-mongodb` pod → database `fieldguide` → collections: `entries`
- `launchpad-mongodb` pod → database `launchpad` → collections: `services`, `events`

**Helm values pattern (charts/launchpad/values.yaml):**
```yaml
mongodb:
  enabled: true
  image: mongo:7
  auth:
    username: root
    password: launchpad-dev-password   # local kind only; never a real credential
    database: launchpad
  persistence:
    enabled: true
    size: 1Gi
    storageClass: ""

config:
  mongoDbName: launchpad
  fieldGuideUrl: "http://field-guide-api"  # ClusterIP DNS — same namespace
  k8sNamespace: "default"
  flaskDebug: ""
```

The `externalMongoUri` seam in `charts/field-guide-api/values.yaml` remains in place and unused — available for future PRDs where a genuine shared DB is warranted.

### Pattern 2: Service-to-Service via ClusterIP DNS

**What:** The launchpad app calls the field-guide-api `/health` endpoint to report platform status. Both apps deploy in the `default` namespace, so the field-guide-api ClusterIP Service is reachable at `http://field-guide-api` (short DNS form — no namespace qualification needed within the same namespace).

**In-cluster resolution chain:**
```
launchpad pod
  → HTTP GET http://field-guide-api/health   (short DNS)
  → kube-dns resolves to field-guide-api ClusterIP (port 80)
  → field-guide-api pod :8000 /health
  ← 200 {"status": "ok", ...}
```

**Config injection via ConfigMap:**
```yaml
# charts/launchpad/templates/configmap.yaml
FIELD_GUIDE_URL: {{ .Values.config.fieldGuideUrl | quote }}
# default: "http://field-guide-api"
```

**App-level graceful degradation (no cluster or field-guide-api down):**
```python
# apps/launchpad/app/routes/status.py
import requests

FIELD_GUIDE_URL = os.environ.get("FIELD_GUIDE_URL", "http://localhost:8080")

def check_field_guide_health():
    try:
        r = requests.get(f"{FIELD_GUIDE_URL}/health", timeout=2)
        return {"status": "ok", "code": r.status_code}
    except requests.exceptions.RequestException:
        return {"status": "unreachable"}
```

For local dev/tests: set `FIELD_GUIDE_URL=http://localhost:8080` in `.env`; if no port-forward is active, the check returns `"unreachable"` — UI shows degraded card, app does not crash.

**Test isolation:** Mock `requests.get` in pytest via `monkeypatch` or `unittest.mock.patch`. Never hit a real network in unit tests.

### Pattern 3: K8s API Access — In-Cluster Config with Kubeconfig Fallback

**What:** The launchpad diagnostics section queries the K8s API for pod and Deployment status in the `default` namespace. The `kubernetes` Python client supports two config loading strategies; the app tries both in order.

**Loading strategy (apps/launchpad/app/k8s.py):**
```python
from kubernetes import client, config
from kubernetes.config import ConfigException

def init_k8s_client():
    """Returns (CoreV1Api, AppsV1Api) tuple or (None, None) on failure."""
    try:
        config.load_incluster_config()        # pod: mounted SA token
    except ConfigException:
        try:
            config.load_kube_config()         # local dev: ~/.kube/config
        except ConfigException:
            return None, None                 # no config — degrade gracefully
    return client.CoreV1Api(), client.AppsV1Api()
```

**In-cluster mechanics:** When the pod runs with a ServiceAccount that has the RBAC role, Kubernetes mounts the token at `/var/run/secrets/kubernetes.io/serviceaccount/token` and the CA at `.../ca.crt`. `load_incluster_config()` reads these automatically. The pod calls `https://kubernetes.default.svc.cluster.local`.

**Local dev mechanics:** `load_kube_config()` reads `~/.kube/config`, which `make cluster-up` populates via `kind create cluster`. The developer's kubeconfig already points at the kind cluster.

**Graceful degradation:** If `init_k8s_client()` returns `(None, None)`, all K8s-dependent routes return a `{"status": "unavailable", "reason": "no_cluster"}` response. The UI renders a degraded diagnostics card without crashing. This is the correct behavior for unit tests (no kubeconfig in CI) and local dev without a running cluster.

**RBAC manifests (charts/launchpad/templates/rbac/):**

```yaml
# serviceaccount.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ include "launchpad.fullname" . }}-sa
  labels: ...

# role.yaml — namespace-scoped (Role, not ClusterRole)
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: {{ include "launchpad.fullname" . }}-reader
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "watch"]

# rolebinding.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: {{ include "launchpad.fullname" . }}-reader
subjects:
- kind: ServiceAccount
  name: {{ include "launchpad.fullname" . }}-sa
  namespace: {{ .Release.Namespace }}
roleRef:
  kind: Role
  name: {{ include "launchpad.fullname" . }}-reader
  apiGroup: rbac.authorization.k8s.io
```

The Deployment spec must include `serviceAccountName: {{ include "launchpad.fullname" . }}-sa` — without this, the pod uses the `default` ServiceAccount (which has no RBAC role) and `load_incluster_config()` succeeds but API calls return 403.

**Namespace strategy:** `default` namespace for both apps. Role is namespace-scoped (not ClusterRole). The diagnostics section lists pods/deployments in `default` only — correct for this project's scope. A `K8S_NAMESPACE` ConfigMap key makes the target namespace configurable without changing templates.

### Pattern 4: Makefile Extension — LP_ Variable Block + Named Targets

**What:** Add a second variable block and named targets for the launchpad app. Existing targets (`build`, `load`, `deploy`, etc.) are untouched — they still refer to field-guide-api. New targets use `LP_` prefix for variables and `-launchpad` suffix for target names.

**Why this over a parameterized APP variable:**
- `make build APP=field-guide-api` changes the existing `make build` contract — breaks muscle memory and any scripts that call `make build`
- Named targets are explicit in `make help` output — a reviewer sees both apps clearly
- Git Bash / MSYS does not add complications from variable interpolation in multi-value targets
- The v1.0 `make up` and `make smoke` chains continue to work unchanged

**Additions to Makefile:**
```makefile
# Launchpad image coordinates — override with: make build-launchpad LP_TAG=v1.1
LP_IMAGE   ?= localhost:5001/launchpad
LP_TAG     ?= dev
LP_RELEASE ?= launchpad
LP_CHART   ?= charts/launchpad

.PHONY: build-launchpad load-launchpad deploy-launchpad undeploy-launchpad \
        port-forward-launchpad smoke-launchpad up-all test-launchpad

build-launchpad: ## build the launchpad Docker image
	docker build -t $(LP_IMAGE):$(LP_TAG) apps/launchpad

load-launchpad: ## push launchpad image to the local kind registry
	docker push $(LP_IMAGE):$(LP_TAG)

deploy-launchpad: ## install or upgrade the launchpad Helm release
	helm upgrade --install $(LP_RELEASE) $(LP_CHART) \
		--set image.repository=$(LP_IMAGE) --set image.tag=$(LP_TAG) \
		--wait --timeout 180s

undeploy-launchpad: ## remove the launchpad Helm release
	helm uninstall $(LP_RELEASE)

port-forward-launchpad: ## forward svc/launchpad to localhost:8081 (Ctrl-C to stop)
	kubectl port-forward svc/$(LP_RELEASE) 8081:80

smoke-launchpad: ## smoke test the launchpad dashboard endpoints
	# (same background port-forward + curl pattern as existing smoke target)
	# checks: /, /health, /api/status

test-launchpad: ## run launchpad pytest suite with coverage
	cd apps/launchpad && \
	{ [ -d .venv ] || $(PYTHON) -m venv .venv; } && \
	VENV_PY=$$([ -x .venv/bin/python ] && echo .venv/bin/python || echo .venv/Scripts/python) && \
	"$$VENV_PY" -m pip install -q -r requirements-dev.txt && \
	"$$VENV_PY" -m pytest

up-all: cluster-up build load deploy build-launchpad load-launchpad deploy-launchpad
up-all: ## bring up full stack: cluster + both apps (field-guide-api + launchpad)
```

Port assignment: `port-forward` uses `localhost:8080` (field-guide-api, existing). `port-forward-launchpad` uses `localhost:8081` (no conflict).

`.PHONY` declaration in the existing line must be extended to include all new targets. Git Bash and MSYS constraints are already handled by the existing `SHELL := /bin/bash` and `export MSYS_NO_PATHCONV=1` headers.

---

## Data Flow

### Request Flow: Browser → Launchpad Dashboard

```
Browser GET http://localhost:8081/
    │  (kubectl port-forward svc/launchpad 8081:80 active)
    ▼
launchpad ClusterIP Service (port 80 → targetPort 8000)
    ▼
launchpad pod (gunicorn :8000)
    │  Jinja2 route: ui.py GET /
    ▼
status.py: check_field_guide_health()
    │  HTTP GET http://field-guide-api/health (ClusterIP DNS, 2s timeout)
    ▼
field-guide-api pod :8000 /health → 200 {"status": "ok"}
    │
k8s.py: list_namespaced_pod(namespace="default")
    │  HTTPS kubernetes.default.svc.cluster.local (SA token)
    ▼
K8s API → pod list in default namespace
    │
mongo: db.services.find(), db.events.find()
    ▼
launchpad-mongodb ClusterIP Service :27017
    ▼
launchpad-mongodb pod → launchpad database
    │
    ◄── Jinja2 renders index.html with status cards + service list
    ◄── HTTP 200 HTML response to browser
```

### Graceful Degradation Flow (local dev, no cluster)

```
Developer runs: cd apps/launchpad && python -m flask run
    │  MONGO_URI=mongodb://localhost:27017/launchpad (.env)
    │  FIELD_GUIDE_URL=http://localhost:8080 (.env)
    ▼
check_field_guide_health()
    │  requests.get("http://localhost:8080/health", timeout=2)
    │  → ConnectionRefused (no port-forward active)
    ▼
returns {"status": "unreachable"}  ← no crash, UI shows degraded card

k8s.py: init_k8s_client()
    │  load_incluster_config() → ConfigException (no SA token)
    │  load_kube_config() → succeeds if cluster is up; ConfigException if not
    ▼
returns (None, None) → k8s routes return {"status": "unavailable"}
    │
Jinja2 renders dashboard with degraded/unknown states for K8s cards
```

### Data Flow: Service Catalog CRUD

```
Browser POST /api/services (htmx request)
    │  {"name": "my-api", "repo": "github.com/..."}
    ▼
launchpad pod: services.py POST handler
    │  validates payload (name required, URL format)
    ▼
mongo: db.services.insert_one(doc)   +   db.events.insert_one(event_doc)
    ▼
launchpad-mongodb pod → launchpad DB
    │
    ◄── HTTP 200 HTML fragment (htmx swap target)
    ◄── service card appears in browser without full page reload
```

---

## Integration Points

### New Integration Points (v1.1)

| Integration | Direction | Mechanism | Failure mode |
|-------------|-----------|-----------|--------------|
| launchpad → field-guide-api | outbound HTTP | `requests.get(FIELD_GUIDE_URL + "/health", timeout=2)` | `ConnectionError` → `{"status": "unreachable"}`; UI shows degraded card |
| launchpad → K8s API | outbound HTTPS | `kubernetes` Python client, in-cluster SA token | `ApiException` / `ConfigException` → `{"status": "unavailable"}`; diagnostics section hidden |
| launchpad → launchpad-mongodb | MongoDB wire | Flask-PyMongo, `MONGO_URI` from K8s Secret | `ServerSelectionTimeoutError` (2s) → `/health` returns 503; service catalog routes return 503 |
| browser → launchpad | inbound HTTP | kubectl port-forward svc/launchpad 8081:80 | port-forward not active → connection refused; not an app-level concern |

### Existing Integration Points (v1.0, unchanged)

| Integration | Direction | Mechanism | Notes |
|-------------|-----------|-----------|-------|
| field-guide-api → field-guide-api-mongodb | outbound MongoDB | Flask-PyMongo, `MONGO_URI` from K8s Secret | `?serverSelectionTimeoutMS=2000` in URI |
| Makefile → Docker daemon | build | `docker build`, `docker push` | `MSYS_NO_PATHCONV=1` prevents path mangling |
| Makefile → Helm | deploy | `helm upgrade --install --wait --timeout 180s` | `--wait` required; pods must be Ready before target returns |
| pod → local registry | image pull | containerd `hosts.toml` mirror config | `localhost:5001` → `http://kind-registry:5000` via Docker network |

### Internal Boundaries (launchpad app)

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `routes/ui.py` ↔ `routes/status.py` | Function call (shared module) | UI route calls status helpers; no circular import if status has no Flask template deps |
| `routes/*.py` ↔ `extensions.py` | Import `mongo` from `app.extensions` | Same pattern as field-guide-api; never import from `app.__init__` |
| `routes/*.py` ↔ `k8s.py` | Import `init_k8s_client` function | `k8s.py` is a standalone module; initialized once at app startup in `create_app()` and stored on `app.extensions` or `g` |
| `app/__init__.py` ↔ blueprints | Deferred import inside `create_app()` | Same pattern as field-guide-api; blueprints imported after extensions are initialized |

---

## Build Order for v1.1

Dependencies are strict within the phase structure. Each item must be complete before the next can be validated end-to-end.

```
EXISTING (v1.0, already done):
  kind cluster + local registry         (make cluster-up)
  field-guide-api image + chart         (make build load deploy)

v1.1 PHASE 1: apps/launchpad/ scaffold
  ├── app/__init__.py (create_app factory — identical pattern to field-guide-api)
  ├── app/config.py (MONGO_URI, FIELD_GUIDE_URL, K8S_NAMESPACE env vars)
  ├── app/extensions.py (Flask-PyMongo init)
  ├── app/k8s.py (in-cluster → kubeconfig → None degradation)
  ├── app/routes/ stubs (ui.py, status.py, services.py, events.py)
  ├── tests/conftest.py (create_app fixture + mock k8s + mock requests)
  ├── requirements.txt + requirements-dev.txt
  └── pytest.ini
  VALIDATES: make test-launchpad passes without cluster or MongoDB

v1.1 PHASE 2: UI layer
  ├── app/templates/ (base.html, index.html, services.html, diagnostics.html)
  ├── app/static/ (vendored htmx.min.js, CSS)
  └── routes/ui.py (Jinja2 render + htmx fragment responses)
  VALIDATES: flask run locally; browser shows dashboard (degraded state cards are OK)

v1.1 PHASE 3: Status API + field-guide-api integration
  ├── routes/status.py (GET /health, GET /api/status)
  └── status.py calls FIELD_GUIDE_URL/health with 2s timeout + graceful degradation
  VALIDATES: /health returns 200; /api/status returns JSON with field_guide status

v1.1 PHASE 4: K8s client + RBAC + charts/launchpad/
  ├── k8s.py complete (list pods, list deployments)
  ├── routes/status.py K8s section
  ├── charts/launchpad/Chart.yaml
  ├── charts/launchpad/values.yaml
  ├── charts/launchpad/templates/_helpers.tpl
  ├── charts/launchpad/templates/deployment.yaml   (includes serviceAccountName)
  ├── charts/launchpad/templates/service.yaml
  ├── charts/launchpad/templates/configmap.yaml
  ├── charts/launchpad/templates/secret.yaml       (MONGO_URI)
  ├── charts/launchpad/templates/rbac/serviceaccount.yaml
  ├── charts/launchpad/templates/rbac/role.yaml
  ├── charts/launchpad/templates/rbac/rolebinding.yaml
  └── apps/launchpad/Dockerfile
  VALIDATES: helm lint charts/launchpad/ passes; make build-launchpad load-launchpad deploy-launchpad
             runs; pod is Running; /health 200; /api/status shows K8s pod list

v1.1 PHASE 5: Service catalog + events (MongoDB CRUD)
  ├── charts/launchpad/templates/mongodb/ (deployment/service/pvc/secret — same pattern)
  ├── routes/services.py (GET/POST/DELETE /api/services + htmx fragment)
  └── routes/events.py (GET /api/events + htmx stream fragment)
  VALIDATES: service catalog form submits; data persists in launchpad DB;
             make undeploy-launchpad + deploy-launchpad; data survives (PVC retained)

v1.1 PHASE 6: Makefile + integration smoke test
  ├── Makefile LP_ variable block
  ├── Makefile launchpad targets (build-launchpad, load-launchpad, deploy-launchpad, ...)
  ├── Makefile up-all target
  └── smoke-launchpad target
  VALIDATES: make up-all (fresh cluster) → both apps running → smoke-launchpad PASS
             make help shows all new targets with descriptions
```

**Critical ordering constraints:**

- `charts/launchpad/templates/rbac/` must include `serviceAccountName` in the Deployment template — if omitted, the pod uses `default` SA and K8s API calls return 403 even though RBAC looks correct in `kubectl get rolebinding`.
- MongoDB manifests in `charts/launchpad/templates/mongodb/` must use helpers from `_helpers.tpl` (e.g., `launchpad.mongodb.fullname`) that are distinct from the `field-guide-api` helpers — name collisions in the same namespace would route traffic between the wrong MongoDB pods.
- `make deploy-launchpad` should run after `make deploy` (field-guide-api) so the field-guide-api Service exists when the dashboard's status check first runs, but this is a soft ordering — launchpad degrades gracefully if field-guide-api is absent.

---

## Anti-Patterns for v1.1

### Anti-Pattern 1: Shared MongoDB with Cross-Chart Secret Reference

**What people do:** Set `mongodb.enabled=false` in `charts/field-guide-api/values.yaml` and point both apps at a single MongoDB release.

**Why it's wrong:** It requires modifying the working v1.0 chart, introducing a new deploy-time dependency ordering (MongoDB release must exist before either app chart), and complicates `helm uninstall` for either app. The `externalMongoUri` seam exists for exactly this scenario but using it here adds risk with minimal benefit for two lightweight apps.

**Do this instead:** Two `mongo:7` pods, two databases. The local kind cluster has ample resources. Keep each chart self-contained.

### Anti-Pattern 2: Using ClusterRole Instead of Role for Dashboard RBAC

**What people do:** Create a `ClusterRole` for the ServiceAccount to avoid dealing with namespace scoping.

**Why it's wrong:** ClusterRole grants permissions across ALL namespaces. For a dashboard that only needs to inspect the `default` namespace, this is unnecessary privilege escalation and a bad security pattern — especially in a portfolio project where a reviewer will check the RBAC manifests.

**Do this instead:** `Role` + `RoleBinding` scoped to `default`. If a future PRD requires multi-namespace inspection, expand to `ClusterRole` with justification in a comment.

### Anti-Pattern 3: Hardcoding Service DNS in the App

**What people do:** `FIELD_GUIDE_URL = "http://field-guide-api"` as a Python constant.

**Why it's wrong:** The URL must be overridable for local dev (`localhost:8080`), CI (mock), and future environments. Hardcoded URLs also break `helm lint` reasoning when the target service name changes.

**Do this instead:** Read from environment variable with a sensible local default. Inject via ConfigMap in the chart. The value in `values.yaml` becomes the single source of truth for the in-cluster URL.

### Anti-Pattern 4: Duplicating Makefile targets instead of LP_ prefix pattern

**What people do:** Copy `build`, `load`, `deploy`, `smoke` target bodies and change image/release names inside them.

**Why it's wrong:** The existing targets refer to `$(IMAGE)`, `$(RELEASE)`, `$(CHART)` variables. Copying and editing the bodies makes `make help` ambiguous and creates divergence when the original targets are updated.

**Do this instead:** New variable block with `LP_` prefix + new target names (`build-launchpad`, etc.). The `up-all` composite chains both sets. `make build` always means field-guide-api; `make build-launchpad` always means the dashboard. No ambiguity.

### Anti-Pattern 5: Calling `load_incluster_config()` Without a Try/Except

**What people do:** `kubernetes.config.load_incluster_config()` at module import time or in `create_app()` without catching `ConfigException`.

**Why it's wrong:** Module-level K8s config loading fails immediately outside the cluster, making the app unimportable for tests. `create_app()` crashes on every `make test-launchpad` run in a developer environment without a cluster.

**Do this instead:** Lazy initialization with the try/except chain in `k8s.py`. Store the result on `current_app` or return `None` when no config is available. Routes check for `None` and return a degraded response.

---

## Namespace Strategy

Both apps deploy in the `default` namespace. This is intentional for v1.1:
- ClusterIP Service DNS short-form works: `http://field-guide-api` resolves within `default`
- RBAC `Role` (not `ClusterRole`) scoped to `default` is correct minimum privilege
- `kubectl port-forward`, `make smoke`, and `make smoke-launchpad` use the same namespace context
- No additional `kubectl config set-context` steps for the developer

A dedicated `launchpad` namespace would require cross-namespace DNS (`http://field-guide-api.default.svc.cluster.local`), namespace-aware RBAC, and `--namespace` flags on every `helm upgrade` and `kubectl` call. Not justified for this scope.

---

## Sources

- `charts/field-guide-api/` — live codebase inspection: Helm helper patterns, MongoDB manifest structure, RBAC-free baseline (HIGH confidence)
- `Makefile` — live codebase inspection: variable naming conventions, `MSYS_NO_PATHCONV`, `SHELL := /bin/bash`, `LP_` prefix approach (HIGH confidence)
- `apps/field-guide-api/app/__init__.py` — live codebase inspection: app factory pattern to replicate in launchpad (HIGH confidence)
- [kubernetes Python client](https://github.com/kubernetes-client/python) — `load_incluster_config()` / `load_kube_config()` / `ConfigException` pattern (HIGH confidence)
- [Kubernetes RBAC docs](https://kubernetes.io/docs/reference/access-authn-authz/rbac/) — Role vs ClusterRole, ServiceAccount mounting, projected token path (HIGH confidence)
- [K8s in-cluster config](https://kubernetes.io/docs/tasks/run-application/access-api-from-pod/) — SA token path `/var/run/secrets/kubernetes.io/serviceaccount/`, `kubernetes.default.svc` (HIGH confidence)
- [K8s Service DNS](https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/) — `<svc>.<namespace>.svc.cluster.local` resolution (HIGH confidence)

---
*Architecture research for: k8s-launchpad v1.1 Product Dashboard (PRD-3)*
*Researched: 2026-07-08*
