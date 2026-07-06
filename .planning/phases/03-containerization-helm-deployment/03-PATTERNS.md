# Phase 3: Containerization + Helm Deployment - Pattern Map

**Mapped:** 2026-07-05
**Files analyzed:** 15 (14 new + 1 modified)
**Analogs found:** 8 / 15 (7 chart/docker files have no in-repo analog — RESEARCH.md Patterns 1–5 are the authoritative source for those)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `apps/field-guide-api/Dockerfile` (NEW) | config (image build) | batch (build-time) | none in repo — RESEARCH.md Pattern 1 is verbatim | none (research-backed) |
| `apps/field-guide-api/.dockerignore` (NEW) | config | batch | `.gitignore` | role-match |
| `charts/field-guide-api/Chart.yaml` (NEW) | config | — | `infra/kind/kind-config.yaml` (header style only) | partial |
| `charts/field-guide-api/values.yaml` (NEW) | config | — | `apps/field-guide-api/.env.example` (dev-default + security-comment discipline) | partial |
| `charts/field-guide-api/.helmignore` (NEW) | config | — | `.gitignore` | role-match |
| `charts/.../templates/_helpers.tpl` (NEW) | utility (template helpers) | transform | none — standard Helm `_helpers.tpl` (RESEARCH.md blesses reusing `helm create` naming conventions only) | none |
| `charts/.../templates/NOTES.txt` (NEW) | docs | — | `scripts/cluster-setup.sh` usage-header style | partial |
| `charts/.../templates/deployment.yaml` (NEW, app) | k8s manifest | request-response runtime | env contract from `app/config.py` + probes from `app/routes/health.py`; RESEARCH.md Pattern 5 + Code Examples | partial |
| `charts/.../templates/service.yaml` (NEW) | k8s manifest | request-response | none — trivial ClusterIP; RESEARCH.md values schema | none |
| `charts/.../templates/configmap.yaml` (NEW) | k8s manifest | config injection | `scripts/cluster-setup.sh` lines 94–104 (in-repo ConfigMap example) | partial |
| `charts/.../templates/secret.yaml` (NEW) | k8s manifest | config injection | none — RESEARCH.md Pattern 4 (live-verified URI) is verbatim | none (research-backed) |
| `charts/.../templates/mongodb/deployment.yaml` (NEW) | k8s manifest | CRUD backend runtime | none — RESEARCH.md Pattern 5 (mongo probe) + HELM-03 | none (research-backed) |
| `charts/.../templates/mongodb/service.yaml` (NEW) | k8s manifest | request-response | none | none |
| `charts/.../templates/mongodb/pvc.yaml` + `mongodb/secret.yaml` (NEW) | k8s manifest | file-I/O / config injection | none — RESEARCH.md (storageClass `""`, `stringData`) | none (research-backed) |
| `Makefile` (MODIFIED — add `build`/`load`/`deploy`/`undeploy`) | config (task runner) | batch | existing `Makefile` targets | exact |

Also touched implicitly: `charts/field-guide-api/.gitkeep` is **deleted** when real chart files land.

## Pattern Assignments

### `Makefile` (MODIFIED — build/load/deploy/undeploy targets)

**Analog:** `E:\Genspark\k8s-launchpad\Makefile` (exact — extend in place)

**Header + phase-comment + .PHONY pattern** (lines 1–11) — new targets must be added to `.PHONY` and the phase comment updated:

```makefile
SHELL := /bin/bash
export MSYS_NO_PATHCONV=1
...
# ─── Targets ──────────────────────────────────────────────────────────────────
# Phase 1: test only | Phase 2: cluster-up, cluster-down | Phase 3+: build, load, deploy
.PHONY: test cluster-up cluster-down
```

**Target doc-comment + recipe style** (lines 13–27) — each target has a `## name: description` comment line; multi-command recipes chain with `&& \`; shell vars use `$$`:

```makefile
## test: create local venv (idempotent), install dev-deps, run pytest with coverage
test:
	cd apps/field-guide-api && \
	{ [ -d .venv ] || $(PYTHON) -m venv .venv; } && \
	VENV_PY=$$([ -x .venv/bin/python ] && echo .venv/bin/python || echo .venv/Scripts/python) && \
	"$$VENV_PY" -m pip install -q -r requirements-dev.txt && \
	"$$VENV_PY" -m pytest

## cluster-up: create kind cluster + local registry (idempotent)
cluster-up:
	bash scripts/cluster-setup.sh
