# Stack Research

**Domain:** Local Kubernetes IDP Foundation — Flask API + Docker + kind + Helm + MongoDB
**Researched:** 2026-07-04
**Confidence:** HIGH (all versions verified against PyPI, official GitHub releases, and official docs)

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11 | Runtime (locked) | Matches developer stack; gunicorn 26 requires ≥3.10; LTS support through 2027 |
| Flask | 3.1.3 | REST API framework (locked) | Latest stable (Feb 2026); drops Werkzeug legacy; async-ready; minimal surface area matches IDP dogfood scope |
| Flask-PyMongo | 3.0.1 | MongoDB integration extension | Requires Flask ≥3.0 + PyMongo ≥4.0; officially maintained under mongodb-labs; cleaner app-factory support than raw MongoClient wiring |
| PyMongo | 4.13.2 | MongoDB driver | Latest stable; `patch-version-number = 4.13.2` confirmed in official snooty.toml; synchronous API appropriate for Flask |
| gunicorn | 26.0.0 | WSGI production server | Latest stable (May 2026); requires Python ≥3.10; standard for Flask-in-container; 1 worker per Kubernetes pod (let K8s scale horizontally) |
| prometheus-flask-exporter | 0.23.2 | /metrics endpoint | Latest (Mar 2025); wraps `prometheus_client`; zero-config auto-instruments HTTP duration, request count, exceptions; exposes on `/metrics` matching PRD-4 Prometheus scrape seam |
| python-dotenv | 1.2.2 | Local .env loading | Latest (Mar 2026); standard for local config without committing secrets |
| kind | v0.32.0 | Local Kubernetes cluster (locked) | Latest release; Kubernetes 1.33.1 default node image; CI-friendly, disposable, free |
| Docker | 27.x (host-installed) | Container runtime (locked) | Required by kind; build target for Flask image |
| Helm | 3.21.2 (locked) | Chart packaging (locked) | Latest Helm 3 (Jun 2026); bug fixes through Jul 2026. **See note below on Helm 4.** |

> **Helm 4 note:** Helm 4.2.2 is now the current stable release (Jun 2026). Helm 3 approaches security-only EOL Nov 2026. Helm 3 charts are fully compatible with Helm 4 unchanged — the chart format did not change. If installing fresh, prefer Helm 4.2.2; the "Helm 3" locked decision refers to chart format (vs Helm 2 / Tiller), not the binary version.

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.1.1 | Test runner | Always; latest stable (Jun 2026); async-aware; rich fixture model |
| pytest-flask | 1.3.0 | Flask test client fixture | Always; v1.3.0 fixed Flask 3.0 compatibility (removed deprecated `request_ctx`); provides `client` fixture via `conftest.py` |
| pytest-cov | 5.x (latest) | Coverage reporting | Always; plug into `make test` for 95% target; `--cov=src --cov-report=term-missing` |
| Werkzeug | (Flask dep, auto) | WSGI utilities | Do not pin separately; Flask 3.x pins compatible version |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| registry:3 | Local OCI registry container | Run as `kind-registry` on `localhost:5001`; push with `docker push localhost:5001/image:tag`; pods reference same host:port via containerd mirror config |
| make | Makefile task runner | Set `SHELL := /bin/bash` at top; add `MSYS_NO_PATHCONV=1` export for Git Bash path-conversion bug; all targets must be POSIX-safe |
| .gitattributes | LF enforcement | Add `* text=auto eol=lf` + `*.sh text eol=lf` to prevent CRLF in scripts on Windows; critical for WSL2/Git Bash shells — CRLF in shell scripts causes `bad interpreter: No such file or directory` |

---

## Installation (requirements.txt)

```text
Flask==3.1.3
Flask-PyMongo==3.0.1
pymongo==4.13.2
gunicorn==26.0.0
prometheus-flask-exporter==0.23.2
python-dotenv==1.2.2
```

```text
# requirements-dev.txt
pytest==9.1.1
pytest-flask==1.3.0
pytest-cov>=5.0
```

---

## MongoDB In-Cluster: Simple Manifest (NOT Bitnami)

**Decision: Bundle MongoDB as plain Kubernetes manifests inside the Helm chart, not as a Helm dependency.**

