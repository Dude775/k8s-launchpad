---
phase: 08-helm-chart-k8s-diagnostics
verified: 2026-07-12T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 8: Helm Chart + K8s Diagnostics Verification Report

**Phase Goal:** The launchpad deploys to the kind cluster via Helm with correct label namespacing and RBAC; the diagnostics page shows real Kubernetes state inside the cluster and degrades gracefully outside it
**Verified:** 2026-07-12
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria, amended text)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `helm lint charts/launchpad/` passes with no warnings; `_helpers.tpl` uses `launchpad.*` prefix, no selector collision with field-guide-api chart | VERIFIED | Ran `helm lint charts/launchpad/` myself (helm v4.2.1): "1 chart(s) linted, 0 chart(s) failed", only an `[INFO] icon is recommended` note (not a warning/error). Ran `helm template launchpad charts/launchpad/`: renders 236 lines, `app.kubernetes.io/name: launchpad` throughout, zero occurrences of `app.kubernetes.io/name: field-guide-api`. Cross-checked by rendering `charts/field-guide-api/` directly — it emits `app.kubernetes.io/name: field-guide-api` / `field-guide-api-mongodb`, confirming no label overlap. |
| 2 | Manual deploy loop verified — pod reached Running in kind | VERIFIED | 08-01-SUMMARY.md records operator-approved checkpoint: `launchpad-555d88fcf8-n89ng 0/1 Running`. **Independently confirmed live** (read-only `kubectl`/`helm` inspection, no cluster mutation performed): `kubectl get pods` on context `kind-kind` shows `launchpad-555d88fcf8-n89ng 0/1 Running 0 13m` right now; `helm list` shows release `launchpad` (chart `launchpad-0.1.0`) STATUS `deployed`; `kubectl get sa launchpad` and `kubectl get role launchpad-read` both exist in-cluster with the expected shape. |
| 3 | `/diagnostics` lists pods/deployments in-cluster, shows "outside cluster" indicator (not 500) locally | VERIFIED | `make test-launchpad`-equivalent (`pytest` via project venv) run directly: 52 passed, 100% coverage, all four `get_cluster_state()` branches (outside-cluster, success incl. `container_statuses=None` coalesce, 403→forbidden, MaxRetryError/500→unreachable) exercised. Additionally ran the app live in-process: (a) with `k8s.get_k8s_clients` monkeypatched to `(None, None)`, `/partials/cluster-state` returned 200 with the exact muted copy `Not running in a cluster — Kubernetes view disabled`, never a 500; (b) with the real (unmocked) accessor against the live `kind-kind` context, the same route returned 200 and listed real pods including `launchpad-555d88fcf8-n89ng` and `field-guide-api-56968d96d7-...` — proving the in-cluster success branch renders genuine K8s API data, not a stub. |
| 4 | Deployment sets `serviceAccountName: launchpad`; namespace-scoped Role (not ClusterRole) grants only get/list/watch on pods and deployments | VERIFIED | `helm template` output: `serviceAccountName: launchpad` present; `rbac.yaml` renders `kind: ServiceAccount` (name `launchpad`), `kind: Role` (name `launchpad-read`, namespace-scoped — apiVersion `rbac.authorization.k8s.io/v1`), `kind: RoleBinding`. Zero occurrences of `kind: ClusterRole` or `kind: ClusterRoleBinding` in rendered output. Role rules: exactly two rule blocks — `apiGroups: [""]` → `resources: ["pods"]`, `apiGroups: ["apps"]` → `resources: ["deployments"]`, both `verbs: ["get","list","watch"]` only. Live-confirmed in-cluster via `kubectl get role launchpad-read -o yaml`. |
| 5 | All K8s API calls pass `_request_timeout=5` | VERIFIED | Source grep of `apps/launchpad/app/cluster_state.py`: both `core_v1.list_namespaced_pod(namespace, _request_timeout=K8S_REQUEST_TIMEOUT_SECONDS)` and `apps_v1.list_namespaced_deployment(namespace, _request_timeout=K8S_REQUEST_TIMEOUT_SECONDS)` carry the timeout, `K8S_REQUEST_TIMEOUT_SECONDS = 5`. A dedicated test (`test_cluster_state_no_list_namespaced_call_missing_timeout`) source-greps for this as a regression gate and passes. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `charts/launchpad/Chart.yaml` | Chart metadata, name: launchpad | VERIFIED | Present, `name: launchpad`, `apiVersion: v2` |
| `charts/launchpad/templates/_helpers.tpl` | launchpad.* naming/label helpers | VERIFIED | Defines `launchpad.name/fullname/chart/labels/selectorLabels`; no mongodb helpers; selectorLabels emits `app.kubernetes.io/name: {{ include "launchpad.name" . }}` |
| `charts/launchpad/templates/rbac.yaml` | ServiceAccount + Role + RoleBinding | VERIFIED | Three-document file exactly as specified; `kind: Role` never `ClusterRole` |
| `charts/launchpad/templates/deployment.yaml` | Deployment w/ SA + POD_NAMESPACE + /health probe | VERIFIED | `serviceAccountName: launchpad`, Downward API `POD_NAMESPACE`, `MONGO_URI` via `secretKeyRef`, readinessProbe `httpGet /health:8000` unweakened |
| `charts/launchpad/templates/secret.yaml` | MONGO_URI Secret placeholder | VERIFIED | `type: Opaque`, single `stringData.MONGO_URI` sourced from `.Values.mongoUri`, includes `serverSelectionTimeoutMS=2000` |
| `charts/launchpad/values.yaml` | image/config/mongoUri surface | VERIFIED | `repository: localhost:5001/launchpad`, `tag: latest`, `config.fieldGuideBaseUrl`, `config.appVersion`, top-level `mongoUri`; no `mongodb:` block, no `externalMongoUri` |
| `apps/launchpad/app/cluster_state.py` | get_cluster_state() never-raises helper | VERIFIED | 49 statements, 100% covered, four documented return shapes, module-attribute k8s import |
| `apps/launchpad/app/routes/partials.py` | /partials/cluster-state route | VERIFIED | Route added to existing `partials_bp`, HX-Request fragment/full-page branch mirrors status_cards |
| `apps/launchpad/app/templates/partials/cluster_state.html` | fragment: tables + muted/error panels | VERIFIED | No `{% extends %}`, no `<html>`; four distinct render branches match plan spec exactly |
| `apps/launchpad/app/templates/diagnostics.html` | two-section page w/ 10s poll | VERIFIED | Both `partials.status_cards` (15s) and `partials.cluster_state` (10s, visibility-guarded) sections present |
| `apps/launchpad/tests/test_cluster_state.py` | branch-per-outcome tests | VERIFIED | 13 tests covering all 4 branches + `_pod_age` edge cases + timeout source-grep gate |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `charts/launchpad/templates/deployment.yaml` | `charts/launchpad/templates/rbac.yaml` | `serviceAccountName: launchpad` | WIRED | Literal match confirmed in rendered output and live in-cluster pod spec |
| `charts/launchpad/templates/deployment.yaml` | `charts/launchpad/templates/secret.yaml` | `secretKeyRef` MONGO_URI | WIRED | Confirmed in rendered output |
| `apps/launchpad/app/routes/partials.py` | `apps/launchpad/app/cluster_state.py` | `from app.cluster_state import get_cluster_state` | WIRED | Import present, route calls `get_cluster_state()` |
| `apps/launchpad/app/cluster_state.py` | `apps/launchpad/app/k8s.py` | `from app import k8s` + `k8s.get_k8s_clients()` | WIRED (BLOCKER-3 regression check PASSED) | `grep "from app.k8s import get_k8s_clients"` returns nothing; module-attribute access confirmed, live-tested against real conftest monkeypatch fixtures and against the real kind cluster |
| `apps/launchpad/app/templates/diagnostics.html` | `/partials/cluster-state` | htmx `hx-get` every 10s | WIRED | `url_for('partials.cluster_state')` present, `every 10s` + visibility guard present |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `partials/cluster_state.html` | `state.pods` / `state.deployments` | `get_cluster_state()` → `core_v1.list_namespaced_pod()` / `apps_v1.list_namespaced_deployment()` | YES — live-verified against the real `kind-kind` cluster; returned actual pod rows for `launchpad-555d88fcf8-n89ng` and `field-guide-api-56968d96d7-...` | FLOWING |
| `partials/cluster_state.html` | `state.available == False` branch | `k8s.get_k8s_clients()` returning `(None, None)` | YES — live-verified by monkeypatching the real accessor and hitting the real route; returned the exact muted copy, HTTP 200 | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| helm lint clean | `helm lint charts/launchpad/` | 0 errors, 0 warnings (1 INFO) | PASS |
| helm template collision-free | `helm template launchpad charts/launchpad/ \| grep field-guide-api` | 0 matches for `app.kubernetes.io/name: field-guide-api` | PASS |
| No ClusterRole | `grep "kind: ClusterRole" <rendered>` | 0 matches | PASS |
| Test suite green at 100% | `pytest` (via project venv) | 52 passed, 100% coverage | PASS |
| /diagnostics renders both sections | live Flask test client `GET /diagnostics` | 200, both `status-cards` and `cluster-state` sections present, `every 10s` present | PASS |
| /partials/cluster-state degrades outside cluster | live Flask test client, `k8s.get_k8s_clients` monkeypatched to `(None, None)` | 200, muted panel copy present, no 500 | PASS |
| /partials/cluster-state shows real cluster data | live Flask test client against real `kind-kind` context (unmocked) | 200, real pod names listed including the launchpad pod itself | PASS |
| Live pod state matches SUMMARY claim | `kubectl get pods` on `kind-kind` | `launchpad-555d88fcf8-n89ng 0/1 Running` present right now | PASS |
| Live RBAC objects exist in-cluster | `kubectl get sa launchpad`, `kubectl get role launchpad-read -o yaml` | Both exist, Role rules match chart source | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DEP-01 | 08-01 | `charts/launchpad/` Helm chart deploys the dashboard; helm lint passes; no selector collision | SATISFIED | helm lint/template verified directly; live helm release `deployed` |
| DEP-02 | 08-01 | ServiceAccount + namespace-scoped Role + RoleBinding, read-only pods/deployments | SATISFIED | rbac.yaml rendered + live-confirmed in-cluster |
| DIAG-01 | 08-02 | In-app platform checks run without a cluster | SATISFIED | `/diagnostics` Platform Checks section reuses Phase-7 status-cards, renders live regardless of cluster state |
| DIAG-02 | 08-02 | Read-only K8s state via in-cluster SA, degrades gracefully outside cluster | SATISFIED | Live-tested both branches (real cluster data + muted outside-cluster panel), zero 500s |

