# Phase 8: Helm Chart + K8s Diagnostics - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-11
**Phase:** 8-helm-chart-k8s-diagnostics
**Areas discussed:** Diagnostics page layout, "Outside cluster" degradation, Refresh behavior, Helm chart shape + readinessProbe

---

## Diagnostics page layout

| Option | Description | Selected |
|--------|-------------|----------|
| Two stacked sections | Platform Checks (status-cards) on top; Cluster State with pods + deployments tables below | ✓ |
| Cards only, no tables | Every check and pod/deployment as an individual card in a grid | |
| Single unified table | One table interleaving checks and K8s workloads | |

**User's choice:** Two stacked sections
**Notes:** Pods table columns name · phase · ready n/m · restarts · age; deployments table name · ready · up-to-date · available. Reuses base.html shell + status-card fragment from Phases 6–7.

---

## "Outside cluster" degradation

| Option | Description | Selected |
|--------|-------------|----------|
| Checks live, K8s panel disabled | Platform Checks render live; Cluster State shows a muted "Kubernetes view disabled" panel | ✓ |
| Hide K8s section entirely | Omit Cluster State completely outside a cluster | |
| Empty tables with inline note | Render empty table headers with an "outside cluster" caption | |

**User's choice:** Checks live, K8s panel disabled
**Notes:** Never 500 (SC #3). Platform Checks (MongoDB ping etc.) work without a cluster; only the K8s tier degrades, via `get_k8s_clients()` returning `(None, None)`.

---

## Refresh behavior

| Option | Description | Selected |
|--------|-------------|----------|
| htmx auto-poll, 10s, visibility-guarded | Cluster State swaps via htmx partial every 10s, pausing when tab hidden | ✓ |
| Auto-poll, slower 30s | Same mechanism, 30s interval | |
| Load once + manual Refresh button | Fetch on load, user clicks to re-query | |

**User's choice:** htmx auto-poll, 10s, visibility-guarded
**Notes:** Same pattern as Phase 6–7 status cards. K8s queries scoped to launchpad's own namespace only (a cluster-wide list would 403 under the namespace-scoped Role anyway).

---

## Helm chart shape + readinessProbe sequencing

| Option | Description | Selected |
|--------|-------------|----------|
| Mirror field-guide chart; readinessProbe on /health now | Mirror charts/field-guide-api minus mongodb/; probe → /health now, pod NotReady until Phase 9 | ✓ |
| Mirror chart; defer readinessProbe to Phase 9 | Same layout, omit probe until Mongo exists so pod reaches Ready now | |
| Mirror chart; readinessProbe on a Mongo-free endpoint | Point probe at a bare-200 endpoint now, switch to /health in Phase 9 | |

**User's choice:** Mirror field-guide chart; readinessProbe on /health now
**Notes:** Orchestrator flagged the sequencing tension up front — launchpad's own Mongo lands in Phase 9 (DEP-03), so /health returns 503 and the pod stays NotReady until then. Accepted because SC #2 only requires `Running`. The locked Phase-7 readinessProbe contract is honored, not weakened. Image `localhost:5001/launchpad:latest`; values.yaml mirrors field-guide-api plus FIELD_GUIDE_BASE_URL/APP_VERSION/MONGO_URI wiring.

---

## Claude's Discretion

- Table styling / column widths, NOTES.txt wording, values.yaml default resource limits.
- Whether Platform Checks poll or render-once (the K8s Cluster State tier is the one that polls at 10s).

## Deferred Ideas

- launchpad's own MongoDB manifests — DEP-03, Phase 9 (also flips pod NotReady → Ready).
- Makefile build/load/deploy-launchpad + up-all + smoke — DEP-04/05, Phase 10.
- Research flag: `serviceAccountName` + `load_incluster_config()` failure modes — no token = clean `ConfigException` (graceful degrade) vs wrong SA = silent 403 on list (distinct handling, not a None return). Confirm during planning.