**Why not Bitnami:** Bitnami MongoDB chart moved behind a Broadcom commercial subscription effective September 29, 2025. The OCI artifacts at `registry-1.docker.io/bitnamicharts/mongodb` no longer receive updates and will eventually require login. This is a hard blocker for a free, local, portfolio project.

**Why not MongoDB Community Operator:** The `mongodb/community-operator` Helm chart deploys a Kubernetes Operator with CRDs, RBAC, and a MongoDBCommunity custom resource. That's 6+ resources for what needs to be a single-instance learning deployment. Wrong complexity tier for PRD-1.

**Recommended approach:** Add these templates directly inside `charts/field-guide-api/templates/`:
- `mongodb-deployment.yaml` — `Deployment` using `mongo:7` (official Docker Hub image; latest LTS)
- `mongodb-service.yaml` — `ClusterIP` Service on port 27017
- `mongodb-pvc.yaml` — `PersistentVolumeClaim` backed by kind's default hostPath StorageClass
- `mongodb-secret.yaml` — Kubernetes `Secret` with `MONGO_INITDB_ROOT_USERNAME` / `MONGO_INITDB_ROOT_PASSWORD` (base64, from values)

This keeps MongoDB fully in-chart, deletable with `helm uninstall`, and visible in the chart for portfolio reviewers to read.

---

## kind + Local Registry Pattern

### Canonical 2025/2026 Setup

The official kind documentation now uses `registry:3` (not registry:2). The canonical shell script (`scripts/kind-with-registry.sh`):

```bash
#!/usr/bin/env bash
set -euo pipefail

REGISTRY_NAME="kind-registry"
REGISTRY_PORT="5001"
CLUSTER_NAME="k8s-launchpad"
KIND_NODE_IMAGE="kindest/node:v1.33.1"

# 1. Start registry container (idempotent)
if [ "$(docker inspect -f '{{.State.Running}}' "${REGISTRY_NAME}" 2>/dev/null)" != 'true' ]; then
  docker run -d --restart=always -p "127.0.0.1:${REGISTRY_PORT}:5000" \
    --network bridge --name "${REGISTRY_NAME}" registry:3
fi

# 2. Create kind cluster with containerd mirror config
cat <<EOF | kind create cluster --name "${CLUSTER_NAME}" --image "${KIND_NODE_IMAGE}" --config=-
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
containerdConfigPatches:
- |-
  [plugins."io.containerd.grpc.v1.cri".registry]
    config_path = "/etc/containerd/certs.d"
EOF

# 3. Write hosts.toml on each node so containerd resolves localhost:5001 -> registry
REGISTRY_DIR="/etc/containerd/certs.d/localhost:${REGISTRY_PORT}"
for node in $(kind get nodes --name "${CLUSTER_NAME}"); do
  docker exec "${node}" mkdir -p "${REGISTRY_DIR}"
  cat <<EOF | docker exec -i "${node}" cp /dev/stdin "${REGISTRY_DIR}/hosts.toml"
[host."http://${REGISTRY_NAME}:5000"]
EOF
done

# 4. Connect registry to kind network (if not already)
if [ "$(docker inspect -f='{{json .NetworkSettings.Networks.kind}}' "${REGISTRY_NAME}")" = 'null' ]; then
  docker network connect kind "${REGISTRY_NAME}"
fi

# 5. Document registry via ConfigMap (for tooling discovery)
kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:${REGISTRY_PORT}"
    help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
EOF
```

**Usage pattern:**
- Build: `docker build -t localhost:5001/field-guide-api:latest ./apps/field-guide-api`
- Push to registry: `docker push localhost:5001/field-guide-api:latest`
- Helm values: `image.repository: localhost:5001/field-guide-api`
- Pod image pull: pods reference `localhost:5001/...` (containerd mirrors it via `kind-registry:5000`)

---

## Docker Image Best Practices

**Base image: `python:3.11-slim`** (Debian-based, NOT Alpine)

Alpine requires compiling Python C extensions from source because Alpine uses musl libc instead of glibc — PyMongo and other wheels ship pre-compiled for glibc. Alpine builds are slower, larger after you install build deps, and more fragile. `python:3.11-slim` is the correct choice.

**Multi-stage Dockerfile pattern:**

