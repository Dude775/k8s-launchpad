# Phase 11: Observability Stack Install - Context

**Gathered:** 2026-07-16
**Status:** Ready for planning

<domain>
## Phase Boundary

A trimmed `kube-prometheus-stack` (Prometheus Operator + Prometheus + Grafana + kube-state-metrics; Alertmanager, node-exporter, default rules, and kind-incompatible kubeadm scrape jobs disabled) runs in its own `observability` namespace on the kind cluster, installed from `infra/observability/`, with a documented CRD teardown policy — and without disturbing the already-running v1.1 apps (field-guide-api + launchpad). Requirements: OBS-01, OBS-02.

Out of this phase: ServiceMonitors (Phase 12), Grafana dashboards (Phase 13), Makefile targets (Phase 14 — this phase delivers the scripts the targets will wrap), any launchpad code or UI work (Phases 15-16).

**Hard constraint (milestone-wide):** ADDITIVE ONLY — nothing from v1.1 is deleted, rewritten, or behavior-changed; existing smoke tests pass unchanged.

</domain>

<decisions>
## Implementation Decisions

### CRD Teardown Policy (OBS-02)
- **D-01:** `observability-down` keeps CRDs — `helm uninstall` only, matching Helm's default behavior. Faster re-install during the v2.0 dev loop; zero cascade-delete risk to Phase 12 ServiceMonitors. Leftover CRDs documented as an accepted limitation in `docs/known-limitations.md` per the project's existing accepted-risk convention.
- **D-02:** Teardown deletes the `observability` namespace (sweeps leftover secrets/configmaps/ephemeral resources). CRDs are cluster-scoped and survive namespace deletion.
- **D-03:** Teardown ends with a built-in verification that the v1.1 app pods (field-guide-api, launchpad) are still healthy — success criterion 3 is enforced by the script itself, matching the self-verifying `cluster-setup.sh` style.

### Install Mechanism (OBS-01)
- **D-04:** Install is driven by idempotent wrapper scripts — `scripts/observability-up.sh` and `scripts/observability-down.sh` — mirroring the existing `scripts/cluster-setup.sh` pattern (idempotent re-runs, self-verifying, POSIX/Git-Bash-safe). Phase 14 wraps these in `make` targets without re-implementing logic.
- **D-05:** Chart sourced via `helm repo add prometheus-community` + `helm upgrade --install --version 87.16.1` (pinned). No vendored chart tarball in git.
- **D-06:** Install script fully self-verifies: waits for all observability pods Running/Ready, then re-checks that the v1.1 app pods are still healthy (no eviction/restart) on every install — catching shared-node resource regressions immediately, not at milestone audit.

### Grafana Admin Credentials
- **D-07:** Explicit known local-dev admin password set in `infra/observability/values-trimmed.yaml` (not the chart default, not .env-driven). Documented in `docs/known-limitations.md` exactly like the v1.1 committed local-dev MongoDB password precedent — local kind only, override for anything real.
- **D-08:** Anonymous viewer access enabled in Grafana (`grafana.ini` anonymous auth, Viewer role) so Phase 15's "Open in Grafana" deep links open without a login wall during demos. Admin login retained for editing. Noted in known-limitations.md.

### Resource Sizing
- **D-09:** Conservative explicit `resources.requests/limits` on every component in `values-trimmed.yaml` from the very first install (research-derived starting values), then verified live with `kubectl top`/`describe` and tuned within this phase. Never install unbounded.
- **D-10:** Install script runs a preflight capacity check before installing: sum the stack's requests, compare against kind node allocatable minus already-running workloads, and **abort with an actionable message** (e.g. "raise Docker Desktop memory to X GB") if it won't fit. Protects the additive-only guarantee before anything lands on the node.
- **D-11:** Prometheus storage is emptyDir (no PVC), retention ~24h — enough for Phase 13's rolling-window uptime panels, lightest footprint, nothing to sweep on teardown. Fits the disposable local demo cluster.

### Claude's Discretion
- Exact per-component request/limit numbers in `values-trimmed.yaml` (starting from research values; live-tuned per D-09).
- Helm `--wait`/timeout strategy vs. script-level `kubectl wait` loops.
- values file layout within `infra/observability/` (single `values-trimmed.yaml` assumed).
- Double-run idempotency details for both scripts (follow the "double-safe teardown" precedent from Phase 2).
- Scrape interval default (coordinate with Phase 13's rate-window sizing pitfall: windows >= 4x scrape interval).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v2.0 Research (grounds every decision above)
- `.planning/research/SUMMARY.md` — executive research summary: trimmed-stack composition, build order, top pitfalls
- `.planning/research/STACK.md` — chart 87.16.1 pin, component enable/disable flags, version matrix
- `.planning/research/PITFALLS.md` — kubeadm scrape-job noise, resource exhaustion, CRD lifecycle tradeoff (pitfalls 1, 7, 8 map to this phase)
- `.planning/research/ARCHITECTURE.md` — infra/observability/ seam layout, namespace split, build order rationale

### Project conventions this phase must follow
- `docs/known-limitations.md` — accepted-risk documentation convention (D-01, D-07, D-08 land here)
- `scripts/cluster-setup.sh` — the idempotent, self-verifying script pattern D-04 mirrors (registry wiring self-check precedent)
- `scripts/cluster-teardown.sh` — double-safe teardown precedent for observability-down.sh
- `infra/kind/kind-config.yaml` — the cluster the stack lands on (node topology for the preflight check)
- `Makefile` — compositional target conventions Phase 14 will wrap the scripts with (do not add targets in this phase)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/cluster-setup.sh` / `scripts/cluster-teardown.sh`: shell idioms, idempotency guards, and self-verification style to mirror in observability-up.sh / observability-down.sh
- `infra/observability/`: empty reserved seam (created in v1.0 exactly for this) — all new manifests/values live here
- Existing `make smoke` / `smoke-launchpad`: the v1.1 health checks the install/teardown scripts re-use for app-survival verification (invoke, don't reimplement)

### Established Patterns
- Self-verifying scripts (cluster-setup.sh verifies registry push/pull at cluster-up) — both new scripts verify their own outcome
- Accepted-risk documentation in docs/known-limitations.md (committed local-dev credentials precedent)
- POSIX/Git-Bash-safe scripting: LF endings via .gitattributes, MSYS path-mangling awareness, no Windows paths
- Many small lowercase conventional commits

### Integration Points
- New namespace `observability` alongside the existing app namespace(s) — label-selector + HTTP only coupling, zero chart edits
- Phase 12 will apply ServiceMonitor CRs against the CRDs this phase installs (why D-01 keeps CRDs)
- Phase 14 wraps this phase's scripts in `make observability-up`/`observability-down`/`port-forward-grafana`

</code_context>

<specifics>
## Specific Ideas

- Preflight failure message should be actionable for a Windows/Docker Desktop operator: name the setting to change ("raise Docker Desktop memory to X GB"), not just "insufficient resources".
- The Grafana anonymous-viewer decision exists specifically to keep the Phase 15/17 flagship demo walkthrough frictionless — don't trade it away for production-realism in this phase.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. (Pre-existing deferrals — Loki, Alertmanager, SLO panels — remain tracked in REQUIREMENTS.md Future Requirements.)

</deferred>

---

*Phase: 11-Observability Stack Install*
*Context gathered: 2026-07-16*
