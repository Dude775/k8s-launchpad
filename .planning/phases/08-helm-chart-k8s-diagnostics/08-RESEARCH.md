# Phase 8: Helm Chart + K8s Diagnostics - Research

**Researched:** 2026-07-11
**Domain:** Helm chart authoring (Helm 3/4 templates + RBAC) + in-cluster Kubernetes read access from Flask via the official `kubernetes` Python client
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** `/diagnostics` renders as **two stacked sections**. Top: **"Platform Checks"** as status-cards (MongoDB ping, self-health, config/version) — the DIAG-01 in-app tier that runs without a cluster. Below: **"Cluster State"** (DIAG-02) with a **pods table** (columns: name · phase · ready `n/m` · restarts · age) and a **deployments table** (columns: name · ready · up-to-date · available).
- **D-02:** Reuse the Phase 6–7 UI shell verbatim — `base.html`, the sidebar nav (`/diagnostics` already present), and the status-card fragment/partial pattern for the Platform Checks tier.
- **D-03:** When `get_k8s_clients()` returns `(None, None)`, **Platform Checks still render live** (MongoDB ping, self-health, version all work without a cluster). The **Cluster State** section renders a **muted, labeled "Not running in a cluster — Kubernetes view disabled" panel** in place of the pods/deployments tables. Never a 500, never empty-looking tables, never a hidden section.
- **D-04:** The **Cluster State** section auto-refreshes via **htmx polling every 10s**, using the **visibility guard** (pause when the tab is hidden) established in Phases 6–7. The section swaps through a dedicated htmx **partial** endpoint (mirrors the status-cards partial pattern). Platform Checks may reuse the same live-refresh mechanism or render on load — planner's discretion, but the K8s tier is the one that polls.
- **D-05:** K8s queries are scoped to **launchpad's own namespace only** (from the pod's namespace, e.g. Downward API `POD_NAMESPACE` / config) — never all-namespaces. Consistent with the namespace-scoped Role in DEP-02.
- **D-06:** `charts/launchpad/` **mirrors `charts/field-guide-api/` verbatim, minus the `mongodb/` subchart**. Files: `Chart.yaml`, `templates/_helpers.tpl` (with the `launchpad.*` name/label prefix per SC #1), `deployment.yaml`, `service.yaml`, `configmap.yaml`, `secret.yaml`, `values.yaml`, `NOTES.txt`, `.helmignore`.
- **D-07:** Image reference convention `localhost:5001/launchpad:latest`. `values.yaml` surface mirrors field-guide-api's (image repo/tag, replicas, resources) plus wiring for `FIELD_GUIDE_BASE_URL`, `APP_VERSION`, and `MONGO_URI` (the latter via the chart's Secret even though the Mongo backend arrives in Phase 9).
- **D-08:** **readinessProbe points at `/health` now** (honors the locked Phase-7 readinessProbe contract). Consequence, accepted: because launchpad's own MongoDB is not deployed until Phase 9, `/health` returns 503 → the pod runs but stays **NotReady** until Phase 9 adds Mongo. **SC #2 only requires the pod to reach `Running`**, not `Ready`. Do NOT weaken the probe.
- **Locked by ROADMAP SCs:** `_helpers.tpl` uses `launchpad.*` prefix (SC #1) · `serviceAccountName: launchpad` (SC #4) · namespace-scoped Role granting only `get`/`list`/`watch` on `pods` and `deployments`, NOT a ClusterRole (SC #4) · all K8s API calls pass `_request_timeout=5` (SC #5).

### Claude's Discretion
- Exact table styling / column widths, NOTES.txt wording, values.yaml default resource limits, and whether Platform Checks poll or render-once (see D-04) are planner/executor discretion within the decisions above.

### Deferred Ideas (OUT OF SCOPE)
- **launchpad's own MongoDB manifests** — DEP-03, Phase 9 (chart's `mongodb/` subchart; also flips the pod from NotReady → Ready by satisfying `/health`).
- **Makefile `build-launchpad`/`load-launchpad`/`deploy-launchpad` + `up-all` + smoke** — DEP-04/05, Phase 10. The chart must be deploy-ready for them, but the targets themselves are not built here.
- Service catalog / events CRUD (Phase 9).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEP-01 | `charts/launchpad/` Helm chart (Deployment, Service, ConfigMap, Secret, values.yaml); `helm lint` passes; `_helpers.tpl` naming does not collide with field-guide-api selectors | Helm Chart Mirroring section — exact file-by-file diff from `charts/field-guide-api/`, `launchpad.*` prefix swap, distinct `app.kubernetes.io/name` avoids selector collision |
| DEP-02 | ServiceAccount + namespace-scoped Role + RoleBinding granting read-only pods/deployments; `serviceAccountName` in Deployment spec | RBAC Manifests section — exact SA/Role/RoleBinding templates with correct `apiGroups` (`""` for pods, `apps` for deployments), verbs `get`/`list`/`watch`, `serviceAccountName: launchpad` wiring |
| DIAG-01 | Diagnostics page with in-app platform checks (MongoDB ping, self-health, config/version) that runs without a cluster | Platform Checks tier reuses `get_platform_status()` (`app/status.py`) + status-cards partial verbatim; cluster-independent |
| DIAG-02 | Read-only Kubernetes state (pods/deployments in the namespace) via in-cluster SA with least-privilege RBAC, degrading to "outside cluster" | In-Cluster Auth Failure Modes + Cluster State partial + object-shape mapping + testing strategy for all three branches |
</phase_requirements>

## Summary

