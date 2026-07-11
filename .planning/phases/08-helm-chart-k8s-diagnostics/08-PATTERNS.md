# Phase 8: Helm Chart + K8s Diagnostics - Pattern Map

**Mapped:** 2026-07-11
**Files analyzed:** 20 (9 chart files + 6 app files + 5 test files)
**Analogs found:** 19 / 20 (only `rbac.yaml` has no direct analog)

This phase is ~80% mechanical reuse. Two workstreams share one page:
1. A Helm chart mirroring `charts/field-guide-api/` (minus `mongodb/`) with a `launchpad.*` prefix + one NEW `rbac.yaml`.
2. A `/diagnostics` route reading pods/deployments via the SA, degrading cleanly with three distinct failure states.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `charts/launchpad/Chart.yaml` | config | — | `charts/field-guide-api/Chart.yaml` | exact |
| `charts/launchpad/.helmignore` | config | — | `charts/field-guide-api/.helmignore` | exact (verbatim copy) |
| `charts/launchpad/values.yaml` | config | — | `charts/field-guide-api/values.yaml` | exact (minus mongodb block) |
| `charts/launchpad/templates/_helpers.tpl` | config | — | `charts/field-guide-api/templates/_helpers.tpl` | exact (prefix swap, drop mongodb helpers) |
| `charts/launchpad/templates/deployment.yaml` | config | request-response | `charts/field-guide-api/templates/deployment.yaml` | exact (+ SA + POD_NAMESPACE) |
| `charts/launchpad/templates/service.yaml` | config | request-response | `charts/field-guide-api/templates/service.yaml` | exact (helper renames only) |
| `charts/launchpad/templates/configmap.yaml` | config | — | `charts/field-guide-api/templates/configmap.yaml` | exact (different keys) |
| `charts/launchpad/templates/secret.yaml` | config | — | `charts/field-guide-api/templates/secret.yaml` | role-match (simplified — single stringData) |
| `charts/launchpad/templates/NOTES.txt` | config | — | `charts/field-guide-api/templates/NOTES.txt` | exact (reword, drop mongo warning) |
| `charts/launchpad/templates/rbac.yaml` | config | — | *(none — new RBAC resource)* | **no analog** |
| `apps/launchpad/app/cluster_state.py` | service | request-response (read-only) | `apps/launchpad/app/status.py` | role-match (bare never-raises helper) |
| `apps/launchpad/app/routes/partials.py` (EDIT) | route | request-response | `status_cards` in same file | exact |
| `apps/launchpad/app/routes/pages.py` (EDIT) | route | request-response | `diagnostics` in same file | exact (flesh out) |
| `apps/launchpad/app/templates/diagnostics.html` (EDIT) | component | — | `index.html` + `diagnostics.html` | exact |
| `apps/launchpad/app/templates/partials/cluster_state.html` | component | — | `partials/status_cards.html` | role-match |
| `apps/launchpad/tests/test_cluster_state.py` | test | — | `tests/test_status.py` | role-match |
| `apps/launchpad/tests/test_partials.py` (EDIT) | test | — | existing `status_cards` tests | exact |
| `apps/launchpad/app/k8s.py` | — | — | REUSE (do not rebuild) | n/a |
| `apps/launchpad/app/__init__.py` (EDIT if needed) | config | — | existing blueprint registration | exact |

**Note:** No new blueprint is needed — `cluster_state` route is added to the existing `partials_bp` (already registered in `__init__.py`). No `__init__.py` edit required unless a new module is imported at factory time (it is not — `cluster_state.py` is imported inside `partials.py`).

---

## Pattern Assignments

### `apps/launchpad/app/cluster_state.py` (service, read-only)

**Analog:** `apps/launchpad/app/status.py`

This is the ONE genuinely new piece of app logic (~40 lines). Mirror `status.py`'s shape exactly: a bare module-level function (NO Blueprint), a module-level timeout constant, and per-call exception isolation so it never raises. The critical difference from `status.py` is **three distinct exception branches** (verified in RESEARCH §In-Cluster Auth Failure Modes).

