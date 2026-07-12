---
phase: 08
slug: helm-chart-k8s-diagnostics
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-12
---

# Phase 08 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| launchpad pod → Kubernetes API | The pod's ServiceAccount identity is what the K8s API authorizes; over-grant here is a privilege risk | RBAC-scoped read calls (pods, deployments) |
| chart Secret → pod env | MONGO_URI must reach the pod only via a Secret, never a ConfigMap or plaintext literal | MongoDB connection string (local-dev placeholder) |
| two charts in one namespace | field-guide-api and launchpad Services must not cross-select each other's pods | Label-selector match surface |
| launchpad app → Kubernetes API (runtime) | Untrusted/failable network call; response drives rendered HTML | Pod/Deployment list responses, API errors |
| K8s API error → rendered page | Exception detail must not leak into HTML; failures must not 500 | Exception objects vs. rendered dict/HTML |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-08-01 | Elevation of Privilege | `charts/launchpad/templates/rbac.yaml` | mitigate | Namespace-scoped `Role` (never `ClusterRole`); verbs limited to `get`/`list`/`watch` on `pods` (core) + `deployments` (apps) | closed |
| T-08-02 | Information Disclosure | `charts/launchpad/templates/secret.yaml`, `deployment.yaml` | mitigate | `MONGO_URI` sourced only via `secretKeyRef`; placeholder is local-dev value, not a real credential | closed |
| T-08-03 | Spoofing / mis-routing | `charts/launchpad/templates/_helpers.tpl` | mitigate | Distinct `app.kubernetes.io/name: launchpad` selector label; rendered output never emits `field-guide-api` name label | closed |
| T-08-04 | Tampering (image supply chain) | manual `docker build` / `kind load` loop | mitigate | Image built locally from `./apps/launchpad`, pushed only to `localhost:5001` / loaded into kind — no external pull | closed |
| T-08-05 | Denial of Service | `apps/launchpad/app/cluster_state.py` list calls | mitigate | `_request_timeout=5` (`K8S_REQUEST_TIMEOUT_SECONDS`) on every `list_namespaced_*` call; source-grep test enforces | closed |
| T-08-06 | Information Disclosure | `apps/launchpad/app/cluster_state.py` exception handling | mitigate | Generic `"forbidden"`/`"unreachable"` strings only; no `str(exception)` anywhere in the module | closed |
| T-08-07 | Elevation of Privilege / masking | 403 handling in `cluster_state.py` | mitigate | 403 renders a DISTINCT error panel (`Kubernetes access denied`), never the muted outside-cluster panel; separately tested branch | closed |
| T-08-08 | Denial of Service | timeout not `ApiException` in `cluster_state.py` | mitigate | `except urllib3.exceptions.HTTPError` explicitly catches `MaxRetryError`/read-timeout; no raw 500; tested via `side_effect` | closed |
| T-08-09 | Elevation of Privilege | namespace scope in `cluster_state.py` | mitigate | Only `*_namespaced_*` calls, scoped to `POD_NAMESPACE`; no `_for_all_namespaces` anywhere in module | closed |
| T-08-SC | Tampering | package installs (chart authoring / app deps) | accept | No package-manager installs occurred in this phase — chart authored from an existing analog; app reuses already-pinned requirements | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Evidence

