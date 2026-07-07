---
phase: 03-containerization-helm-deployment
verified: 2026-07-07T00:00:00Z
status: passed
score: 5/5
overrides_applied: 0
re_verification: false
---

# Phase 3: Containerization + Helm Deployment Verification Report

**Phase Goal:** The field-guide API runs as a gunicorn container in the kind cluster, reachable locally, backed by in-cluster MongoDB deployed via plain mongo:7 manifests inside the Helm chart
**Verified:** 2026-07-07T00:00:00Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | docker build produces a working image; container runs as non-root and is served by gunicorn (not Flask dev server) | VERIFIED | Dockerfile: multi-stage `python:3.11-slim`, `USER 10001` numeric, exec-form `CMD ["gunicorn", ...]` targeting `wsgi:app`. No `flask run` or `FLASK_DEBUG` ENV anywhere. Live: build context 9.85kB, `id -u` → `10001`, PID 1 = gunicorn. |
| 2 | helm lint passes; helm install deploys both app and MongoDB to the kind cluster without errors | VERIFIED | `helm lint` exit 0 (only INFO: icon). `make deploy` reached Ready; both `field-guide-api` and `field-guide-api-mongodb` pods 1/1 Running. Post-fix re-deploy confirmed with fixed chart. |
| 3 | Deployed app responds at /health (200) and returns entries from /entries via port-forward | VERIFIED | Orchestrator re-verified post CR-01 fix: `kubectl port-forward svc/field-guide-api 8080:80` + curl → HTTP 200 on `/health` (`{"status":"ok","mongo":"up"}`), `/entries` (`[]`), `/metrics` (Prometheus text). 4/4 consecutive 200s. |
| 4 | MongoDB runs as plain mongo:7 manifests embedded in chart templates; helm uninstall removes all resources cleanly | VERIFIED | Templates: `mongodb/deployment.yaml` (`image: "mongo:7"`, plain Deployment not StatefulSet), `/service.yaml`, `/pvc.yaml`, `/secret.yaml` — all gated on `mongodb.enabled`. No Bitnami references. `make undeploy` → labeled resource query returns empty (PVC gone). |
| 5 | values.yaml is generic (image.*, service.*, resources, secrets, metrics.enabled, imagePullPolicy: IfNotPresent) and structured for PRD-3 templating | VERIFIED | values.yaml contains `pullPolicy: IfNotPresent` (HELM-04 locked), `replicaCount`, `image.*`, `service.*`, `resources.*`, `metrics.enabled`, `config.*`, `mongodb.*` with enabled toggle, `externalMongoUri` seam for DB-less apps. |