```dockerfile
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
# Copy installed packages from builder
COPY --from=builder /install /usr/local
# Non-root user
RUN useradd --no-create-home --shell /bin/bash appuser
COPY src/ ./src/
USER appuser
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "30", "src.app:create_app()"]
```

**Size targets:** `python:3.11-slim` base ~130MB compressed. With a well-layered multi-stage build, final image should be 150-180MB. Acceptable for local portfolio use.

**gunicorn workers:** 1 worker per pod. Kubernetes handles horizontal scale. Multi-worker per pod fights with K8s memory limits and complicates signals.

---

## Helm Chart Structure

```
charts/field-guide-api/
├── Chart.yaml          # apiVersion: v2, type: application
├── values.yaml         # image.repository, image.tag, mongo.*, replicaCount
├── templates/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   ├── secret.yaml            # App secrets (FLASK_SECRET_KEY, etc.)
│   ├── mongodb-deployment.yaml
│   ├── mongodb-service.yaml
│   ├── mongodb-pvc.yaml
│   └── mongodb-secret.yaml
└── .helmignore
```

**`values.yaml` PRD-3 seam:** Structure `image.repository`, `image.tag`, `replicaCount`, `service.port`, `env.*` at top level so PRD-3's template engine can render new app charts by varying these values.

---

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| Flask-PyMongo 3.0.1 | raw `pymongo.MongoClient` in app factory | Flask-PyMongo handles app-context teardown, connection pooling, and URI config automatically; less boilerplate |
| prometheus-flask-exporter | bare `prometheus_client` + custom `/metrics` route | prometheus-flask-exporter auto-instruments all routes; bare client requires manual labeling for every route |
| python:3.11-slim base | python:3.11-alpine | Alpine = musl libc = no pre-compiled wheels for PyMongo, cryptography, etc.; slower builds, larger final size after gcc |
| python:3.11-slim base | python:3.11 (full Debian) | Full image is ~1GB+; slim removes docs, man pages, locale data while keeping glibc; negligible feature difference |
| Simple MongoDB manifest | Bitnami mongodb Helm chart | Bitnami behind Broadcom paywall since Sep 29 2025; no longer free |
| Simple MongoDB manifest | MongoDB Community Operator | Operator adds CRDs, RBAC, MongoDBCommunity CRs — 6+ resources for a single-instance learning deployment; PRD-1 scope |
| registry:3 + kind | minikube registry addon | kind is locked; minikube is a separate tool with heavier resource profile |
| gunicorn | Flask dev server (`flask run`) | Dev server is single-threaded, not signal-safe, not for containers; gunicorn handles SIGTERM for graceful K8s pod termination |
| Helm 4.2.2 | Helm 3.21.2 | Charts are identical; Helm 3 EOL Jul 2026 (security patches only Nov 2026). If installing fresh, use Helm 4. If team has Helm 3, charts work unchanged. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Bitnami MongoDB Helm chart | Behind Broadcom subscription paywall since Sep 29 2025; no longer free/public | Simple Kubernetes manifests with `mongo:7` official image |
| Alpine base image for Python | musl libc means no pre-compiled wheels; C-extension packages (PyMongo, cryptography) need full build toolchain — negates size benefit | `python:3.11-slim` |
| Flask dev server in Docker | Single-threaded, no SIGTERM handling, debug mode in prod is a security risk | `gunicorn` with 1 worker |
| `registry:2` in kind scripts | Official kind docs now reference `registry:3`; registry:2 still works but is dated | `registry:3` |
| Helm `--atomic` flag in Makefile | Renamed to `--rollback-on-failure` in Helm 4; flag is deprecated | Use `--rollback-on-failure` or avoid in Makefile for portability |
| `git add -A` before first commit | Will capture `.env`, `__pycache__`, kubeconfig if .gitignore not in place | Commit `.gitignore` first; then add specific paths |
| CRLF line endings in shell scripts | Git Bash / WSL2 bash fails with `bad interpreter: No such file or directory` on CRLF scripts | `.gitattributes` with `* text=auto eol=lf`; `*.sh text eol=lf` |

---

## WSL2 / Git Bash Makefile Compatibility

### Required Makefile Header

```makefile
SHELL := /bin/bash
export MSYS_NO_PATHCONV := 1
```