```

Two delegation styles exist: inline one-liners (`test`) and script delegation (`cluster-up`/`cluster-down`). RESEARCH.md Open Question 1 recommends **inline one-liners** for `build`/`load`/`deploy`/`undeploy` (wrapping Pattern 6 commands: `docker build`, `docker push`, `helm upgrade --install ... --wait`, `helm uninstall`). Overridable variables follow the `PYTHON ?= python3` pattern (line 7) — e.g. `IMAGE ?= localhost:5001/field-guide-api`, `TAG ?= dev`, `RELEASE ?= field-guide-api`. Never use `--atomic` (banned; removed from `helm install` in Helm 4).

---

### `apps/field-guide-api/.dockerignore` (NEW)

**Analog:** `E:\Genspark\k8s-launchpad\.gitignore` (role-match — same exclusion vocabulary, commented sections)

**Exclusion-list pattern** (`.gitignore` lines 1–29): grouped entries with `#` section comments, trailing-slash directories:

```
# Secrets and local config — NEVER commit real credentials
.env
...
# Virtual environments
.venv/
...
# Testing and coverage
.pytest_cache/
.coverage
```

RESEARCH.md Pattern 2 gives the exact content list (`.venv/`, `.pytest_cache/`, `__pycache__/`, `**/__pycache__/`, `*.pyc`, `.coverage`, `.env`, `tests/`). Confirmed on disk this session: `apps/field-guide-api/.venv/`, `.pytest_cache/`, `.coverage`, and `app/__pycache__/` all exist inside the build context — the .dockerignore is load-bearing, not hygiene. Keep the `.gitignore`-style section comments.

---

### `apps/field-guide-api/Dockerfile` (NEW)

**Analog:** none in repo. Use RESEARCH.md Pattern 1 verbatim (multi-stage `python:3.11-slim`, `USER 10001`, exec-form gunicorn CMD, `--workers 1 --threads 4`, port 8000).

**Repo facts the Dockerfile must match:**

`wsgi.py` (lines 9–11) — the gunicorn target `wsgi:app` already exists; COPY exactly `app/` and `wsgi.py`:

```python
from app import create_app

app = create_app()
```

`requirements.txt` (lines 3–8) — pinned runtime deps the builder stage installs (gunicorn 26.0.0 is already in this file; no dev deps in the image):

```
Flask==3.1.3
Flask-PyMongo==3.0.1
pymongo==4.13.2
gunicorn==26.0.0
prometheus-flask-exporter==0.23.2
python-dotenv==1.2.2
```

**File-header convention** (shared pattern below): start with a comment block stating purpose + source citation, as in `infra/kind/kind-config.yaml` lines 1–2 and `scripts/cluster-setup.sh` lines 1–7.

---

### `charts/field-guide-api/templates/deployment.yaml` (app) (NEW)

**Analog:** partial — env-var contract and probe semantics come from the app source; template syntax from RESEARCH.md Code Examples.

**Env-var contract** — `app/config.py` lines 30–37 define the exact names the Deployment must inject (`MONGO_URI` from Secret; `MONGO_DBNAME`, `FLASK_DEBUG` from ConfigMap):

```python
MONGO_URI: str = os.environ.get(
    "MONGO_URI", "mongodb://localhost:27017/fieldguide"
)
MONGO_DBNAME: str = os.environ.get("MONGO_DBNAME", "fieldguide")

# Debug mode is opt-in via FLASK_DEBUG=1/true/yes/on; default is False.
DEBUG: bool = _env_flag("FLASK_DEBUG")
```

`_env_flag` (config.py lines 17–24) treats empty string as disabled — so `FLASK_DEBUG: ""` in the ConfigMap is safe and correct.

**Probe semantics** — `app/routes/health.py` lines 26–33 (readinessProbe target; returns 503 within ~2s when Mongo is down thanks to `MONGO_SERVER_SELECTION_TIMEOUT_MS=2000` set in `app/__init__.py` lines 46–50):

```python
@health_bp.route("/health", methods=["GET"])
def health():
    try:
        mongo.cx.admin.command("ping")
        return jsonify({"status": "ok", "mongo": "up"}), 200
    except Exception:
        return jsonify({"status": "unavailable", "mongo": "down"}), 503
```

Readiness = httpGet `/health:8000`; liveness = tcpSocket 8000 (NEVER `/health` — RESEARCH.md Pattern 5). Container port 8000 matches the Dockerfile CMD bind. securityContext: `runAsNonRoot: true`, `runAsUser: 10001`, `allowPrivilegeEscalation: false` (matches Dockerfile `USER 10001`).