This phase is two loosely-coupled workstreams that share one page: (1) a Helm chart that mirrors the already-proven `charts/field-guide-api/` chart with a `launchpad.*` naming prefix plus three new RBAC resources, and (2) a `/diagnostics` route that reads pods/deployments from the Kubernetes API using the SA the chart provisions, degrading cleanly when there is no cluster. Nearly everything needed already exists in the repo as a working analog — the risk is not "what library" but "getting three distinct failure states right and not colliding label selectors."

The single most important correctness finding: **there are three distinct outcomes from the K8s calls, and the carried research flag is confirmed exactly.** (a) No ServiceAccount token / not in a cluster → `get_k8s_clients()` already returns `(None, None)` via a caught `ConfigException` → the muted "outside cluster" panel (D-03). (b) In-cluster but the SA lacks RBAC → `list_namespaced_pod()` raises `kubernetes.client.exceptions.ApiException` with `.status == 403` → this is an **error state, NOT the outside-cluster panel** and must be surfaced distinctly. (c) A hung socket → because of `_request_timeout=5`, urllib3 raises a `urllib3.exceptions.MaxRetryError` (wrapping `ReadTimeoutError`) that the client's `rest.py` does **not** catch for GET requests, so it propagates raw to the route. All three must be caught explicitly in the diagnostics data helper so the page never 500s.

**Primary recommendation:** Copy `charts/field-guide-api/` → `charts/launchpad/`, delete `templates/mongodb/`, mechanically swap the `_helpers.tpl` prefix to `launchpad.*`, add `templates/rbac.yaml` (SA + Role + RoleBinding) and `serviceAccountName: launchpad` to the Deployment, wire `POD_NAMESPACE` via the Downward API, and build a `cluster_state.py` helper + `/partials/cluster-state` route that branches on `(None,None)` / `ApiException 403` / `MaxRetryError` / success, mirroring the exact `HX-Request` partial pattern from `app/routes/partials.py`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Deploy launchpad to kind | Helm chart / K8s | — | DEP-01; packaging + rollout is a chart concern, not app code |
| Grant read access to pods/deployments | K8s RBAC (chart) | — | DEP-02; least-privilege identity is provisioned declaratively, never in code |
| Detect "am I in a cluster?" | API/Backend (`app/k8s.py`) | — | Already solved in Phase 5; per-request lazy accessor |
| Read pods/deployments | API/Backend (new `app/cluster_state.py`) | K8s API | DIAG-02; app queries its own namespace via the SA identity |
| Platform Checks (Mongo/version/health) | API/Backend (`app/status.py`) | — | DIAG-01; cluster-independent, reuses Phase-7 aggregation |
| Render tables + muted panel | Frontend Server (Jinja2 partial) | — | Server-rendered fragment; no client-side data fetching beyond htmx swap |
| 10s visibility-guarded refresh | Browser (htmx attrs) | Frontend Server | D-04; htmx polls the partial endpoint, tab-hidden guard pauses it |
| Learn own namespace | API/Backend | K8s Downward API | D-05; `POD_NAMESPACE` env injected by the Deployment spec |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `kubernetes` (Python client) | 36.0.2 | `CoreV1Api.list_namespaced_pod`, `AppsV1Api.list_namespaced_deployment`, `ApiException` | Already pinned in `apps/launchpad/requirements.txt` and installed in the venv; official client; already wired in `app/k8s.py` `[VERIFIED: requirements.txt + venv dist-info]` |
| Helm | 3.21.2 / 4.x | Chart lint, template, install | Locked (CLAUDE.md); `field-guide-api` chart is `apiVersion: v2` and installs unchanged under either `[VERIFIED: charts/field-guide-api/Chart.yaml]` |
| Flask | 3.1.3 | Route + Jinja2 rendering | Already the app framework; reuse blueprints `[VERIFIED: requirements.txt]` |

**No new packages are required for this phase.** Everything is already installed. Skip the Package Legitimacy Audit — no external installs.

### Supporting (existing, reuse — do not re-add)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `mongomock` | (test dep) | In-memory Mongo for tests | Platform Checks tests (already used in conftest) |
| `pytest` / `pytest-cov` | (test dep) | 100% coverage gate | `--cov-fail-under=100` in `pytest.ini` `[VERIFIED: pytest.ini]` |
| `unittest.mock.MagicMock` | stdlib | Fake `CoreV1Api`/`AppsV1Api` + fake `V1PodList` objects | Cluster-present + 403 + timeout branch tests |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `POD_NAMESPACE` via Downward API | Read `/var/run/secrets/kubernetes.io/serviceaccount/namespace` | The file is authoritative in-cluster but requires filesystem mocking in tests and only exists inside a pod; the env var is trivially injectable, overridable for local dev, and testable via `monkeypatch.setenv`. **Recommend the env var (D-05 explicitly allows it).** |
| `_request_timeout=5` (per-call) | Global `Configuration` timeout | The per-call kwarg is what SC #5 mandates and is simplest to grep/verify; a global config is invisible at the call site |
| One shared partial | Separate Platform-Checks and Cluster-State partials | D-04 says the K8s tier is the one that polls; keep the existing `/partials/status-cards` untouched and add ONE new `/partials/cluster-state` route |

## Package Legitimacy Audit

Not applicable — **this phase installs no external packages.** The only libraries used (`kubernetes==36.0.2`, `Flask==3.1.3`, test deps) are already pinned in `apps/launchpad/requirements.txt` and present in the venv (`kubernetes-36.0.2.dist-info` confirmed). No registry lookups or slopcheck run needed.

## Architecture Patterns

### System Architecture Diagram