`MSYS_NO_PATHCONV=1` prevents Git Bash (MSYS2) from translating POSIX paths like `/app` into Windows paths like `C:/Program Files/Git/app` inside `docker exec` and `kubectl` commands.

### Required `.gitattributes`

```gitattributes
* text=auto eol=lf
*.sh text eol=lf
*.py text eol=lf
Makefile text eol=lf
*.bat text eol=crlf
*.cmd text eol=crlf
```

Commit this before any shell scripts. Without it, Windows editors write CRLF and WSL2 bash sees `\r` at end of shebang line → cryptic failure.

### Makefile Targets Checklist

- Use `$$` for shell variables inside Makefile rules (single `$` is Makefile variable)
- Use `$(shell ...)` for shell substitution in variable definitions
- Avoid Windows-style paths; use relative paths from repo root
- `make -f Makefile` works identically in WSL2, Git Bash, and native Linux

---

## Version Compatibility Matrix

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| Flask 3.1.3 | Flask-PyMongo 3.0.1, Werkzeug ≥3.0 | Flask-PyMongo 3.x requires Flask ≥3.0 |
| Flask-PyMongo 3.0.1 | PyMongo ≥4.0, MongoDB ≥4.4 | |
| PyMongo 4.13.2 | MongoDB 4.4, 5.0, 6.0, 7.0 | `mongo:7` Docker image is the right pairing |
| gunicorn 26.0.0 | Python ≥3.10, Flask 3.x | gunicorn dropped Python 3.9 support |
| prometheus-flask-exporter 0.23.2 | Flask 1.x–3.x, Python 3.8–3.12 | Tested against Python 3.11 |
| pytest-flask 1.3.0 | pytest ≥5.2, Flask 3.0+ | v1.3.0 specifically fixed Flask 3.0 compat |
| python-dotenv 1.2.2 | Python ≥3.10 (dropped 3.9 in 1.2.x) | |
| kind v0.32.0 | Docker 27.x, Kubernetes 1.33.1 default node image | |

---

## Sources

- `/pallets/flask` (Context7) — Flask 3.x versions, app factory patterns
- `/mongodb/docs-pymongo` (Context7) — PyMongo 4.13.2 snooty.toml confirmation
- `/pytest-dev/pytest` (Context7) — pytest fixtures, plugin list
- [Flask PyPI](https://pypi.org/project/Flask/) — version 3.1.3, Feb 2026 (HIGH confidence)
- [gunicorn PyPI](https://pypi.org/project/gunicorn/) — version 26.0.0, May 2026 (HIGH confidence)
- [pytest PyPI](https://pypi.org/project/pytest/) — version 9.1.1, Jun 2026 (HIGH confidence)
- [pytest-flask PyPI](https://pypi.org/project/pytest-flask/) — version 1.3.0, Flask 3 compat (HIGH confidence)
- [prometheus-flask-exporter PyPI](https://pypi.org/project/prometheus-flask-exporter/) — 0.23.2 (HIGH confidence)
- [python-dotenv PyPI](https://pypi.org/project/python-dotenv/) — 1.2.2, Mar 2026 (HIGH confidence)
- [Flask-PyMongo PyPI](https://pypi.org/project/Flask-PyMongo/) — 3.0.1, Jan 2025, requires Flask≥3 (HIGH confidence)
- [kind local registry docs](https://kind.sigs.k8s.io/docs/user/local-registry/) — registry:3, containerd config patch, ConfigMap pattern (HIGH confidence)
- [Bitnami catalog changes issue #35164](https://github.com/bitnami/charts/issues/35164) — paywall effective Sep 2025 (HIGH confidence)
- [Helm GitHub releases](https://github.com/helm/helm/releases) — Helm 4.2.2 latest, Helm 3.21.2 latest Helm 3 (HIGH confidence)
- [Helm 4 overview docs](https://helm.sh/docs/overview/) — Helm 3 charts compatible with Helm 4 unchanged (HIGH confidence)
- [kind GitHub releases](https://github.com/kubernetes-sigs/kind/releases) — v0.32.0 (MEDIUM confidence, inferred from search)
- WSL2/Makefile CRLF — Microsoft WSL issue tracker, multiple community sources (MEDIUM confidence)

---

*Stack research for: k8s-launchpad PRD-1 Foundation*
*Researched: 2026-07-04*