---

### `charts/field-guide-api/templates/configmap.yaml` (NEW)

**Analog:** `E:\Genspark\k8s-launchpad\scripts\cluster-setup.sh` lines 94–104 — the only ConfigMap in the repo; shows the project's minimal-manifest style (no annotations cruft):

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:${reg_port}"
    help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
```

Chart version replaces literal name/namespace with `{{ include "field-guide-api.fullname" . }}` + helper labels; keys are `MONGO_DBNAME` and `FLASK_DEBUG` from values `config.mongoDbName` / `config.flaskDebug`.

---

### `charts/field-guide-api/values.yaml` (NEW)

**Analog:** `E:\Genspark\k8s-launchpad\apps\field-guide-api\.env.example` (partial — the project's established "dev-only default + explicit warning comment" discipline):

```
# Copy this file to .env and fill in real values for local development.
# The .env file is listed in .gitignore — NEVER commit real credentials.

# MongoDB connection URI. For local dev, point at the Docker Compose or
# local MongoDB instance. In-cluster, this is supplied via a Kubernetes Secret.
MONGO_URI=mongodb://localhost:27017/fieldguide

# MUST be empty (or unset/0) in containers and Kubernetes deployments.
FLASK_DEBUG=
```

Apply the same commenting voice to values.yaml: the `mongodb.auth.password: fieldguide-dev-password` default must carry a comment saying "local kind only; never a real credential — override with --set for anything real". Content schema is RESEARCH.md Pattern 3 verbatim (image.*, service.*, resources, metrics.enabled, config.*, mongodb.* with `enabled` toggle, `pullPolicy: IfNotPresent` locked by HELM-04).

---

### `charts/field-guide-api/templates/secret.yaml` + `templates/mongodb/*` (NEW)

**Analog:** none in repo. Use RESEARCH.md verbatim:
- Pattern 4 for the app Secret — `stringData` (never `data`), canonical URI with `?authSource=admin` and DB name in path (both live-verified; omitting either breaks the app)
- mongodb Deployment: `mongo:7`, `MONGO_INITDB_ROOT_USERNAME/PASSWORD` from its own Secret, readinessProbe `mongosh --quiet --eval "db.adminCommand('ping')"` (auth-free, live-verified)
- mongodb pvc: `storageClass: ""` → cluster default; Deployment-owned PVC, NOT StatefulSet (uninstall must remove it)
- All mongodb templates gated on `{{- if .Values.mongodb.enabled }}`

**Critical single-source-of-truth rule** (RESEARCH.md Pitfall 9): the mongodb Service `metadata.name` and the hostname inside the Secret's `MONGO_URI` must both come from the SAME helper in `_helpers.tpl` (e.g. `field-guide-api.mongodb.fullname`). Never write the hostname twice.

---

### `charts/field-guide-api/Chart.yaml`, `.helmignore`, `_helpers.tpl`, `NOTES.txt` (NEW)

**Analog:** none in repo (charts/ holds only `.gitkeep`). Constraints from RESEARCH.md:
- `Chart.yaml`: `apiVersion: v2` (Helm-3-compatible; installed CLI is Helm 4.2.1), `version: 0.1.0`. Add the repo's standard header comment (purpose line).
- `_helpers.tpl`: standard `helm create` naming conventions ONLY — name/fullname/labels/selectorLabels + a mongodb-fullname helper. The scaffold's fullname helper collapses release `field-guide-api` + chart `field-guide-api` to `field-guide-api` (RESEARCH.md Open Question 2 recommends that release name).
- `NOTES.txt`: port-forward + curl instructions; mirror the `Usage:` block style of `scripts/cluster-setup.sh` lines 5–7.
- `.helmignore`: standard content; `.gitignore`-style comments.

---

## Shared Patterns

### File-header comment with purpose + source citation
**Source:** `scripts/cluster-setup.sh` lines 1–7, `infra/kind/kind-config.yaml` lines 1–2, every Python module docstring
**Apply to:** Dockerfile, .dockerignore, Chart.yaml, values.yaml, every template

```bash
#!/usr/bin/env bash
# scripts/cluster-setup.sh
# Idempotent kind cluster + local registry setup with end-to-end wiring verification.
# Source: https://kind.sigs.k8s.io/docs/user/local-registry/
#
# Usage:  bash scripts/cluster-setup.sh
#         make cluster-up
```

### Idempotency: check-then-act with "— skipping." echo
**Source:** `scripts/cluster-setup.sh` lines 44–61 (registry), 64–70 (cluster), 85–90 (network); `scripts/cluster-teardown.sh` lines 23–33
**Apply to:** Makefile `deploy` (use `helm upgrade --install` — natively idempotent) and `undeploy` (guard like teardown, or rely on `helm uninstall --ignore-not-found` style behavior)

```bash
if ! kind get clusters 2>/dev/null | grep -q '^kind$'; then
  kind create cluster --config infra/kind/kind-config.yaml
  echo "    Cluster created."
else
  echo "    Cluster already exists — skipping."
fi
```

### kubectl context pinning
**Source:** `scripts/cluster-setup.sh` lines 17–20
**Apply to:** every `kubectl` invocation in new Makefile targets / verification steps

```bash
# Pin every kubectl call to the kind cluster's context so an idempotent
# re-run ... can never mutate whatever cluster the user's kubeconfig
# currently points at.
KCTX='--context=kind-kind'
```

### Self-verifying steps that surface real failure causes
**Source:** `scripts/cluster-setup.sh` lines 107–129 (push → run pod → wait on phase → on timeout, dump events, clean up, exit 1)
**Apply to:** deploy verification (helm `--wait` failure handling, port-forward smoke test)

```bash
if ! kubectl ${KCTX} wait --for=jsonpath='{.status.phase}'=Succeeded pod/registry-verify --timeout=60s; then
  echo "ERROR: registry verification failed — pod status:"
  kubectl ${KCTX} describe pod registry-verify | sed -n '/Events:/,$p'
  kubectl ${KCTX} delete pod registry-verify --ignore-not-found
  exit 1
fi
```

Progress echo convention throughout: `echo "==> Step N: ..."` for steps, four-space-indented `echo "    detail"` for outcomes.

### Secrets discipline
**Source:** `.gitignore` lines 1–4, `.env.example` header, `app/config.py` lines 28–32 ("Never embed a real URI or password here")
**Apply to:** values.yaml (labeled dev default only), secret.yaml (MONGO_URI lives ONLY here — never in ConfigMap, Dockerfile ENV, or NOTES.txt output)

### LF line endings — already enforced, no action needed
**Source:** `.gitattributes` lines 3–13
**Apply to:** all new files. `*.yaml`, `*.yml`, `*.sh` have explicit rules; `Dockerfile`, `.dockerignore`, `_helpers.tpl`, `NOTES.txt` are covered by `* text=auto eol=lf` (line 3). No .gitattributes change required.

## No Analog Found

Files with no close in-repo match (planner uses RESEARCH.md patterns instead — all are fully concrete there):

| File | Role | Data Flow | Reason | RESEARCH.md Source |
|------|------|-----------|--------|--------------------|
| `apps/field-guide-api/Dockerfile` | image build | batch | First Dockerfile in the repo | Pattern 1 (verbatim) |
| `charts/.../templates/secret.yaml` | k8s manifest | config injection | First Secret template | Pattern 4 (live-verified URI) |
| `charts/.../templates/mongodb/*.yaml` | k8s manifests | CRUD/file-I/O | First DB manifests | Pattern 5 + HELM-03 + Pitfalls 4, 7, 9 |
| `charts/.../Chart.yaml`, `_helpers.tpl`, `service.yaml`, `.helmignore`, `NOTES.txt` | chart plumbing | — | First Helm chart | Structure section + standard `helm create` naming conventions only (scaffold itself rejected) |

## Metadata

**Analog search scope:** repo root, `apps/field-guide-api/` (app/, routes/, tests/ excluded from excerpts — no Python changes this phase), `scripts/`, `infra/`, `charts/`
**Files scanned:** 12 read in full (Makefile, cluster-setup.sh, cluster-teardown.sh, kind-config.yaml, app/__init__.py, config.py, extensions.py, wsgi.py, routes/health.py, requirements.txt, .gitattributes, .gitignore, .env.example)
**Key repo facts confirmed on disk:** `apps/field-guide-api/.venv/` + `.pytest_cache/` + `.coverage` + `__pycache__/` exist inside the Docker build context (validates .dockerignore criticality); `charts/field-guide-api/` contains only `.gitkeep`; no Dockerfile, docker-compose.yml, or Helm chart exists anywhere in the repo
**Pattern extraction date:** 2026-07-05
