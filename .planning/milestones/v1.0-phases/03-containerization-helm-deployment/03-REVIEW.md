---
phase: 03-containerization-helm-deployment
reviewed: 2026-07-06T20:36:56Z
depth: standard
files_reviewed: 16
files_reviewed_list:
  - apps/field-guide-api/Dockerfile
  - apps/field-guide-api/.dockerignore
  - Makefile
  - charts/field-guide-api/Chart.yaml
  - charts/field-guide-api/values.yaml
  - charts/field-guide-api/.helmignore
  - charts/field-guide-api/templates/_helpers.tpl
  - charts/field-guide-api/templates/NOTES.txt
  - charts/field-guide-api/templates/deployment.yaml
  - charts/field-guide-api/templates/service.yaml
  - charts/field-guide-api/templates/configmap.yaml
  - charts/field-guide-api/templates/secret.yaml
  - charts/field-guide-api/templates/mongodb/deployment.yaml
  - charts/field-guide-api/templates/mongodb/service.yaml
  - charts/field-guide-api/templates/mongodb/pvc.yaml
  - charts/field-guide-api/templates/mongodb/secret.yaml
findings:
  critical: 1
  warning: 7
  info: 6
  total: 14
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-07-06T20:36:56Z
**Depth:** standard
**Files Reviewed:** 16
**Status:** issues_found

## Summary

Reviewed the Dockerfile, Makefile build/load/deploy targets, and the full Helm chart (app + embedded mongo:7 manifests). The Dockerfile is solid (multi-stage, numeric non-root UID, exec-form CMD, allowlist COPY) and cross-checks cleanly against the app source (`wsgi:app`, env var names `MONGO_URI`/`MONGO_DBNAME`/`FLASK_DEBUG`, `/health` probe contract).

One **blocking cross-resource bug** exists in the chart: the MongoDB pod carries the same `app.kubernetes.io/name` + `app.kubernetes.io/instance` labels as the API pod, so the API Service's selector matches BOTH pods. Once the mongo pod is Ready, roughly half of all requests to the API Service (and `kubectl port-forward svc/...` from NOTES.txt) land on the mongod pod's port 8000, which refuses connections. The default `make deploy` path ships this bug.

Additional warnings cover: the documented-but-unimplemented `mongodb.enabled: false` external-URI seam, unencoded passwords in the Mongo URI, missing checksum annotations (stale env after `helm upgrade`), missing `Recreate` strategy on the single-replica Mongo Deployment (upgrade deadlock on the RWO PVC), the Makefile `deploy` target silently ignoring `IMAGE`/`TAG`, readiness-probe behavior contradicting its own documentation during Mongo outages, and the committed default password lacking a production guard (flagged per the PRD-3 seam context).

## Critical Issues

### CR-01: API Service selector also matches the MongoDB pod — intermittent connection-refused on the app Service

**Files:**
- `charts/field-guide-api/templates/mongodb/deployment.yaml:24-29` (pod labels)
- `charts/field-guide-api/templates/service.yaml:18-19` (app Service selector)
- `charts/field-guide-api/templates/_helpers.tpl:69-72` (shared selectorLabels)

**Issue:** The app Service selects pods by `field-guide-api.selectorLabels` only:

```yaml
selector:
  app.kubernetes.io/name: field-guide-api
  app.kubernetes.io/instance: <release>
```

The MongoDB pod template (mongodb/deployment.yaml:26-29) carries those exact two labels **plus** `app.kubernetes.io/component: mongodb`. Kubernetes label selectors are subset matches — extra labels on a pod do not exclude it. The mongo pod passes its readiness probe (`mongosh ping`), so it is added to the app Service's Endpoints. The app Service's `targetPort: 8000` then routes to port 8000 on the mongod pod, where nothing listens:

- With the default `replicaCount: 1`, ~50% of requests to `svc/field-guide-api` get connection refused.
- `kubectl port-forward svc/field-guide-api ...` (the exact command printed by NOTES.txt:5) picks a single backing pod and can pick the mongod pod, making the documented smoke test fail nondeterministically.
- The app Deployment's selector also matches mongo pods (ownership via ReplicaSet ownerRefs prevents adoption, but `kubectl` label-based operations and any future HPA/PDB on these labels are ambiguous).