```
Browser (/diagnostics)
   │  full-page GET
   ▼
pages.diagnostics ──renders──► diagnostics.html (extends base.html)
   │                                │
   │                                ├─ Platform Checks section
   │                                │     hx-get /partials/status-cards  (existing, reused)
   │                                │        └─► get_platform_status()  [app/status.py]
   │                                │               ├─ mongo ping
   │                                │               └─ version / service_count
   │                                │
   │                                └─ Cluster State section
   │                                      hx-get /partials/cluster-state  (NEW)
   │                                      hx-trigger every 10s [visible]
   ▼
partials.cluster_state (NEW)
   │  HX-Request? fragment : full page
   ▼
get_cluster_state()  [app/cluster_state.py, NEW]
   │
   ├─ get_k8s_clients()  ──► (None,None) ──────────────► {"available": False}  → muted panel (D-03)
   │        [app/k8s.py, reused]
   │
   └─ (core_v1, apps_v1) present:
        namespace = POD_NAMESPACE env  (Downward API)
        try:
          core_v1.list_namespaced_pod(ns, _request_timeout=5)      ┐
          apps_v1.list_namespaced_deployment(ns, _request_timeout=5)┘
        except ApiException as e (e.status == 403) ──► {"available": True, "error": "forbidden"}  → error panel
        except urllib3 MaxRetryError / ApiException(other) ──► {"available": True, "error": "unreachable"} → error panel
        else ──► {"available": True, "pods":[...], "deployments":[...]}  → two tables
                                    │
                                    ▼
                        cluster_state.html partial (pods table + deployments table)
```

### Recommended Structure (new/changed files)
```
apps/launchpad/app/
├── cluster_state.py                 # NEW — get_cluster_state() helper (mirrors status.py shape: bare, never raises)
├── routes/partials.py               # EDIT — add /partials/cluster-state route (mirrors status_cards HX-Request branch)
├── templates/
│   ├── diagnostics.html             # EDIT — two sections: Platform Checks + Cluster State
│   └── partials/
│       └── cluster_state.html        # NEW — pods table + deployments table + muted/error panels
└── tests/
    ├── test_cluster_state.py         # NEW — helper: (None,None) / success / 403 / timeout branches
    └── test_partials.py              # EDIT — /partials/cluster-state fragment vs full-page

charts/launchpad/                     # NEW — mirror of charts/field-guide-api/ minus mongodb/
├── Chart.yaml
├── .helmignore
├── values.yaml
├── templates/
│   ├── _helpers.tpl                  # launchpad.* prefix (SC #1)
│   ├── deployment.yaml               # + serviceAccountName + POD_NAMESPACE env + readinessProbe /health
│   ├── service.yaml
│   ├── configmap.yaml
│   ├── secret.yaml                   # MONGO_URI placeholder (Phase 9 supplies real Mongo)
│   ├── rbac.yaml                     # NEW — ServiceAccount + Role + RoleBinding (DEP-02)
│   └── NOTES.txt
```

### Pattern 1: Bare "never-raises" helper (mirror `app/status.py`)
**What:** `get_cluster_state()` is a Blueprint-free module-level function that returns a plain dict and never raises — every K8s call is exception-isolated, exactly like `get_platform_status()`.
**When to use:** Always, for the DIAG-02 data source.
**Example:**
```python
# app/cluster_state.py  — mirrors app/status.py's shape (no Blueprint, never raises)
import os
import urllib3
from kubernetes.client.exceptions import ApiException
from app import k8s  # module import, NOT `from app.k8s import get_k8s_clients` —
                     # conftest monkeypatches app.k8s.get_k8s_clients; a from-import
                     # binds the original function and the patch never reaches it
                     # (plan-check BLOCKER 3, 2026-07-11)

K8S_REQUEST_TIMEOUT_SECONDS = 5  # SC #5 — every list call passes this

def _pod_ready_counts(pod):
    statuses = pod.status.container_statuses or []
    ready = sum(1 for c in statuses if c.ready)
    return ready, len(statuses)

def get_cluster_state() -> dict:
    core_v1, apps_v1 = k8s.get_k8s_clients()
    if core_v1 is None:                       # (a) outside cluster (D-03) — NOT an error
        return {"available": False}

    namespace = os.environ.get("POD_NAMESPACE", "default")
    try:
        pod_list = core_v1.list_namespaced_pod(
            namespace, _request_timeout=K8S_REQUEST_TIMEOUT_SECONDS)
        dep_list = apps_v1.list_namespaced_deployment(
            namespace, _request_timeout=K8S_REQUEST_TIMEOUT_SECONDS)
    except ApiException as exc:
        if exc.status == 403:                 # (b) SA lacks RBAC — distinct error state
            return {"available": True, "error": "forbidden"}
        return {"available": True, "error": "unreachable"}
    except urllib3.exceptions.HTTPError:      # (c) timeout / socket — MaxRetryError subclass
        return {"available": True, "error": "unreachable"}

    pods = [{
        "name": p.metadata.name,
        "phase": p.status.phase,
        "ready": "{}/{}".format(*_pod_ready_counts(p)),
        "restarts": sum((c.restart_count for c in (p.status.container_statuses or [])), 0),
        "age": p.metadata.creation_timestamp,  # format in template or helper
    } for p in pod_list.items]

    deployments = [{
        "name": d.metadata.name,
        "ready": "{}/{}".format(d.status.ready_replicas or 0, d.spec.replicas or 0),
        "up_to_date": d.status.updated_replicas or 0,
        "available": d.status.available_replicas or 0,
    } for d in dep_list.items]

    return {"available": True, "pods": pods, "deployments": deployments}
```
*Source: field mapping `[VERIFIED: kubernetes 36.0.2 model files — v1_pod_status.py, v1_container_status.py, v1_deployment_status.py, v1_object_meta.py]`; pattern shape `[VERIFIED: app/status.py]`.*