**Imports/module-constant pattern** (`status.py` lines 18-28) — mirror the module-level timeout constant idiom:
```python
import requests
from flask import current_app
from prometheus_client import REGISTRY
from app.extensions import mongo

FIELD_GUIDE_TIMEOUT_SECONDS = 2
```
For `cluster_state.py`, the equivalent is:
```python
import os
import urllib3
from kubernetes.client.exceptions import ApiException
from app import k8s  # module import — conftest monkeypatches app.k8s.get_k8s_clients; a from-import binds the original and the patch never reaches it (plan-check BLOCKER 3)

K8S_REQUEST_TIMEOUT_SECONDS = 5  # SC #5 — every list call passes this
```

**Never-raises helper pattern** (`status.py` lines 52-98) — each sub-check wrapped in its own try/except, returns a plain dict, discards exception detail (T-07-07: never `str(exception)`):
```python
    mongo_status = "down"
    try:
        mongo.cx.admin.command("ping")
        mongo_status = "up"
    except Exception:
        pass
    ...
    return {
        "api_health": "ok" if mongo_status == "up" else "degraded",
        "mongo_status": mongo_status,
        ...
    }
```

**Reused dependency — the K8s client accessor** (`app/k8s.py` lines 24-49). Do NOT rebuild. Call it per-request and branch on `None`:
```python
core_v1, apps_v1 = k8s.get_k8s_clients()   # returns (None, None) outside a cluster
if core_v1 is None:
    return {"available": False}        # (a) D-03 muted panel — NOT an error
```

**Three failure branches (the load-bearing new logic — RESEARCH §In-Cluster Auth Failure Modes, verified against kubernetes==36.0.2):**
- `(None, None)` from `get_k8s_clients()` → `{"available": False}` (D-03 muted panel, NOT an error)
- `ApiException` with `.status == 403` → `{"available": True, "error": "forbidden"}` (RBAC missing — distinct error state, must NOT be conflated with outside-cluster)
- `ApiException` other status OR `urllib3.exceptions.HTTPError` (MaxRetryError/timeout) → `{"available": True, "error": "unreachable"}`
- success → `{"available": True, "pods": [...], "deployments": [...]}`