All four requirements marked `[x]` complete in REQUIREMENTS.md, consistent with codebase evidence. No orphaned requirements found for Phase 8 in REQUIREMENTS.md traceability table.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| charts/launchpad/templates/secret.yaml | 4 | "LOCAL DEV PLACEHOLDER ONLY" comment | None (informational) | Intentional, documented, non-secret local-dev default per D-07; not a stub/debt marker — no TBD/FIXME/XXX found anywhere in phase-modified files |

No blocker or warning anti-patterns found. No `TBD`/`FIXME`/`XXX`/`TODO`/`HACK` markers in any file created/modified by this phase.

### Scope Creep Check

- No `templates/mongodb/` directory in `charts/launchpad/` — confirmed absent (correctly deferred to Phase 9 per D-06/DEP-03).
- No new Makefile deploy targets added in Phase 8 — `git log --oneline -- Makefile` shows the launchpad target stubs were added in `44bcc5c feat(05-02)`, not touched by Phase 8 commits. The stubs still echo "available in Phase 8" but this pre-existing text belongs to Phase 5 scaffolding, not new Phase 8 work — consistent with D-09 (manual loop only, `make deploy-launchpad` deferred to Phase 10 / DEP-04).
- `grep -r field-guide-api charts/launchpad/` returns exactly one hit: `values.yaml`'s `config.fieldGuideBaseUrl: http://field-guide-api`, which is the mandated in-cluster Service DNS default (not leaked analog boilerplate) — confirmed this is functional wiring, not a collision risk, since it never touches label/selector fields.

### Human Verification Required

None. All must-haves were verified programmatically, including a live check against the actual running kind cluster (read-only inspection only — no deploy/mutate operations performed, per the constraint given).

### Gaps Summary

No gaps found. All 5 amended ROADMAP success criteria, all must-haves from both 08-01-PLAN.md and 08-02-PLAN.md frontmatter, and all four requirements (DEP-01, DEP-02, DIAG-01, DIAG-02) are verified against live codebase evidence — not merely SUMMARY.md claims. Verification went beyond static inspection: `helm lint`/`helm template` were re-run independently, the full test suite was re-run independently (52/52 passing, 100% coverage), and the live kind cluster was inspected (read-only) confirming the launchpad Helm release is actually deployed with the pod in the exact state (`0/1 Running`) the 08-01-SUMMARY.md claims, plus the diagnostics route was exercised live against that real cluster and correctly listed real pod data.

---

*Verified: 2026-07-12*
*Verifier: Claude (gsd-verifier)*
