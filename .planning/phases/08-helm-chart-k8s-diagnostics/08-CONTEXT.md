# Phase 8: Helm Chart + K8s Diagnostics - Context

**Gathered:** 2026-07-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Deploy the launchpad dashboard to the local kind cluster via a Helm chart with correct
`launchpad.*` label namespacing and least-privilege RBAC, and build the `/diagnostics` page
that shows real read-only Kubernetes state (pods/deployments) inside the cluster while degrading
gracefully to an "outside cluster" state when no cluster is reachable.

Requirements: DEP-01 (chart), DEP-02 (ServiceAccount + Role + RoleBinding), DIAG-01 (in-app
platform checks that run without a cluster), DIAG-02 (read-only K8s state via in-cluster SA).

**Out of scope (locked elsewhere):** launchpad's own MongoDB manifests (DEP-03 → Phase 9);
service catalog / events CRUD (Phase 9); Makefile `up-all` + smoke integration (DEP-04/05 → Phase 10).
</domain>

<decisions>
## Implementation Decisions

### Diagnostics page layout (DIAG-01 + DIAG-02)
- **D-01:** `/diagnostics` renders as **two stacked sections**. Top: **"Platform Checks"** as
  status-cards (MongoDB ping, self-health, config/version) — the DIAG-01 in-app tier that runs
  without a cluster. Below: **"Cluster State"** (DIAG-02) with a **pods table** (columns:
  name · phase · ready `n/m` · restarts · age) and a **deployments table** (columns:
  name · ready · up-to-date · available).
- **D-02:** Reuse the Phase 6–7 UI shell verbatim — `base.html`, the sidebar nav (`/diagnostics`
  already present), and the status-card fragment/partial pattern for the Platform Checks tier.

### "Outside cluster" degradation (SC #3 — never 500)
- **D-03:** When `get_k8s_clients()` returns `(None, None)`, **Platform Checks still render live**
  (MongoDB ping, self-health, version all work without a cluster). The **Cluster State** section
  renders a **muted, labeled "Not running in a cluster — Kubernetes view disabled" panel** in place
  of the pods/deployments tables. Never a 500, never empty-looking tables, never a hidden section.

### Refresh behavior
- **D-04:** The **Cluster State** section auto-refreshes via **htmx polling every 10s**, using the
  **visibility guard** (pause when the tab is hidden) established in Phases 6–7. The section swaps
  through a dedicated htmx **partial** endpoint (mirrors the status-cards partial pattern). Platform
  Checks may reuse the same live-refresh mechanism or render on load — planner's discretion, but the
  K8s tier is the one that polls.
- **D-05:** K8s queries are scoped to **launchpad's own namespace only** (from the pod's namespace,
  e.g. Downward API `POD_NAMESPACE` / config) — never all-namespaces. Consistent with the
  namespace-scoped Role in DEP-02 (a cluster-wide list would 403 under least-privilege RBAC anyway).