Every list call passes `_request_timeout=K8S_REQUEST_TIMEOUT_SECONDS` (SC #5), scoped to `os.environ.get("POD_NAMESPACE", "default")` (D-05). Use `*_namespaced_*` variants only — never `list_pod_for_all_namespaces` (would 403 under the namespace Role and violate SC #4).

**Object-shape mapping (RESEARCH §Cluster State Table Data Shapes, VERIFIED against 36.0.2 model files):**
- Pods: `p.metadata.name`, `p.status.phase`, ready = count of `c.ready` over `(p.status.container_statuses or [])`, restarts = `sum(c.restart_count ...)`, age from `p.metadata.creation_timestamp`
- Deployments: `d.metadata.name`, `f"{d.status.ready_replicas or 0}/{d.spec.replicas or 0}"`, `d.status.updated_replicas or 0`, `d.status.available_replicas or 0`
- **Always coalesce `None` with `or 0` / `or []`** — these fields are `None` before objects settle.

---

### `apps/launchpad/app/routes/partials.py` (route, request-response) — EDIT

**Analog:** the existing `status_cards` route in the SAME file (`partials.py` lines 33-40).

Add ONE new route to the existing `partials_bp` blueprint (already registered). Copy the `HX-Request` branch byte-for-byte:

**Existing `status_cards` pattern** (`partials.py` lines 33-40):
```python
@partials_bp.route("/status-cards", methods=["GET"])
def status_cards():
    status = get_platform_status()
    if request.headers.get("HX-Request") == "true":
        return render_template("partials/status_cards.html", status=status)
    return render_template("status_full_page.html", status=status)
```

New route (mirror exactly — same `HX-Request == "true"` check, same fragment-vs-full-page split):
```python
from app.cluster_state import get_cluster_state   # add to imports

@partials_bp.route("/cluster-state", methods=["GET"])
def cluster_state():
    state = get_cluster_state()
    if request.headers.get("HX-Request") == "true":
        return render_template("partials/cluster_state.html", state=state)
    return render_template("cluster_state_full_page.html", state=state)
```
Import `get_cluster_state` at module top alongside `from app.status import get_platform_status` (line 28). Planner's discretion whether to add a dedicated `cluster_state_full_page.html` (mirror `status_full_page.html`) or reuse `diagnostics.html` for the non-htmx branch.

---

### `apps/launchpad/app/routes/pages.py` (route) — EDIT

**Analog:** the existing `diagnostics` route in the SAME file (`pages.py` lines 34-37).

The route already exists and renders `diagnostics.html`. No signature change — the work is in the template, not the route. Leave the route as-is unless passing a context var:
```python
@pages_bp.route("/diagnostics", methods=["GET"])
def diagnostics():
    return render_template("diagnostics.html")
```

---

### `apps/launchpad/app/templates/diagnostics.html` (component) — EDIT

**Analogs:** `index.html` (htmx polling section) + `base.html` (shell) + current `diagnostics.html` stub.

Render two stacked sections (D-01). Top = Platform Checks (reuse the existing `/partials/status-cards` hx-get, D-02). Bottom = Cluster State (NEW `/partials/cluster-state` hx-get, polls every 10s).

**Shell pattern** (current `diagnostics.html` lines 1-7) — extends base, sets title/content blocks:
```html
{% extends "base.html" %}
{% block title %}Diagnostics{% endblock %}
{% block content %}
...
{% endblock %}
```

**htmx visibility-guarded poll pattern** (`index.html` lines 4-13, VERIFIED — resolves the Phase-7 visibility-guard flag). For the Platform Checks section reuse the 15s trigger verbatim; for Cluster State change ONLY the interval to `10s` (D-04):
```html
<section id="cluster-state"
         hx-get="{{ url_for('partials.cluster_state') }}"
         hx-trigger="load, every 10s [document.visibilityState === 'visible'], visibilitychange[document.visibilityState === 'visible'] from:document"
         hx-swap="innerHTML">
  <p>Loading cluster state…</p>
</section>
```
Keep the server-rendered fallback `<p>` inside the section (matches `index.html`'s "Loading platform status…" fallback for first paint / no-JS).

---

### `apps/launchpad/app/templates/partials/cluster_state.html` (component) — NEW

**Analog:** `partials/status_cards.html` (lines 1-16) — the fragment-only template (no `{% extends %}`, no `<html>`).

The fragment renders one of four states off the `state` dict from `get_cluster_state()`:
- `state.available == False` → muted panel, exact copy: **"Not running in a cluster — Kubernetes view disabled"** (D-03 / RESEARCH §Specific Ideas). Must be a muted panel, NOT an error style.
- `state.error == "forbidden"` → error panel ("Kubernetes access denied — check RBAC")
- `state.error == "unreachable"` → error panel ("Kubernetes API unreachable")
- else → pods table (name · phase · ready `n/m` · restarts · age) + deployments table (name · ready · up-to-date · available)

**Fragment shape to mirror** (`status_cards.html` — plain `<article>`/markup, conditional classes via Jinja, no shell):
```html
<article class="status-card status-card--{{ 'ok' if status.mongo_status == 'up' else 'degraded' }}">
  <header>MongoDB</header>
  <p>{{ status.mongo_status }}</p>
</article>
```
Reuse the `status-card` / `status-card--*` class vocabulary for the muted/error panels so styling stays consistent with Platform Checks.

---

### `apps/launchpad/tests/test_cluster_state.py` (test) — NEW

**Analog:** `tests/test_status.py` (branch-per-outcome structure) + `tests/test_k8s.py` (fixture usage) + `tests/conftest.py` fixtures.

100% coverage gate (`--cov-fail-under=100`) — every branch must be hit. Reuse the existing `k8s_disabled` and `k8s_enabled` fixtures from `conftest.py` (lines 54-77) — do NOT write new client mocks.

**Fixture reuse pattern** (`conftest.py` lines 67-77) — `k8s_enabled` yields `(fake_core_v1, fake_apps_v1)` MagicMocks; set `.return_value` / `.side_effect` on their list methods:
```python
core_v1, apps_v1 = k8s_enabled
core_v1.list_namespaced_pod.return_value = fake_pod_list
```

**Branch-per-test structure** (`test_status.py` lines 17-59 idiom — one test per outcome, `app.app_context()` where `current_app` is touched):
- Branch 1 (outside cluster): `k8s_disabled` → assert `{"available": False}`
- Branch 2 (success): `k8s_enabled` + `SimpleNamespace`-shaped fake `V1PodList`/`V1DeploymentList` (RESEARCH §Testing Strategy lines 439-455). Assert mapped columns; assert `_request_timeout=5` passed (`core_v1.list_namespaced_pod.assert_called_once_with("launchpad", _request_timeout=5)` after `monkeypatch.setenv("POD_NAMESPACE", "launchpad")`). Include one pod with `container_statuses=None` to cover the `or []` guard.
- Branch 3 (403): `core_v1.list_namespaced_pod.side_effect = ApiException(status=403, reason="Forbidden")` → assert `{"available": True, "error": "forbidden"}`
- Branch 4 (timeout/unreachable): `side_effect = urllib3.exceptions.MaxRetryError(pool=None, url="/api")` AND a non-403 `ApiException(status=500)` → both assert `{"available": True, "error": "unreachable"}`

**Timeout-kwarg grep gate** (mirror `test_status.py` lines 145-158 `test_status_no_requests_get_call_missing_timeout`): a companion test that `inspect.getsource(cluster_state_module)` and asserts every `list_namespaced_*(` call line contains `_request_timeout=` (SC #5 enforcement).

---

### `apps/launchpad/tests/test_partials.py` (test) — EDIT

**Analog:** the existing `status_cards` tests in the SAME file (`test_partials.py` lines 11-27).

Add cluster-state route tests mirroring the fragment-vs-full-page pattern exactly. Use `k8s_disabled` so no cluster is needed:

**Fragment-vs-fullpage assertion pattern** (`test_partials.py` lines 11-27):
```python
def test_..._fragment_when_hx_request_present(client, k8s_disabled):
    resp = client.get("/partials/cluster-state", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "<html" not in body

def test_..._full_page_when_no_hx_request(client, k8s_disabled):
    resp = client.get("/partials/cluster-state")
    assert "<html" in resp.get_data(as_text=True)
```
Also assert the muted-panel copy ("Not running in a cluster") appears in the `k8s_disabled` fragment.

---

### `charts/launchpad/` chart files (config)

**Analog:** `charts/field-guide-api/` — copy the whole chart, delete `templates/mongodb/`, apply mechanical changes. All source line references below are from the field-guide-api chart files (each read in full).

#### `Chart.yaml` (analog `field-guide-api/Chart.yaml` lines 1-12)
```yaml
apiVersion: v2
name: field-guide-api           # → name: launchpad
description: >- ...             # → reword for launchpad dashboard
type: application
version: 0.1.0
appVersion: "0.1.0"
```
Keep `apiVersion: v2`. Change `name:` to `launchpad`, reword `description`.

#### `_helpers.tpl` (analog `field-guide-api/templates/_helpers.tpl` lines 1-88) — THE load-bearing SC #1 change
Rename EVERY `field-guide-api.*` define/include → `launchpad.*`. **Keep** these five blocks: `name` (lines 12-14), `fullname` (lines 22-33), `chart` (lines 49-51), `labels` (lines 56-63), `selectorLabels` (lines 69-72). **DELETE** the two mongodb helpers: `field-guide-api.mongodb.fullname` (lines 42-44) and `field-guide-api.mongodb.selectorLabels` (lines 84-87) — no mongodb subchart. The distinct `app.kubernetes.io/name: launchpad` in `selectorLabels` (line 70) is exactly what prevents the SC #1 selector collision with field-guide-api pods.

selectorLabels block to preserve (with prefix swap):
```
{{- define "launchpad.selectorLabels" -}}
app.kubernetes.io/name: {{ include "launchpad.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
```

#### `deployment.yaml` (analog `field-guide-api/templates/deployment.yaml` lines 1-82)
Rename helper includes to `launchpad.*`. Then apply RESEARCH §Helm Chart Mirroring changes:
1. Add `serviceAccountName: launchpad` under `spec.template.spec` (alongside `securityContext`, near line 37). **Literal `launchpad`** (SC #4).
2. Add `POD_NAMESPACE` Downward API env to the container `env:` list (currently lines 48-63):
   ```yaml
   - name: POD_NAMESPACE
     valueFrom:
       fieldRef:
         fieldPath: metadata.namespace
   ```
3. Env sources: keep `MONGO_URI` from Secret (lines 49-53); replace `MONGO_DBNAME` with `FIELD_GUIDE_BASE_URL` and `APP_VERSION` from the ConfigMap; keep `FLASK_DEBUG` from ConfigMap (lines 59-63).
4. **readinessProbe stays `httpGet /health` port 8000** (lines 64-72) — D-08, do NOT weaken. Keep livenessProbe `tcpSocket 8000` (lines 73-77).
5. Keep the `checksum/config` + `checksum/secret` annotations (lines 29-30) and `securityContext runAsUser 10001` (lines 37-39, matches Dockerfile USER 10001).

readinessProbe block to keep verbatim (D-08):
```yaml
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5
            timeoutSeconds: 3
```

#### `service.yaml` (analog `field-guide-api/templates/service.yaml` lines 1-19)
Rename helper includes to `launchpad.*` only. Keep `type: {{ .Values.service.type }}`, `port` 80, `targetPort` 8000. No structural change.

#### `configmap.yaml` (analog `field-guide-api/templates/configmap.yaml` lines 1-14)
Rename helper includes. Replace the `data:` keys — emit `FIELD_GUIDE_BASE_URL`, `APP_VERSION`, `FLASK_DEBUG` (the non-secret keys `app/config.py` reads, lines 38-48). Drop `MONGO_DBNAME` (launchpad's `MONGO_URI` carries the db in its path, per `config.py` line 31-33).

#### `secret.yaml` (analog `field-guide-api/templates/secret.yaml` lines 1-28) — SIMPLIFIED
Rename helper includes. Replace the whole `mongodb.enabled` conditional (lines 16-28) with a single `stringData.MONGO_URI` from `.Values.mongoUri` — no urlquery-from-parts assembly (that was mongodb-subchart-specific). Keep `serverSelectionTimeoutMS=2000` in the placeholder URI so `/health` fails fast (matches `app/__init__.py` line 48 default of 2000). Placeholder value until Phase 9 supplies real in-cluster Mongo.

#### `values.yaml` (analog `field-guide-api/values.yaml` lines 1-60)
Keep `replicaCount` (line 7), `image` block (lines 9-14 — but set `repository: localhost:5001/launchpad`, `tag: latest` per D-07), `service` (lines 16-19), `resources` (lines 21-27), `metrics.enabled` (lines 29-30). **REMOVE** the entire `mongodb:` block (lines 47-60) and `externalMongoUri` (lines 38-42). Replace `config.mongoDbName` with `config.fieldGuideBaseUrl` and `config.appVersion`; keep `config.flaskDebug: ""`. Add a plain `mongoUri` value for the Secret placeholder.

#### `NOTES.txt` (analog `field-guide-api/templates/NOTES.txt` lines 1-22)
Rename helper includes to `launchpad.*`. **DELETE** the mongodb-password warning block (lines 2-7). Reword usage for launchpad (port-forward, then curl `/health` `/diagnostics` `/api/status`).

#### `.helmignore` (analog `field-guide-api/.helmignore`)
Copy verbatim — no changes.

---

### `charts/launchpad/templates/rbac.yaml` (config) — NEW, NO ANALOG

No existing RBAC resource in the repo. Use the standard SA/Role/RoleBinding shape from RESEARCH §RBAC Manifests (lines 311-352, `[CITED: kubernetes.io RBAC docs]`), using the same `{{- include "launchpad.labels" . | nindent 4 }}` templating convention that every other template in the chart uses.

Three documents in one file:
- **ServiceAccount** `metadata.name: launchpad` (literal — SC #4)
- **Role** (namespace-scoped, NOT ClusterRole — SC #4) named `{{ include "launchpad.fullname" . }}-read`, rules: `apiGroups: [""]` → `pods`, `apiGroups: ["apps"]` → `deployments`, verbs `["get", "list", "watch"]` only
- **RoleBinding** binding the Role to `ServiceAccount launchpad` in `{{ .Release.Namespace }}`

The `labels:` block on each resource copies the same include idiom seen in every field-guide-api template (e.g. `deployment.yaml` lines 13-14):
```yaml
  labels:
    {{- include "launchpad.labels" . | nindent 4 }}
```

---

## Shared Patterns

### Bare "never-raises" helper (NO Blueprint)
**Source:** `apps/launchpad/app/status.py` lines 31-98
**Apply to:** `app/cluster_state.py`
A module-level function returning a plain dict, every external call wrapped in its own try/except, exception detail discarded (never `str(exception)` — T-07-07 / RESEARCH §Security Domain "Secret leakage" mitigation). This is the exact discipline `get_platform_status()` uses; `get_cluster_state()` must match it but with the three explicit K8s exception branches.

### `HX-Request` fragment-vs-full-page branch
**Source:** `apps/launchpad/app/routes/partials.py` lines 33-40 (`status_cards`)
**Apply to:** the new `/partials/cluster-state` route
`if request.headers.get("HX-Request") == "true": render fragment; else render full page`. Byte-identical structure.

### htmx visibility-guarded polling
**Source:** `apps/launchpad/app/templates/index.html` lines 4-7 (VERIFIED — resolves Phase-7 visibility-guard flag)
**Apply to:** the Cluster State `<section>` in `diagnostics.html` (change interval `15s`→`10s` per D-04)
```
hx-trigger="load, every 10s [document.visibilityState === 'visible'], visibilitychange[document.visibilityState === 'visible'] from:document"
```

### Chart label/naming helper prefix
**Source:** `charts/field-guide-api/templates/_helpers.tpl` lines 56-72
**Apply to:** every template in `charts/launchpad/` (all `include "launchpad.*"`)
The `labels` / `selectorLabels` includes + `nindent`. The distinct `app.kubernetes.io/name: launchpad` prevents the SC #1 selector collision.

### `_request_timeout=5` on every K8s call (SC #5)
**Source:** RESEARCH §Standard Stack + §Don't Hand-Roll (VERIFIED against `core_v1_api.py` + `rest.py`); discipline mirrors `status.py`'s `FIELD_GUIDE_TIMEOUT_SECONDS` (line 28)
**Apply to:** every `list_namespaced_*` call in `cluster_state.py`, enforced by a source-grep test (mirror `test_status.py` lines 145-158)

### Existing K8s / Mongo test fixtures
**Source:** `apps/launchpad/tests/conftest.py` — `k8s_disabled` (lines 54-64), `k8s_enabled` (lines 67-77), `app`/`client` (lines 19-51)
**Apply to:** `test_cluster_state.py` and the new `test_partials.py` cluster-state tests. Reuse verbatim — do not write new client/K8s mocks.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `charts/launchpad/templates/rbac.yaml` | config | — | No RBAC resource (SA/Role/RoleBinding) exists anywhere in the repo. Use RESEARCH §RBAC Manifests shape + the chart's existing `include "launchpad.labels"` templating convention. This is the only genuinely-new chart template. |

---

## Metadata

**Analog search scope:** `charts/field-guide-api/` (all 13 files), `apps/launchpad/app/` (all .py + templates), `apps/launchpad/tests/`
**Files scanned:** 24 read in full (9 chart, 6 app source, 4 template, 5 test)
**Pattern extraction date:** 2026-07-11