| Threat ID | Evidence |
|-----------|----------|
| T-08-01 | `charts/launchpad/templates/rbac.yaml:14-26` — `kind: Role` (namespace-scoped), rules limited to `apiGroups: [""]`/`resources: ["pods"]` and `apiGroups: ["apps"]`/`resources: ["deployments"]`, both `verbs: ["get","list","watch"]`. `helm lint charts/launchpad/` → `0 chart(s) failed`. `helm template launchpad charts/launchpad/` rendered `kind:` lines: `ServiceAccount, Secret, ConfigMap, Role, RoleBinding, Service, Deployment` — zero `ClusterRole`/`ClusterRoleBinding` occurrences (verified via full-file `^kind:` grep, not a substring match). |
| T-08-02 | `charts/launchpad/templates/secret.yaml:9-17` — `type: Opaque`, `stringData.MONGO_URI` sourced from `.Values.mongoUri` (placeholder `mongodb://localhost:27017/launchpad?serverSelectionTimeoutMS=2000`, documented as local-dev-only, never a real credential). `deployment.yaml:57-61` — `MONGO_URI` env sourced exclusively via `secretKeyRef`; `configmap.yaml` contains no `MONGO_URI` key. Rendered template confirms `secretKeyRef` present, no plaintext Mongo credential in ConfigMap/env literal. |
| T-08-03 | `charts/launchpad/templates/_helpers.tpl:61-64` — `launchpad.selectorLabels` emits `app.kubernetes.io/name: {{ include "launchpad.name" . }}` which resolves to `launchpad`. `helm template launchpad charts/launchpad/` output greped for `app.kubernetes.io/name: field-guide-api` → no match (`NO_COLLISION`). |
| T-08-04 | `.planning/phases/08-helm-chart-k8s-diagnostics/08-01-SUMMARY.md` Checkpoint Result — manual deploy loop executed and approved by operator (2026-07-12): `docker build -t localhost:5001/launchpad:latest ./apps/launchpad`, loaded/pushed to `localhost:5001`, `helm install` → pod `Running`. No external image reference anywhere in `charts/launchpad/values.yaml` (`image.repository: localhost:5001/launchpad`). |
| T-08-05 | `apps/launchpad/app/cluster_state.py:106-107` — both `list_namespaced_pod` and `list_namespaced_deployment` calls pass `_request_timeout=K8S_REQUEST_TIMEOUT_SECONDS` (constant = 5, line 31). Enforced by `apps/launchpad/tests/test_cluster_state.py::test_cluster_state_no_list_namespaced_call_missing_timeout` (source-grep gate) and `test_success_maps_pods_and_deployments` asserting `assert_called_once_with("launchpad", _request_timeout=5)`. Live pytest run: 52 passed, `cluster_state.py` 100% coverage. |
| T-08-06 | `apps/launchpad/app/cluster_state.py:108-113` — `except ApiException` and `except urllib3.exceptions.HTTPError` both return fixed strings (`"forbidden"` / `"unreachable"`); no `str(exc)` / exception interpolation anywhere in the module (confirmed by full-file read — only docstring references the discipline, no live leak). |
| T-08-07 | `apps/launchpad/app/cluster_state.py:108-110` — `if exc.status == 403: return {"available": True, "error": "forbidden"}`, distinct from the `{"available": False}` outside-cluster shape. `apps/launchpad/app/templates/partials/cluster_state.html:6-10` renders a separate `status-card--degraded` panel with copy `Kubernetes access denied — check RBAC`, distinct from the `status-card--unknown` muted panel (lines 1-5). Tested by `test_forbidden_403_returns_distinct_error`. |
| T-08-08 | `apps/launchpad/app/cluster_state.py:112-113` — `except urllib3.exceptions.HTTPError:` catches `MaxRetryError` explicitly (ordered after `ApiException`, since `ApiException` is not an `HTTPError` subclass), returns `{"available": True, "error": "unreachable"}`. Tested by `test_max_retry_error_returns_unreachable` using `side_effect = urllib3.exceptions.MaxRetryError(...)`. |
| T-08-09 | `apps/launchpad/app/cluster_state.py` — only `list_namespaced_pod` / `list_namespaced_deployment` calls present; `namespace = os.environ.get("POD_NAMESPACE", "default")` (line 103). Grep for `list_pod_for_all_namespaces`/`list_deployment_for_all_namespaces`/`ClusterRole` in the module: no matches. |
| T-08-SC | This entry — see Accepted Risks Log below. |

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-08-SC-01 | T-08-SC | No package-manager installs (npm/pip/cargo) occurred during Phase 8 — `charts/launchpad/` was authored by mirroring the already-audited `charts/field-guide-api/` analog, and `apps/launchpad/`'s Python dependencies were already pinned/installed in prior phases. Per-phase Package Legitimacy Audit is not applicable this phase. | gsd-security-auditor (automated audit) | 2026-07-12 |

*Accepted risks do not resurface in future audit runs.*

---

## Unregistered Flags

None. Both `.planning/phases/08-helm-chart-k8s-diagnostics/08-01-SUMMARY.md` and `08-02-SUMMARY.md` were checked for a `## Threat Flags` section — neither contains one. No new attack surface was flagged by the executor beyond the threats already in the register.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-12 | 10 | 10 | 0 | gsd-security-auditor |

**Verification commands run (read-only):**
- `helm lint charts/launchpad/` → `1 chart(s) linted, 0 chart(s) failed` (one informational `icon is recommended` notice only)
- `helm template launchpad charts/launchpad/` → rendered successfully; `^kind:` lines confirmed as exactly `ServiceAccount, Secret, ConfigMap, Role, RoleBinding, Service, Deployment` (no ClusterRole/ClusterRoleBinding); no `app.kubernetes.io/name: field-guide-api`; `serviceAccountName: launchpad`, `fieldPath: metadata.namespace`, `secretKeyRef`, `path: /health` all present
- `apps/launchpad/.venv/Scripts/python.exe -m pytest -q --cov=app --cov-report=term-missing` → 52 passed, 100% total coverage, `app/cluster_state.py` 49/49 statements covered
- `grep -rn field-guide-api charts/launchpad/` → only `values.yaml:34 fieldGuideBaseUrl: http://field-guide-api` (mandated functional Service DNS default, documented in 08-01-SUMMARY.md as intentional, not a leftover analog reference)

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-12