### Helm chart shape + readinessProbe sequencing
- **D-06:** `charts/launchpad/` **mirrors `charts/field-guide-api/` verbatim, minus the `mongodb/`
  subchart** (launchpad's Mongo manifests are deferred to DEP-03 / Phase 9). Files: `Chart.yaml`,
  `templates/_helpers.tpl` (with the `launchpad.*` name/label prefix per SC #1 to avoid selector
  collision when both charts share a namespace), `deployment.yaml`, `service.yaml`, `configmap.yaml`,
  `secret.yaml`, `values.yaml`, `NOTES.txt`, `.helmignore`.
- **D-07:** Image reference convention `localhost:5001/launchpad:latest` (the local-registry pattern
  from v1.0). `values.yaml` surface mirrors field-guide-api's (image repo/tag, replicas, resources)
  plus wiring for `FIELD_GUIDE_BASE_URL`, `APP_VERSION`, and `MONGO_URI` (the latter via the chart's
  Secret even though the Mongo backend arrives in Phase 9).
- **D-08:** **readinessProbe points at `/health` now** (honors the locked Phase-7 readinessProbe
  contract). Consequence, accepted: because launchpad's own MongoDB is not deployed until Phase 9,
  `/health` returns 503 → the pod runs but stays **NotReady** until Phase 9 adds Mongo. This is fine —
  **SC #2 only requires the pod to reach `Running`**, not `Ready`. Do NOT weaken the probe to a
  Mongo-free endpoint or defer it; the contract is exercised as designed.

### Locked by ROADMAP success criteria (not re-decided here)
- `_helpers.tpl` uses `launchpad.*` prefix (SC #1) · `serviceAccountName: launchpad` (SC #4) ·
  namespace-scoped Role granting only `get`/`list`/`watch` on `pods` and `deployments`, NOT a
  ClusterRole (SC #4) · all K8s API calls pass `_request_timeout=5` (SC #5).

### Claude's Discretion
- Exact table styling / column widths, NOTES.txt wording, values.yaml default resource limits,
  and whether Platform Checks poll or render-once (see D-04) are planner/executor discretion within
  the decisions above.
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase spec & requirements
- `.planning/ROADMAP.md` §"Phase 8: Helm Chart + K8s Diagnostics" — goal + 5 success criteria (the locked contract)
- `.planning/REQUIREMENTS.md` — DEP-01, DEP-02, DIAG-01, DIAG-02 (full requirement text + traceability)

### Helm chart analog (mirror this)
- `charts/field-guide-api/` — complete chart to mirror for `charts/launchpad/` (Chart.yaml, `templates/_helpers.tpl`, deployment/service/configmap/secret, values.yaml, NOTES.txt, .helmignore). **Exclude** `templates/mongodb/` — deferred to Phase 9 (DEP-03).

### Kubernetes client (reuse, do not rebuild)
- `apps/launchpad/app/k8s.py` — `get_k8s_clients()` lazy per-request accessor: in-cluster→kubeconfig fallback (D-05), returns `(None, None)` outside a cluster, no caching (D-06). Built in Phase 5 specifically for these routes.
- `.planning/phases/05-monorepo-scaffold-app-factory/05-CONTEXT.md` — original k8s.py decisions (fallback order, no-caching rationale) locked as D-05/D-06 there.

### UI shell & patterns to extend (Phases 6–7)
- `apps/launchpad/app/routes/pages.py` — page routes (`/diagnostics` page route to flesh out)
- `apps/launchpad/app/routes/partials.py` — htmx partial routes (add a Cluster State partial here)
- `apps/launchpad/app/templates/base.html` + the status-card fragment under `app/templates/partials/` — the shell and card pattern to reuse for Platform Checks
- `apps/launchpad/app/routes/status.py` + `app/status.py` — Phase-7 aggregation + htmx `HX-Request` branching precedent for the Platform Checks tier and the polling partial

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `get_k8s_clients()` (`app/k8s.py`): the entire cluster-vs-outside detection is already solved —
  diagnostics routes call it per-request and branch on `None` for the D-03 degraded panel.
- `charts/field-guide-api/`: a full, `helm lint`-clean chart to copy-and-rename (the `_helpers.tpl`
  prefix swap to `launchpad.*` is the load-bearing change for SC #1).
- Status-card fragment + htmx visibility-guarded polling (Phases 6–7): drop-in for the Platform
  Checks tier and the 10s Cluster State poll (D-04).

### Established Patterns
- Lazy K8s client, per-request, never at import/create_app time (D-05/D-06 from Phase 5) — keeps
  `create_app()` cluster-free and unit-testable.
- htmx partial + `HX-Request` branch (Phase 7 `/api/status` ↔ `/partials/status-cards`) — the model
  for the Cluster State polling partial.
- 100% coverage gate on the launchpad suite (`pytest.ini --cov-fail-under=100`) — diagnostics
  routes' cluster-present AND cluster-absent branches must both be tested (mock `get_k8s_clients`).

### Integration Points
- New `/diagnostics` full-page route + a new Cluster State htmx partial route wire into the existing
  `pages_bp` / `partials_bp` blueprints and `base.html` sidebar.
- The Helm `deployment.yaml` readinessProbe → `/health` connects Phase 7's readiness contract to the
  running pod (D-08); the `serviceAccountName` + Role/RoleBinding connect the in-cluster SA to
  `load_incluster_config()` inside `get_k8s_clients()`.
</code_context>

<specifics>
## Specific Ideas

- Pod row columns: name · phase · ready `n/m` · restarts · age. Deployment row columns:
  name · ready · up-to-date · available. (Mirrors `kubectl get pods` / `get deployments` mental model.)
- Degraded copy: "Not running in a cluster — Kubernetes view disabled" (muted panel, not an error).
</specifics>

<deferred>
## Deferred Ideas

- **launchpad's own MongoDB manifests** — DEP-03, Phase 9 (chart's `mongodb/` subchart; also flips
  the pod from NotReady → Ready by satisfying `/health`).
- **Makefile `build-launchpad`/`load-launchpad`/`deploy-launchpad` + `up-all` + smoke** — DEP-04/05,
  Phase 10. Phase 8 assumes these targets may be added later; the chart must be deploy-ready for them.

**Research flag carried from STATE.md:** confirm `serviceAccountName` + `load_incluster_config()`
failure modes during planning — *no token* = clean `ConfigException` (→ graceful degrade) vs
*wrong ServiceAccount* = silent 403 on list (→ needs handling, not a None return). The 403 path is
NOT the same as the outside-cluster path and must be handled distinctly.

</deferred>

---

*Phase: 8-helm-chart-k8s-diagnostics*
*Context gathered: 2026-07-11*