**Score:** 5/5 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/field-guide-api/Dockerfile` | Multi-stage python:3.11-slim, non-root UID 10001, gunicorn CMD | VERIFIED | Two `FROM python:3.11-slim` stages; `groupadd/useradd` UID 10001; exec-form `CMD ["gunicorn", "--bind", "0.0.0.0:8000", ..., "wsgi:app"]` |
| `apps/field-guide-api/.dockerignore` | Excludes .venv/, tests/, .env, caches | VERIFIED | Contains exact lines `.venv/`, `.pytest_cache/`, `__pycache__/`, `**/__pycache__/`, `*.pyc`, `.coverage`, `.env`, `tests/` |
| `charts/field-guide-api/Chart.yaml` | apiVersion v2, Helm-3 compatible | VERIFIED | `apiVersion: v2`, `name: field-guide-api`, `version: 0.1.0` |
| `charts/field-guide-api/values.yaml` | Generic PRD-3 seam with IfNotPresent | VERIFIED | All HELM-04 fields present; `pullPolicy: IfNotPresent` locked; `externalMongoUri` seam; dev password with override comment |
| `charts/field-guide-api/templates/_helpers.tpl` | name/fullname/labels/selectorLabels + mongodb helpers | VERIFIED | Defines `field-guide-api.fullname`, `field-guide-api.mongodb.fullname`, and (CR-01 fix) `field-guide-api.mongodb.selectorLabels` with distinct `name: field-guide-api-mongodb` identity |
| `charts/field-guide-api/templates/deployment.yaml` | App Deployment with Secret+ConfigMap env, probes, securityContext | VERIFIED | `secretKeyRef` MONGO_URI, `configMapKeyRef` MONGO_DBNAME/FLASK_DEBUG; readinessProbe httpGet `/health:8000` (timeoutSeconds:3); livenessProbe tcpSocket; `runAsNonRoot: true`, `runAsUser: 10001`, `allowPrivilegeEscalation: false`; checksum annotations |
| `charts/field-guide-api/templates/secret.yaml` | MONGO_URI with authSource=admin, stringData, Secret-only | VERIFIED | `stringData` MONGO_URI with `urlquery` encoding, `?authSource=admin&serverSelectionTimeoutMS=2000`; branches on `mongodb.enabled` for external URI |
| `charts/field-guide-api/templates/service.yaml` | ClusterIP Service 80→8000, correct selector | VERIFIED | `type: ClusterIP`, `port: 80`, `targetPort: 8000`; selector uses `field-guide-api.selectorLabels` → `name=field-guide-api` only |
| `charts/field-guide-api/templates/configmap.yaml` | MONGO_DBNAME + FLASK_DEBUG only, no MONGO_URI | VERIFIED | `data: MONGO_DBNAME` + `FLASK_DEBUG`; `MONGO_URI` absent (confirmed by grep) |
| `charts/field-guide-api/templates/mongodb/deployment.yaml` | Plain mongo:7 Deployment, NOT StatefulSet, gated | VERIFIED | `kind: Deployment`, `image: "mongo:7"`, `strategy: {type: Recreate}`, gated on `mongodb.enabled`, uses `mongodb.selectorLabels` |
| `charts/field-guide-api/templates/mongodb/service.yaml` | ClusterIP :27017, name from mongodb.fullname helper | VERIFIED | `type: ClusterIP`, port 27017; `metadata.name` from `field-guide-api.mongodb.fullname`; selector from `field-guide-api.mongodb.selectorLabels` |
| `charts/field-guide-api/templates/mongodb/pvc.yaml` | ReadWriteOnce 1Gi, storageClass conditional | VERIFIED | `accessModes: [ReadWriteOnce]`, `storage: 1Gi`; `storageClassName` omitted when value empty |
| `charts/field-guide-api/templates/mongodb/secret.yaml` | MONGO_INITDB_ROOT_* in stringData, gated | VERIFIED | `stringData: MONGO_INITDB_ROOT_USERNAME/PASSWORD`; gated on `mongodb.enabled` |
| `Makefile` | build/load/deploy/undeploy targets, IMAGE/TAG vars, no --atomic | VERIFIED | Four targets in `.PHONY`; `IMAGE ?=`, `TAG ?=`, `RELEASE ?=`, `CHART ?=` overridable; `deploy` passes `--set image.repository=$(IMAGE) --set image.tag=$(TAG)`; zero `--atomic` occurrences |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `Dockerfile` | `wsgi:app` | exec-form gunicorn CMD | VERIFIED | CMD array: `["gunicorn", ..., "wsgi:app"]` — gunicorn is PID 1 |
| `Dockerfile` | `USER 10001` | numeric non-root directive | VERIFIED | `groupadd -r -g 10001 app && useradd -r -u 10001 -g app app; USER 10001` |
| `templates/secret.yaml` | `templates/mongodb/service.yaml` | shared `mongodb.fullname` helper | VERIFIED | Both reference `{{ include "field-guide-api.mongodb.fullname" . }}` — hostname and service name cannot drift |
| `templates/deployment.yaml` | `templates/secret.yaml` | `secretKeyRef` MONGO_URI | VERIFIED | `env[0]: name: MONGO_URI, valueFrom: secretKeyRef` |
| `templates/deployment.yaml` | `templates/configmap.yaml` | `configMapKeyRef` MONGO_DBNAME/FLASK_DEBUG | VERIFIED | Two env entries with `configMapKeyRef` |
| `templates/service.yaml` | API pods only (not mongodb) | `selectorLabels` distinct identity | VERIFIED | Service selector `name=field-guide-api`; mongodb pods labeled `name=field-guide-api-mongodb` via `mongodb.selectorLabels` helper — CR-01 fixed and re-verified live |
| `Makefile:build` | `apps/field-guide-api/Dockerfile` | docker build context | VERIFIED | `docker build -t $(IMAGE):$(TAG) apps/field-guide-api` |
| `Makefile:deploy` | `charts/field-guide-api` | helm upgrade --install | VERIFIED | `helm upgrade --install $(RELEASE) $(CHART) --set image.repository=$(IMAGE) --set image.tag=$(TAG) --wait --timeout 180s` |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|-------------------|--------|
| `deployment.yaml` | `MONGO_URI` env | `secret.yaml` stringData (templated from values.yaml) | Yes — URI with live-verified shape rendered at `helm install` | FLOWING |
| Running app pod | `/health` response | App health route → PyMongo `admin.command("ping")` | Yes — returns `{"status":"ok","mongo":"up"}` from live MongoDB | FLOWING |
| Running app pod | `/entries` response | App entries routes → PyMongo `mongo.db.entries.find()` | Yes — POST+GET CRUD round-trip proven live (201 + 200 with persisted doc) | FLOWING |
| Running app pod | `/metrics` response | `prometheus-flask-exporter` | Yes — Prometheus-format text with `python_gc_*`, `process_*`, `flask_exporter_info` metrics | FLOWING |

---

### Behavioral Spot-Checks

| Behavior | Evidence Source | Result | Status |
|----------|----------------|--------|--------|
| `make build` produces `localhost:5001/field-guide-api:dev` | 03-04-SUMMARY check #2 | Build context 9.85kB; image tagged correctly | PASS |
| `make load` pushes to localhost:5001 | 03-04-SUMMARY check #3 | `docker push` succeeded, digest sha256:1293ed58... | PASS |
| `helm lint charts/field-guide-api` exits 0 | 03-04-SUMMARY check #4 | 1 chart linted, 0 failed | PASS |
| `make deploy` deploys app + MongoDB Running | 03-04-SUMMARY check #5 | Both pods 1/1 Running | PASS |
| Container UID 10001 at runtime | 03-04-SUMMARY check #6; live exec | `kubectl exec -l app.kubernetes.io/name=field-guide-api -- id -u` → `10001` | PASS |
| gunicorn PID 1 at runtime | 03-04-SUMMARY check #7 | `cat /proc/1/cmdline` → `gunicorn --bind 0.0.0.0:8000 --workers 1 ...` | PASS |
| `/health` → HTTP 200 via port-forward | Orchestrator re-verification post CR-01 fix | `curl localhost:8080/health` → `{"status":"ok","mongo":"up"}`; 4/4 consecutive 200s | PASS |
| `/entries` → valid JSON via port-forward | Orchestrator re-verification | `curl localhost:8080/entries` → `[]` | PASS |
| `/metrics` → Prometheus text via port-forward | Orchestrator re-verification | Prometheus-format text confirmed | PASS |
| `make undeploy` removes all resources incl. PVC | 03-04-SUMMARY check #9 | Labeled resource query returns "No resources found" | PASS |
| `make test` → 32 passed, 100% coverage | 03-04-SUMMARY check #10; post-fix confirmation | 32 passed, 100% coverage (95% threshold met) | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| IMG-01 | 03-01, 03-04 | Dockerfile builds a small working image (python:3.11-slim base, non-root user) | SATISFIED | `Dockerfile`: `FROM python:3.11-slim` (two stages), `USER 10001`; live build at 9.85kB context |
| IMG-02 | 03-01, 03-04 | Image serves via gunicorn (graceful SIGTERM handling), never the Flask dev server | SATISFIED | Exec-form CMD with `gunicorn`; PID 1 = gunicorn confirmed live; no `flask run` or `FLASK_DEBUG` anywhere |
| HELM-01 | 03-02, 03-04 | Helm chart with Deployment/Service/ConfigMap/Secret and values.yaml; helm lint passes | SATISFIED | All 8 templates exist; `helm lint` exit 0; `Chart.yaml` apiVersion v2 |
| HELM-02 | 03-03, 03-04 | Deployed app is reachable locally and returns data from /health and field-guide endpoints | SATISFIED | Port-forward + curl confirmed HTTP 200 on /health, /entries, /metrics by orchestrator re-verification |
| HELM-03 | 03-02, 03-04 | MongoDB runs in-cluster via plain mongo:7 official-image manifests embedded in the chart (NOT Bitnami) | SATISFIED | Four mongodb templates (Deployment/Service/PVC/Secret) using `mongo:7`; no Bitnami; clean uninstall confirmed |
| HELM-04 | 03-02 | values.yaml is generic (image.*, service.*, resources, metrics.enabled, imagePullPolicy: IfNotPresent) for PRD-3 | SATISFIED | `values.yaml` contains all required fields; `pullPolicy: IfNotPresent` locked; `externalMongoUri` seam added |

**Orphaned requirements check:** REQUIREMENTS.md maps IMG-01, IMG-02, HELM-01, HELM-02, HELM-03, HELM-04 to Phase 3. All six are claimed and satisfied by plans 03-01 through 03-04. No orphaned requirements.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| — | — | — | — | No anti-patterns found in any phase-3-modified file |

Scanned: `apps/field-guide-api/Dockerfile`, `apps/field-guide-api/.dockerignore`, `Makefile`, all `charts/field-guide-api/**` templates.
No `TBD`, `FIXME`, `XXX`, `TODO`, `HACK`, `PLACEHOLDER`, stub patterns, or hardcoded empty return values found.

---

### Code Review Resolution (Post-Execution)

The 03-REVIEW.md identified 1 Critical + 7 Warnings. All 8 are resolved per 03-REVIEW-FIX.md (commits 4223b4f..f82f42e). Key verification:

| Finding | Resolution | Codebase Evidence |
|---------|------------|------------------|
| CR-01: API Service selector matched MongoDB pod | Added `field-guide-api.mongodb.selectorLabels` helper with `name=field-guide-api-mongodb`; used in mongodb Deployment and Service | `_helpers.tpl` line 84-87; `mongodb/deployment.yaml` uses `mongodb.selectorLabels`; `service.yaml` selector unchanged (`name=field-guide-api` only) |
| WR-01: `mongodb.enabled=false` broken URI | `externalMongoUri` value + branched `secret.yaml` with `required` guard | `values.yaml` `externalMongoUri: ""`; `secret.yaml` if/else on `mongodb.enabled` with `required` |
| WR-02: URI without URL-encoding | `urlquery` pipe on username and password | `secret.yaml` line 24: `{{ .Values.mongodb.auth.username | urlquery }}:{{ .Values.mongodb.auth.password | urlquery }}` |
| WR-03: No checksum annotations | Unconditional checksum/config + checksum/secret annotations in pod template | `deployment.yaml` lines 29-30 |
| WR-04: RollingUpdate deadlock on RWO PVC | `strategy: {type: Recreate}` | `mongodb/deployment.yaml` lines 23-24 |
| WR-05: `make deploy` ignored IMAGE/TAG | `--set image.repository=$(IMAGE) --set image.tag=$(TAG)` added | `Makefile` deploy target |
| WR-06: /health 30s hang on Mongo outage | `&serverSelectionTimeoutMS=2000` + `timeoutSeconds: 3` on readiness probe | `secret.yaml` MONGO_URI; `deployment.yaml` readinessProbe |
| WR-07: No guard on committed dev password | Conditional WARNING block in NOTES.txt | `NOTES.txt` lines 2-7 |

CR-01 re-verified LIVE by orchestrator after fix: `kubectl get endpoints field-guide-api` lists ONLY the API pod IP; `kubectl port-forward svc/field-guide-api 8080:80` + curl → HTTP 200 on /health, /entries, /metrics; 4/4 consecutive 200s.

---

### Human Verification Required

None. All must-haves verified programmatically (code inspection) or by documented live cluster evidence (03-04-SUMMARY + orchestrator re-verification).

The initial 03-04 port-forward failure was root-caused to CR-01 (selector bug now fixed). Post-fix port-forward confirmed working by orchestrator with HTTP 200 on all three endpoints.

Cosmetic deferred observation (not blocking): gunicorn `/home/app` permission warning in startup logs (non-root has no writable home). Harmless — gunicorn served traffic throughout. Optional Phase 4 polish (`HOME=/tmp` or `--worker-tmp-dir`).

---

### Gaps Summary

No gaps. All Phase 3 success criteria are met:

1. Non-root gunicorn container → proven in codebase (Dockerfile) and live (UID 10001, PID 1 = gunicorn)
2. helm lint + helm install clean → proven live; all templates verified in codebase
3. App reachable via port-forward, /health 200, /entries JSON → proven by orchestrator re-verification (4/4 200s)
4. Plain mongo:7 manifests, clean uninstall → proven in codebase and live (PVC gone)
5. Generic values.yaml for PRD-3 → proven in codebase (all required fields present, IfNotPresent locked)

The post-execution code review (1 Critical + 7 Warnings) was fully resolved before this verification; the fixed chart is the current codebase state.

---

_Verified: 2026-07-07T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