### Pattern 2: `HX-Request` partial branch (mirror `app/routes/partials.py`)
**What:** New `/partials/cluster-state` route returns the fragment when `HX-Request == "true"`, a full page otherwise — byte-identical structure to `status_cards`.
```python
# add to app/routes/partials.py
from app.cluster_state import get_cluster_state

@partials_bp.route("/cluster-state", methods=["GET"])
def cluster_state():
    state = get_cluster_state()
    if request.headers.get("HX-Request") == "true":
        return render_template("partials/cluster_state.html", state=state)
    return render_template("cluster_state_full_page.html", state=state)  # or reuse diagnostics.html
```
*Source `[VERIFIED: app/routes/partials.py status_cards]`.*

### Pattern 3: htmx visibility-guarded 10s poll (mirror `index.html`)
**What:** The Cluster State `<section>` polls every 10s and pauses when the tab is hidden — the exact trigger string already in `index.html` (only the interval changes from `15s` to `10s`).
```html
<section id="cluster-state"
         hx-get="{{ url_for('partials.cluster_state') }}"
         hx-trigger="load, every 10s [document.visibilityState === 'visible'], visibilitychange[document.visibilityState === 'visible'] from:document"
         hx-swap="innerHTML">
  <p>Loading cluster state…</p>
</section>
```
*Source `[VERIFIED: app/templates/index.html]` — resolves the STATE.md Phase-7 htmx visibility-guard flag; the pattern is already shipped and working.*

### Anti-Patterns to Avoid
- **Treating a 403 as "outside cluster":** silently rendering the muted panel on `ApiException.status == 403` hides a real RBAC misconfiguration. The carried flag explicitly forbids this — 403 is an error state.
- **`except Exception:` swallowing everything in the K8s helper:** catch `ApiException` and `urllib3.exceptions.HTTPError` specifically; a bare catch masks bugs (same discipline `app/k8s.py` uses with `ConfigException`).
- **Adding a ClusterRole or `list_pod_for_all_namespaces`:** violates SC #4 least-privilege AND would 403 under the namespace-scoped Role. Always call the `*_namespaced_*` variants scoped to `POD_NAMESPACE`.
- **Weakening the readinessProbe to dodge NotReady:** explicitly forbidden by D-08.
- **Copying `templates/mongodb/` into `charts/launchpad/`:** deferred to Phase 9 (DEP-03).
- **Reusing `field-guide-api.*` helper names in the new chart:** identical `app.kubernetes.io/name` labels would let one Service's selector match the other's pods — the exact collision SC #1 guards against.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| In-cluster vs local detection | Custom env-var sniffing | `get_k8s_clients()` (`app/k8s.py`) | Already solved in Phase 5, tested, returns `(None,None)` |
| K8s API request timeout | Custom socket/thread watchdog | `_request_timeout=5` kwarg | Native to the client; SC #5 mandates it `[VERIFIED: core_v1_api.py + rest.py]` |
| Chart naming/labels | New `_helpers.tpl` from scratch | Copy field-guide-api's and swap the prefix | The helper logic (trunc 63, selectorLabels immutability) is already correct `[VERIFIED: _helpers.tpl]` |
| Platform Checks data | New aggregation | `get_platform_status()` | DIAG-01 == the Phase-7 status tier, cluster-free `[VERIFIED: app/status.py]` |
| htmx polling + tab-hidden guard | Custom JS | The `hx-trigger` string from `index.html` | Shipped and working in Phases 6–7 |

**Key insight:** Phase 8 is ~80% mechanical reuse. The genuinely new logic is one ~40-line helper (`cluster_state.py`) with three explicit exception branches and one `rbac.yaml` template. Resist rebuilding anything that already exists in the repo.

## Runtime State Inventory