**Fix:** Give MongoDB resources a distinct selector identity. Add a dedicated helper in `_helpers.tpl`:

```yaml
{{- define "field-guide-api.mongodb.selectorLabels" -}}
app.kubernetes.io/name: {{ include "field-guide-api.name" . }}-mongodb
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
```

Use it in `mongodb/deployment.yaml` (`spec.selector.matchLabels`, `spec.template.metadata.labels`, keeping `app.kubernetes.io/component: mongodb` as a non-selector label if desired) and in `mongodb/service.yaml` (`spec.selector`). Since the chart is pre-release (0.1.0), the selector-immutability constraint is not yet a migration concern — fix it now, before first tagged release. Verify with:

```bash
kubectl get endpoints field-guide-api -o wide   # must list ONLY the API pod IP
```

## Warnings

### WR-01: `mongodb.enabled: false` renders a broken MONGO_URI — the documented external-DB seam does not exist

**Files:** `charts/field-guide-api/templates/secret.yaml:17`, `charts/field-guide-api/values.yaml:40-41`
**Issue:** values.yaml:40 documents: "DB-less apps set mongodb.enabled: false and supply an external MONGO_URI via --set." But `secret.yaml` unconditionally renders:

```yaml
MONGO_URI: "mongodb://{{ .Values.mongodb.auth.username }}:...@{{ include "field-guide-api.mongodb.fullname" . }}:27017/..."
```

There is no value key for an external URI anywhere in the chart, and the hostname is always the in-chart `<fullname>-mongodb` Service — which is not rendered when `mongodb.enabled=false`. Result: setting the documented flag produces an app pointing at a nonexistent Service, permanently unready (`/health` 503), and `helm upgrade --wait` times out. There is no `--set` that can fix it because no template consumes one. The documented PRD-3 seam is unimplemented.

**Fix:** Add an `externalMongoUri` value and branch in secret.yaml:

```yaml
stringData:
  {{- if .Values.mongodb.enabled }}
  MONGO_URI: "mongodb://{{ .Values.mongodb.auth.username }}:{{ .Values.mongodb.auth.password | urlquery }}@{{ include "field-guide-api.mongodb.fullname" . }}:27017/{{ .Values.mongodb.auth.database }}?authSource=admin"
  {{- else }}
  MONGO_URI: {{ required "mongodb.enabled=false requires externalMongoUri" .Values.externalMongoUri | quote }}
  {{- end }}
```

### WR-02: MongoDB password interpolated into URI without URL-encoding

**File:** `charts/field-guide-api/templates/secret.yaml:17`
**Issue:** `{{ .Values.mongodb.auth.password }}` is embedded raw into the connection string. values.yaml:46 explicitly instructs users to `--set mongodb.auth.password=<real>` for anything real — but any password containing URI-reserved characters (`@`, `:`, `/`, `%`, `?`, `#`) produces an invalid or mis-parsed URI. PyMongo raises `InvalidURI` at startup (crash-loop), and an `@` in the password can shift the parsed hostname. Same applies to the username.
**Fix:**

```yaml
MONGO_URI: "mongodb://{{ .Values.mongodb.auth.username | urlquery }}:{{ .Values.mongodb.auth.password | urlquery }}@{{ include "field-guide-api.mongodb.fullname" . }}:27017/{{ .Values.mongodb.auth.database }}?authSource=admin"
```

### WR-03: No checksum annotations — config/secret changes do not restart app pods on `helm upgrade`

**File:** `charts/field-guide-api/templates/deployment.yaml:20-29`
**Issue:** MONGO_URI, MONGO_DBNAME, and FLASK_DEBUG are injected via `secretKeyRef`/`configMapKeyRef` env vars, which are read once at container start. `helm upgrade` with a changed password, DB name, or debug flag updates the Secret/ConfigMap but leaves running pods on stale values — and `--wait` reports success. This silently breaks the `make deploy` idempotent-upgrade contract for any config change.
**Fix:** Add checksum annotations to the pod template metadata:

```yaml
annotations:
  checksum/config: {{ include (print $.Template.BasePath "/configmap.yaml") . | sha256sum }}
  checksum/secret: {{ include (print $.Template.BasePath "/secret.yaml") . | sha256sum }}
```

(Note: the existing `{{- if .Values.metrics.enabled }}` guard around `annotations:` must be restructured so the annotations map always exists when checksums are added.)

### WR-04: MongoDB Deployment uses default RollingUpdate — upgrades deadlock on the RWO PVC / mongod lock

**File:** `charts/field-guide-api/templates/mongodb/deployment.yaml:17-30`
**Issue:** A single-replica database Deployment bound to a `ReadWriteOnce` PVC has no `strategy` set, so it defaults to `RollingUpdate` (maxSurge 25% → 1). On any pod-template change (e.g., bumping `mongodb.image` to `mongo:8`), Kubernetes starts the new mongod pod *before* terminating the old one. On single-node kind both pods can mount the RWO volume (RWO is node-scoped), so the new mongod starts against a `/data/db` still held by the running old mongod — it fails on the WiredTiger/mongod.lock, crash-loops, never becomes Ready, and `helm upgrade --wait --timeout 180s` hangs then fails. Two mongod processes racing on one data dir is also a data-integrity hazard.
**Fix:**

```yaml
spec:
  replicas: 1
  strategy:
    type: Recreate
```

### WR-05: `make deploy` silently ignores IMAGE/TAG — deploys chart-default `dev` regardless of what was built

**File:** `Makefile:44-45`
**Issue:** `build` and `load` are parameterized on `$(IMAGE):$(TAG)`, but `deploy` runs `helm upgrade --install $(RELEASE) $(CHART) --wait --timeout 180s` with no image overrides. `make build TAG=v1.0 && make load TAG=v1.0 && make deploy TAG=v1.0` builds and pushes `v1.0`, then deploys `dev` — with `pullPolicy: IfNotPresent` this can even run a stale cached image with zero error. The variables exist specifically to coordinate these three targets; deploy breaks the chain silently.
**Fix:**

```make
deploy:
	helm upgrade --install $(RELEASE) $(CHART) \
		--set image.repository=$(IMAGE) --set image.tag=$(TAG) \
		--wait --timeout 180s
```

### WR-06: Readiness probe never gets the documented 503 — /health hangs 30s on Mongo outage and exhausts the gunicorn thread pool

**Files:** `charts/field-guide-api/templates/deployment.yaml:58-63`, `charts/field-guide-api/templates/secret.yaml:17`
**Issue:** deployment.yaml:4 documents "readinessProbe: httpGet /health — returns 503 when Mongo is down." In practice it cannot: MONGO_URI sets no `serverSelectionTimeoutMS`, so PyMongo's `admin.command("ping")` blocks up to the 30s default when Mongo is unreachable, while the probe's default `timeoutSeconds: 1` gives up after 1s. The kubelet still marks the pod unready (correct outcome), but each 5s probe leaves a request hanging ~30s inside gunicorn — with `--workers 1 --threads 4` (Dockerfile:37-38), a Mongo outage saturates all 4 threads within ~20s, blocking `/metrics` scrapes and any in-flight traffic, and the graceful-503 design is dead code.
**Fix:** Append a bounded timeout to the URI in secret.yaml (`...?authSource=admin&serverSelectionTimeoutMS=2000`) and optionally set `timeoutSeconds: 3` on the readinessProbe so the 503 path actually executes.

### WR-07: Default credential committed in values.yaml with no production guard on the PRD-3 seam

**File:** `charts/field-guide-api/values.yaml:44-48`
**Issue:** `mongodb.auth.password: fieldguide-dev-password` is clearly commented as local-dev-only, which is acceptable for this milestone. The hazard is structural: values.yaml is the declared PRD-3 templating seam, and nothing in the chart fails or warns when the default is used — a copy of this pattern deploys to any cluster with a known, committed root password and reports success. Safety currently depends entirely on a comment.
**Fix:** Keep the dev default, but add a guard rail — either a `values.schema.json`, or a NOTES.txt warning block, or (preferred for PRD-3 reuse) an explicit opt-in:

```yaml
{{- if eq .Values.mongodb.auth.password "fieldguide-dev-password" }}
{{- if not .Values.mongodb.auth.allowDevPassword }}
{{- fail "Refusing to deploy with the committed dev password. Set mongodb.auth.password or mongodb.auth.allowDevPassword=true for local kind." }}
{{- end }}
{{- end }}
```

## Info

### IN-01: containerPort and prometheus.io/port hardcode 8000 while service.targetPort is a value

**File:** `charts/field-guide-api/templates/deployment.yaml:28,40,61,66`
**Issue:** `service.targetPort: 8000` is configurable in values.yaml:19, but the containerPort, both probes, and the `prometheus.io/port` annotation hardcode `8000`. Changing the value silently breaks routing/probes/scraping.
**Fix:** Use `{{ .Values.service.targetPort }}` in all four places (or drop targetPort from values and document 8000 as fixed).

### IN-02: MongoDB container has no resource requests/limits

**File:** `charts/field-guide-api/templates/mongodb/deployment.yaml:31-37`
**Issue:** The app container has requests/limits; mongod has none. WiredTiger defaults its cache to ~50% of node RAM, so the mongo pod is the likeliest OOM/eviction candidate on a resource-constrained kind node.
**Fix:** Add a `mongodb.resources` values block and `resources: {{- toYaml ... }}` mirroring the app container.

### IN-03: MongoDB selector labels duplicated inline in three places

**Files:** `charts/field-guide-api/templates/mongodb/deployment.yaml:21-29`, `charts/field-guide-api/templates/mongodb/service.yaml:21-23`
**Issue:** The three-label selector set is hand-written in the Deployment matchLabels, the pod template, and the Service selector. A typo in any one silently produces an empty-endpoint Service. The chart's own convention (helpers as single source of truth, per _helpers.tpl:37-40) is violated here.
**Fix:** Folded into the CR-01 fix — define `field-guide-api.mongodb.selectorLabels` and include it in all three sites.

### IN-04: `config.mongoDbName` / MONGO_DBNAME is dead configuration that can silently diverge from the real database

**Files:** `charts/field-guide-api/values.yaml:33`, `charts/field-guide-api/templates/configmap.yaml:12`, `charts/field-guide-api/templates/deployment.yaml:48-52`
**Issue:** Flask-PyMongo 3.x derives `mongo.db` from the URI path (secret.yaml comment line 7 says so), which comes from `mongodb.auth.database`. `MONGO_DBNAME` is read into `Config` (app/config.py:33) but never consumed by any route — all data access goes through `mongo.db`. Two value keys now encode the same fact; setting `config.mongoDbName: other` changes nothing at runtime but misleads operators.
**Fix:** Either drop `config.mongoDbName`/MONGO_DBNAME from the chart, or derive both from a single value (`{{ .Values.mongodb.auth.database }}`) in the ConfigMap.

### IN-05: `make undeploy` is not idempotent

**File:** `Makefile:48-49`
**Issue:** `helm uninstall $(RELEASE)` errors if the release is absent, unlike the deliberately idempotent `deploy`/`cluster-up` targets.
**Fix:** `helm uninstall $(RELEASE) --ignore-not-found`

### IN-06: MongoDB pod has no securityContext (entrypoint starts as root)

**File:** `charts/field-guide-api/templates/mongodb/deployment.yaml:30-37`
**Issue:** The app pod enforces `runAsNonRoot` + `allowPrivilegeEscalation: false`; the mongo pod sets nothing, so the `mongo:7` entrypoint runs as root (it drops to the `mongodb` user for mongod itself, but the entrypoint and any exec'd probe shell start privileged). Acceptable for local kind; inconsistent hardening if the chart is copied forward.
**Fix:** For mongo:7 the minimal safe hardening is `securityContext: { allowPrivilegeEscalation: false }` on the container, plus pod-level `fsGroup: 999` with `runAsUser: 999` if root-less init is desired (requires the PVC to be writable by GID 999).

---

_Reviewed: 2026-07-06T20:36:56Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