This phase is greenfield-additive (new chart, new route) with one rename-adjacent concern — chart naming collision — already handled by the `launchpad.*` prefix. No datastore/OS/secret state is renamed or migrated.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — the diagnostics read is stateless; no new collection | None (verified — DIAG-02 is read-only K8s API, no Mongo write) |
| Live service config | New RBAC objects (SA/Role/RoleBinding) created **by the chart**, so they live in git, not a UI | None beyond authoring the templates |
| OS-registered state | None — no Task Scheduler / pm2 / systemd involvement | None (verified — pure kind/Helm) |
| Secrets/env vars | New `POD_NAMESPACE` env (non-secret, Downward API) + existing `MONGO_URI` Secret placeholder | Wire `POD_NAMESPACE` fieldRef in deployment.yaml; `MONGO_URI` Secret carried forward (real Mongo = Phase 9) |
| Build artifacts | `localhost:5001/launchpad:latest` image must be built + loaded before deploy (Makefile targets are Phase 10, but SC #2 exercises the loop manually) | Build + `kind load` the image before `helm install` for SC #2 verification |

## In-Cluster Auth Failure Modes (carried research flag — RESOLVED)

The three outcomes, with exact types and import paths, all verified against installed `kubernetes==36.0.2`:

| # | Scenario | What raises / returns | Where caught | UI result |
|---|----------|-----------------------|--------------|-----------|
| a | No SA token / not in a cluster (local dev, CI) | `config.load_incluster_config()` raises `kubernetes.config.ConfigException`; `get_k8s_clients()` already catches it and returns `(None, None)` | `app/k8s.py` (existing) — helper sees `core_v1 is None` | **Muted "Not running in a cluster" panel (D-03)** — NOT an error |
| b | In-cluster, but SA lacks RBAC | `list_namespaced_pod()` raises `kubernetes.client.exceptions.ApiException` with `.status == 403` (`.reason == "Forbidden"`) | `except ApiException as e: if e.status == 403` in `get_cluster_state()` | **Error panel** ("Kubernetes access denied — check RBAC"), distinct from (a) |
| c | Hung socket / API unreachable | `_request_timeout=5` → `urllib3.Timeout(total=5)` → on expiry urllib3 raises `urllib3.exceptions.MaxRetryError` (subclass of `HTTPError`) wrapping `ReadTimeoutError`. **The client's `rest.py` GET path only catches `SSLError`, so this propagates raw to the caller.** | `except urllib3.exceptions.HTTPError` in `get_cluster_state()` | **Error panel** ("Kubernetes API unreachable") |

**Verified facts:**
- `ApiException` is defined in `kubernetes/client/exceptions.py` and re-exported as `kubernetes.client.ApiException`. It carries `.status` (int) and `.reason` (str) attributes set from the HTTP response `[VERIFIED: exceptions.py:103-115]`.
- `_request_timeout` is a real kwarg on `list_namespaced_pod` / `list_namespaced_deployment`; an int/float becomes `urllib3.Timeout(total=n)` `[VERIFIED: core_v1_api.py + rest.py:141-144]`.
- The GET branch of `rest.py` wraps `pool_manager.request(...)` in a `try` that **only** catches `urllib3.exceptions.SSLError` and re-raises as `ApiException(status=0)`. A read timeout (`MaxRetryError`) is **not** caught there and reaches the route — so the route MUST catch `urllib3.exceptions.HTTPError` (or `MaxRetryError`) explicitly `[VERIFIED: rest.py:215-219]`.

**Recommendation:** catch `ApiException` first (branch on `.status == 403` vs. other statuses → both are "cluster reachable but query failed"), then `urllib3.exceptions.HTTPError` for the timeout/socket path. Import: `import urllib3` and `from kubernetes.client.exceptions import ApiException`.

## Namespace Discovery (D-05)

**Recommendation: Downward API env `POD_NAMESPACE`**, read via `os.environ.get("POD_NAMESPACE", "default")`.

Deployment wiring (add to the container `env:` list):
```yaml
- name: POD_NAMESPACE
  valueFrom:
    fieldRef:
      fieldPath: metadata.namespace
```

Rationale vs. reading `/var/run/secrets/kubernetes.io/serviceaccount/namespace`:
- The env var is trivially injectable and **overridable for local dev**, and testable with `monkeypatch.setenv("POD_NAMESPACE", "launchpad")` — no filesystem mocking.
- The service-account `namespace` file (sibling of the token/cert files at `/var/run/secrets/kubernetes.io/serviceaccount/`) only exists inside a pod and would need file-I/O mocking for the 100% coverage gate. `[VERIFIED: incluster_config.py defines SERVICE_TOKEN_FILENAME/SERVICE_CERT_FILENAME in that dir; namespace file is the standard sibling]`
- D-05 explicitly names `POD_NAMESPACE` as an acceptable source.

## RBAC Manifests (DEP-02 / SC #4)

Single `templates/rbac.yaml` (three documents). Correct `apiGroups`: `""` (core) for pods, `apps` for deployments. **Namespace-scoped `Role`, never `ClusterRole`.**

```yaml
# templates/rbac.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: launchpad                       # SC #4 — exact name referenced by serviceAccountName
  labels:
    {{- include "launchpad.labels" . | nindent 4 }}
---
apiVersion: rbac.authorization.k8s.io/v1
kind: Role                              # namespace-scoped, NOT ClusterRole (SC #4)
metadata:
  name: {{ include "launchpad.fullname" . }}-read
  labels:
    {{- include "launchpad.labels" . | nindent 4 }}
rules:
  - apiGroups: [""]                     # core group → pods
    resources: ["pods"]
    verbs: ["get", "list", "watch"]
  - apiGroups: ["apps"]                 # apps group → deployments
    resources: ["deployments"]
    verbs: ["get", "list", "watch"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: {{ include "launchpad.fullname" . }}-read
  labels:
    {{- include "launchpad.labels" . | nindent 4 }}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: {{ include "launchpad.fullname" . }}-read
subjects:
  - kind: ServiceAccount
    name: launchpad
    namespace: {{ .Release.Namespace }}
```

Deployment wiring: add `serviceAccountName: launchpad` under `spec.template.spec` (alongside `securityContext`).

*Note:* SA name is the literal `launchpad` (SC #4 mandates `serviceAccountName: launchpad`), while Role/RoleBinding use the `fullname` helper — this is fine because the `roleRef`/`subjects` reference each other by exact name. If the planner prefers a fully-templated SA name, it MUST still resolve to `launchpad` to satisfy SC #4; recommend keeping the SA name literal to avoid drift. `[CITED: kubernetes.io/docs/reference/access-authn-authz/rbac — Role/RoleBinding shape, apiGroups "" vs apps]`

## Helm Chart Mirroring (D-06 / DEP-01)

Copy `charts/field-guide-api/` → `charts/launchpad/`, then apply exactly these changes:

| File | Change |
|------|--------|
| `templates/mongodb/` (whole dir) | **DELETE** — deferred to Phase 9 (DEP-03) |
| `_helpers.tpl` | Rename every `field-guide-api.*` define/include → `launchpad.*`. **DELETE** the two mongodb helpers (`launchpad.mongodb.fullname`, `launchpad.mongodb.selectorLabels`) — no mongodb subchart here. Keep name/fullname/chart/labels/selectorLabels. Distinct `app.kubernetes.io/name: launchpad` is what prevents the SC #1 selector collision with field-guide-api. |
| `Chart.yaml` | `name: launchpad`; update `description`; keep `apiVersion: v2` |
| `values.yaml` | `image.repository: localhost:5001/launchpad`, `image.tag: latest` (D-07). **Remove** the entire `mongodb:` block and `externalMongoUri` gating. Add `config.fieldGuideBaseUrl` and `config.appVersion`. Keep `replicaCount`, `image.pullPolicy`, `service`, `resources`, `metrics.enabled`. Add a plain `mongoUri` value for the Secret placeholder (Phase 9 replaces with real in-cluster Mongo). |
| `templates/configmap.yaml` | Emit `FIELD_GUIDE_BASE_URL`, `APP_VERSION`, `FLASK_DEBUG` (non-secret env, matches `app/config.py` keys). Drop `MONGO_DBNAME` (launchpad's config uses `MONGO_URI` with the db in the path, per `app/config.py`). |
| `templates/secret.yaml` | Single `MONGO_URI` stringData from `.Values.mongoUri` (no urlquery-from-parts assembly — that was mongodb-subchart-specific). Placeholder value until Phase 9; keep `serverSelectionTimeoutMS=2000` in the URI so `/health` fails fast (matches `app/__init__.py` 2000ms default). |
| `templates/deployment.yaml` | (1) add `serviceAccountName: launchpad`; (2) add `POD_NAMESPACE` Downward API env; (3) `env` sources `MONGO_URI` from the Secret and `FIELD_GUIDE_BASE_URL`/`APP_VERSION`/`FLASK_DEBUG` from the ConfigMap; (4) **readinessProbe → `/health`, port 8000** (D-08 — leave as-is); (5) container port stays 8000 (gunicorn); (6) keep `checksum/config` + `checksum/secret` annotations, `securityContext` runAsUser 10001, tcpSocket livenessProbe. |
| `templates/service.yaml` | Rename helper includes only; `targetPort: 8000`, `port: 80` (same as field-guide-api) — launchpad's own Service. Note: the local port-forward on a *distinct* local port is a **Phase 10** Makefile concern (`port-forward-launchpad`), not the Service's cluster port. |
| `templates/NOTES.txt` | Reword for launchpad; drop the mongodb-password warning block. |
| `templates/rbac.yaml` | **NEW** — see RBAC section above. |
| `.helmignore` | Copy verbatim. |

**Verification gate for DEP-01/SC #1:** `helm lint charts/launchpad/` must pass with no warnings, and `helm template` of BOTH charts into the same namespace must produce disjoint `app.kubernetes.io/name` selector labels (`field-guide-api` vs `launchpad`). A quick check: `helm template launchpad charts/launchpad | grep "app.kubernetes.io/name"` should never emit `field-guide-api`.

## Cluster State Table Data Shapes (D-01)

Object attribute mapping, all `[VERIFIED: kubernetes 36.0.2 model files]`:

**Pods table** (`core_v1.list_namespaced_pod(...).items` → `list[V1Pod]`):
| Column | Source attribute |
|--------|------------------|
| name | `pod.metadata.name` (`V1ObjectMeta.name`) |
| phase | `pod.status.phase` (`V1PodStatus.phase`, e.g. "Running") |
| ready `n/m` | `n` = count of `c.ready == True`, `m` = `len(...)` over `pod.status.container_statuses` (`V1ContainerStatus.ready`) |
| restarts | `sum(c.restart_count ...)` (`V1ContainerStatus.restart_count`) |
| age | derived from `pod.metadata.creation_timestamp` (`V1ObjectMeta.creation_timestamp`, a `datetime`) |

**Deployments table** (`apps_v1.list_namespaced_deployment(...).items` → `list[V1Deployment]`):
| Column | Source attribute |
|--------|------------------|
| name | `dep.metadata.name` |
| ready | `f"{dep.status.ready_replicas or 0}/{dep.spec.replicas or 0}"` (`V1DeploymentStatus.ready_replicas`) |
| up-to-date | `dep.status.updated_replicas or 0` |
| available | `dep.status.available_replicas or 0` |

**Guard note:** `container_statuses`, `ready_replicas`, `updated_replicas`, `available_replicas` can be `None` before a pod/deployment settles — always coalesce with `or 0` / `or []`. Compute age relative to `datetime.now(timezone.utc)` since `creation_timestamp` is tz-aware.

## Common Pitfalls

### Pitfall 1: 403 rendered as the "outside cluster" panel
**What goes wrong:** A misconfigured RoleBinding silently shows the muted D-03 panel, masking the RBAC bug during the SC #4 verification.
**Why it happens:** Catching `ApiException` and returning `{"available": False}` conflates it with `(None, None)`.
**How to avoid:** Return distinct dict shapes: `{"available": False}` ONLY for `(None,None)`; `{"available": True, "error": "forbidden"}` for 403.
**Warning signs:** The pod is Running but the page shows "Not running in a cluster."

### Pitfall 2: Timeout propagates and 500s the page
**What goes wrong:** A hung API server makes `list_namespaced_pod` raise `MaxRetryError`, which is NOT an `ApiException`, so an `except ApiException`-only helper lets it escape → 500 (violates D-03 "never a 500").
**Why it happens:** `rest.py` doesn't wrap read timeouts into `ApiException`.
**How to avoid:** Add `except urllib3.exceptions.HTTPError` after the `ApiException` handler.
**Warning signs:** Intermittent 500s on `/partials/cluster-state` under API load.

### Pitfall 3: Label selector collision between the two charts
**What goes wrong:** Installing both charts into one namespace with identical `app.kubernetes.io/name` makes each Service's selector match both apps' pods → traffic misroutes.
**Why it happens:** Copying `_helpers.tpl` without swapping the prefix.
**How to avoid:** Mechanical `field-guide-api.*` → `launchpad.*` rename; verify with `helm template ... | grep app.kubernetes.io/name`.
**Warning signs:** `helm lint` passes but the launchpad Service Endpoints list field-guide-api pods.

### Pitfall 4: Missing `POD_NAMESPACE` → wrong namespace queried
**What goes wrong:** Without the Downward API env, the helper defaults to `"default"` and lists nothing (or 403s if the Role isn't there).
**Why it happens:** Forgetting the `fieldRef` env in deployment.yaml.
**How to avoid:** Add the `POD_NAMESPACE` env block; test both "env set" and "env absent → default" paths.
**Warning signs:** Empty pods table in-cluster despite running pods.

### Pitfall 5: 100% coverage gate misses a branch
**What goes wrong:** `--cov-fail-under=100` fails the suite if any of the four branches (none/success/403/timeout) is untested, or an `or 0`/`or []` guard line is unhit.
**Why it happens:** New multi-branch helper.
**How to avoid:** One test per branch (see Testing section); include a fake pod with `container_statuses = None` to hit the coalesce.

## Testing Strategy (100% coverage gate)

The existing `conftest.py` already provides `k8s_enabled` (fake `CoreV1Api`/`AppsV1Api` MagicMocks) and `k8s_disabled` ((None,None)) fixtures — reuse them. For `get_cluster_state()` set return values / side effects on the fake API methods.

**Branch 1 — outside cluster (D-03):** use `k8s_disabled`; assert `{"available": False}`; partial renders the muted panel copy "Not running in a cluster — Kubernetes view disabled".

**Branch 2 — cluster present, success:** with `k8s_enabled`, make the fake `list_namespaced_pod` return a fake `V1PodList`-shaped object. Fake shape to build with `MagicMock` / `SimpleNamespace`:
```python
from types import SimpleNamespace
from datetime import datetime, timezone

fake_pod = SimpleNamespace(
    metadata=SimpleNamespace(name="launchpad-abc", creation_timestamp=datetime.now(timezone.utc)),
    status=SimpleNamespace(
        phase="Running",
        container_statuses=[SimpleNamespace(ready=True, restart_count=0)],
    ),
)
fake_pod_list = SimpleNamespace(items=[fake_pod])
core_v1, apps_v1 = k8s_enabled
core_v1.list_namespaced_pod.return_value = fake_pod_list

fake_dep = SimpleNamespace(
    metadata=SimpleNamespace(name="launchpad"),
    spec=SimpleNamespace(replicas=1),
    status=SimpleNamespace(ready_replicas=0, updated_replicas=1, available_replicas=0),
)
apps_v1.list_namespaced_deployment.return_value = SimpleNamespace(items=[fake_dep])
```
Assert the returned dict has `pods`/`deployments` with the mapped columns; assert `_request_timeout=5` was passed (`core_v1.list_namespaced_pod.assert_called_once_with("launchpad", _request_timeout=5)` after `monkeypatch.setenv("POD_NAMESPACE", "launchpad")`). Also include a pod with `container_statuses=None` to cover the `or []` guard.

**Branch 3 — 403 (RBAC missing):** `core_v1.list_namespaced_pod.side_effect = ApiException(status=403, reason="Forbidden")` (import `from kubernetes.client.exceptions import ApiException`); assert `{"available": True, "error": "forbidden"}`.

**Branch 4 — timeout/unreachable:** `core_v1.list_namespaced_pod.side_effect = urllib3.exceptions.MaxRetryError(pool=None, url="/api")` (or any `HTTPError` subclass); assert `{"available": True, "error": "unreachable"}`. Also cover a non-403 `ApiException` (e.g. status=500) hitting the `"unreachable"` branch.

**Route tests (`test_partials.py`):** mirror the existing `status_cards` tests — one `HX-Request: true` → fragment (no `<html>`), one no-header → full page (has `<html>`); use `k8s_disabled` so no cluster is needed; assert 200 and the muted-panel copy for the fragment.

All branches are mockable with zero real cluster/network, satisfying `--cov-fail-under=100`. `[VERIFIED: conftest.py fixtures + pytest.ini]`

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `kubernetes` Python client | DIAG-02 route | ✓ | 36.0.2 | — (already installed) |
| Helm | DEP-01 lint/template | Assumed ✓ (locked stack, Helm 3.21.2/4.x) | per CLAUDE.md | — |
| kind cluster + local registry | SC #2 (deploy + Running) | Runtime-dependent (must be up for SC #2) | kind v0.32.0 | Chart authoring + `helm lint` + unit tests don't need a live cluster; only SC #2 manual verify does |
| Docker | Build `localhost:5001/launchpad:latest` | Assumed ✓ (locked stack) | 27.x | — |

**Missing dependencies with no fallback:** none for authoring/lint/test. SC #2 (pod reaches Running) requires a live kind cluster + the launchpad image built and `kind load`-ed — the Makefile targets that automate this are Phase 10, so SC #2 verification is a manual `docker build` + `kind load docker-image` + `helm install` sequence in Phase 8.

## Security Domain

`security_enforcement` is not disabled in config → included.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Local single-user platform; no auth in v1.1 (REQUIREMENTS Out of Scope) |
| V3 Session Management | no | No sessions |
| V4 Access Control | **yes** | **Kubernetes RBAC least-privilege** — namespace-scoped Role, get/list/watch only, no ClusterRole (SC #4 / DEP-02). This IS the phase's core access-control control. |
| V5 Input Validation | minimal | No user input on the diagnostics read path (GET only, no form) |
| V6 Cryptography | no | No new crypto; `MONGO_URI` stays in a Secret, never ConfigMap/env-literal (existing discipline) |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Over-privileged ServiceAccount (cluster-wide read) | Elevation of Privilege | Namespace-scoped `Role`, verbs limited to get/list/watch on pods+deployments (SC #4) |
| Secret leakage in K8s error surfaced to UI | Information Disclosure | Return generic `"error": "forbidden"/"unreachable"` strings — never `str(exception)` (mirrors `app/status.py` T-07-07 discipline: no hostname/stack-trace/URI leakage into HTML) |
| DoS via hung API socket stalling the single gunicorn worker | Denial of Service | `_request_timeout=5` on every K8s call (SC #5) — bounds the request the same way `FIELD_GUIDE_TIMEOUT_SECONDS` bounds the status check |
| MONGO_URI credential in ConfigMap/env-literal | Information Disclosure | Keep it in the Secret only (existing chart discipline) |

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Bitnami MongoDB Helm chart | Plain `mongo:7` manifests | Sep 2025 (Broadcom paywall) | N/A this phase (Mongo is Phase 9); noted in CLAUDE.md |
| Helm `--atomic` | `--rollback-on-failure` (Helm 4) | Helm 4 | Avoid `--atomic` in any Makefile target (Phase 10 concern) |
| Global client timeout | per-call `_request_timeout` | stable | SC #5 mandates per-call; still current in 36.0.2 |

**Deprecated/outdated:** none affecting this phase. `kubernetes==36.0.2` is the installed, pinned version — no upgrade in scope.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Helm CLI (3.21.2 or 4.x) is installed and on PATH in the dev/CI environment | Environment Availability | `helm lint`/`template` verification steps fail; low risk — locked stack, field-guide-api chart already exists and was linted |
| A2 | A kind cluster + local registry can be brought up for SC #2 manual verification (Makefile automation is Phase 10) | Environment Availability | SC #2 (pod Running) can't be demonstrated until Phase 10; the chart is still authored/linted/tested. Confirm whether SC #2 is verified manually in Phase 8 or deferred |
| A3 | `urllib3.exceptions.MaxRetryError` is the concrete type raised on `_request_timeout` expiry (vs. a bare `ReadTimeoutError`) | In-Cluster Auth Failure Modes | Low — catching the `HTTPError` base class covers both; verified that rest.py doesn't re-wrap read timeouts into ApiException |

## Open Questions

1. **[RESOLVED 2026-07-11, user decision]** Phase 8 verifies "pod reaches Running" via the manual loop (hand-run docker build + kind load + helm install); Phase 10 wraps it in `make` targets (DEP-04). ROADMAP SC #2 amended accordingly. Original question:
   **Is SC #2 (pod reaches Running) verified in Phase 8 or deferred to Phase 10?**
   - What we know: The Makefile targets (`build-launchpad`/`load-launchpad`/`deploy-launchpad`) that automate it are explicitly Phase 10 (DEP-04). SC #2 names those exact targets.
   - What's unclear: Whether Phase 8's DoD includes a manual `docker build` + `kind load docker-image localhost:5001/launchpad:latest` + `helm install` to prove Running, or whether SC #2 is exercised in Phase 10.
   - Recommendation: Author + `helm lint` + full unit-test the chart in Phase 8; treat the live-cluster "reaches Running" check as a manual verification step here (the loop can be run by hand) and let Phase 10 wrap it in `make`. Flag for the planner to confirm the DoD boundary.

2. **SA name: literal `launchpad` vs. templated.**
   - What we know: SC #4 mandates `serviceAccountName: launchpad` (literal).
   - Recommendation: Keep the SA `metadata.name: launchpad` literal; use the `fullname` helper only for Role/RoleBinding names. Resolved above — low risk.

## Sources

### Primary (HIGH confidence)
- Installed `kubernetes==36.0.2` source (venv) — `client/exceptions.py` (ApiException `.status`/`.reason`), `client/rest.py` (`_request_timeout`→`urllib3.Timeout`, GET only catches SSLError), `client/api/core_v1_api.py` (`_request_timeout` kwarg), `client/models/v1_pod_status.py`, `v1_container_status.py`, `v1_deployment_status.py`, `v1_object_meta.py`, `v1_pod_list.py` (field names), `config/incluster_config.py` (token/cert file paths)
- Repo code — `apps/launchpad/app/k8s.py`, `app/status.py`, `app/routes/partials.py`, `app/routes/status.py`, `app/config.py`, `app/__init__.py`, `tests/conftest.py`, `tests/test_k8s.py`, `tests/test_partials.py`, `pytest.ini`; `charts/field-guide-api/*` (all templates + values)
- `.planning/phases/08-helm-chart-k8s-diagnostics/08-CONTEXT.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `.planning/config.json`

### Secondary (MEDIUM confidence)
- `kubernetes.io/docs/reference/access-authn-authz/rbac` — Role/RoleBinding shape, `apiGroups` `""` (core/pods) vs `apps` (deployments) [CITED, standard RBAC knowledge]

### Tertiary (LOW confidence)
- None — all load-bearing claims verified against installed source.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; versions read from installed dist-info
- Architecture / failure modes: HIGH — exception types, `_request_timeout` behavior, and model field names verified against the installed 36.0.2 source
- Helm mirroring: HIGH — the analog chart was read in full; changes are mechanical
- RBAC shape: HIGH — standard, apiGroups verified against model semantics
- Testing: HIGH — existing fixtures cover all four branches

**Research date:** 2026-07-11
**Valid until:** 2026-08-10 (stable; kubernetes client + Helm chart pinned, no fast-moving deps)
