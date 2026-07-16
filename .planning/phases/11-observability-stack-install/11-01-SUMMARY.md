---
phase: 11-observability-stack-install
plan: 01
subsystem: infra
tags: [helm, kube-prometheus-stack, prometheus, grafana, kind, observability]

# Dependency graph
requires:
  - phase: 10-launchpad-hardening-and-multi-app-polish (v1.1)
    provides: make smoke / make smoke-launchpad targets and stable field-guide-api + launchpad deployments this plan's install/verify steps depend on
provides:
  - "infra/observability/values-trimmed.yaml — trimmed kube-prometheus-stack Helm values (87.16.1 pinned)"
  - "scripts/observability-up.sh — idempotent, self-verifying install wrapper"
affects: [11-02-observability-teardown-and-docs, 12-servicemonitors-and-scrape-config, 13-grafana-dashboards, 14-makefile-targets]

# Tech tracking
tech-stack:
  added: [kube-prometheus-stack@87.16.1 (Helm chart, prometheus-community repo)]
  patterns:
    - "Idempotent self-verifying wrapper script (mirrors scripts/cluster-setup.sh): prereq gate -> preflight -> mutate -> self-verify -> app-survival re-check"
    - "Live kubectl-jsonpath resource-capacity preflight check (no jq dependency), same convention as cluster-setup.sh's registry verification"

key-files:
  created: [infra/observability/values-trimmed.yaml, scripts/observability-up.sh]
  modified: []

key-decisions:
  - "All seven disable flags (alertmanager, nodeExporter, kubeEtcd, kubeControllerManager, kubeScheduler, kubeProxy, defaultRules) set per locked D-04/D-05 decisions from 11-CONTEXT.md; not re-litigated"
  - "Preflight capacity check computed live via kubectl jsonpath at script runtime (D-10) rather than a hardcoded machine-specific number, per RESEARCH.md Open Question 2 resolution"
  - "Trimmed stack's known total memory requests (516Mi = 100+256+128+32) hardcoded as a comparison constant since it's derived directly from the committed values file, not runtime-discoverable without re-parsing YAML in bash"
  - "Removed infra/observability/.gitkeep now that values-trimmed.yaml occupies the directory (per RESEARCH.md Recommended Project Structure note)"

patterns-established:
  - "Second wrapper script (after cluster-setup.sh/cluster-teardown.sh) following the same errexit/no-pipefail/MSYS_NO_PATHCONV/prereq-gate/step-echo/self-verify house style"

requirements-completed: [OBS-01]

# Metrics
duration: 15min
completed: 2026-07-16
---

# Phase 11 Plan 01: Observability Stack Install Artifacts Summary

**Trimmed kube-prometheus-stack (87.16.1) Helm values plus an idempotent, preflight-guarded `observability-up.sh` install script that self-verifies pod readiness and re-runs `make smoke`/`make smoke-launchpad` to prove the v1.1 apps are undisturbed.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-07-16T13:25:00Z (approx, worktree checkout)
- **Completed:** 2026-07-16T10:28:44Z (UTC)
- **Tasks:** 2/2 completed
- **Files modified:** 2 created, 1 removed (.gitkeep)

## Accomplishments
- `infra/observability/values-trimmed.yaml`: disables Alertmanager, node-exporter, and all four kubeadm-only scrape jobs (kubeEtcd/kubeControllerManager/kubeScheduler/kubeProxy), disables defaultRules, and sets explicit bounded `resources.requests/limits` on every kept-enabled component (prometheusOperator, prometheus, grafana, kubeStateMetrics) — no unbounded component ships.
- Grafana configured with committed local-dev admin password (`grafana-dev-password`) and anonymous Viewer-role access via `grafana.ini` (D-07/D-08), plus explicit sidecar dashboard discovery config for Phase 13.
- Prometheus configured for 24h retention with emptyDir storage (no PVC, no `storageSpec:` key present) and both `serviceMonitorSelectorNilUsesHelmValues`/`podMonitorSelectorNilUsesHelmValues` set to `false` so Phase 12's standalone ServiceMonitors are discoverable without extra labels.
- `scripts/observability-up.sh`: mirrors `scripts/cluster-setup.sh`'s house style exactly — prereq gate (docker/kubectl/helm + daemon check), a live jsonpath-based preflight memory-capacity check (D-10) that aborts with an actionable Docker Desktop message if headroom is insufficient, idempotent `helm repo add`/`update`, `helm upgrade --install --version 87.16.1 --wait --timeout 300s` (no `--atomic`), a readiness wait scoped to exclude the short-lived Succeeded admission-webhook Job pod, and a final `make smoke && make smoke-launchpad` re-check (D-06) that halts the script (errexit) if either app was disturbed.

## Task Commits

Each task was committed atomically:

1. **Task 1: Write infra/observability/values-trimmed.yaml (trimmed chart values)** - `d05946b` (feat)
2. **Task 2: Write scripts/observability-up.sh (idempotent self-verifying install)** - `5287fd1` (feat)

**Plan metadata:** (this commit, pending)

## Files Created/Modified
- `infra/observability/values-trimmed.yaml` - Trimmed kube-prometheus-stack Helm values: 7 disable flags, 4 bounded resource blocks, Grafana admin/anonymous-viewer config, Prometheus 24h/emptyDir retention config
- `scripts/observability-up.sh` - Idempotent install wrapper: preflight capacity check, helm upgrade --install, readiness wait, app-survival re-check
- `infra/observability/.gitkeep` - removed (superseded by values-trimmed.yaml landing in the directory)

## Decisions Made
All implementation decisions (D-04 through D-11) were already locked during `/gsd:discuss-phase` and confirmed against live chart defaults during `/gsd:research-phase` — this plan implemented them exactly, no new decisions were made. The only Claude's-Discretion items exercised were: exact resource numbers (carried over verbatim from RESEARCH.md Pattern 2, already resolved in Open Question 1), and the preflight comparison constant (hardcoded 516Mi sum, matching the committed values file) rather than parsing YAML at runtime in bash.

## Deviations from Plan

None - plan executed exactly as written, with one syntax-conformance fix applied during self-verification:

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Hardcoded `--version 87.16.1` and `-f infra/observability/values-trimmed.yaml` as literal strings instead of shell variables**
- **Found during:** Task 2 self-verification (running the plan's own automated verify grep commands)
- **Issue:** Initial draft used `CHART_VERSION`/`VALUES_FILE` shell variables in the `helm upgrade --install` invocation for readability; this broke the plan's literal-string verification gate (`grep -q -- "--version 87.16.1"` and `grep -q -- "-f infra/observability/values-trimmed.yaml"`) since the variables aren't expanded by grep.
- **Fix:** Replaced both variables with the literal strings directly in the helm command (matching the exact form shown in RESEARCH.md Pattern 1 and this plan's own acceptance criteria).
- **Files modified:** scripts/observability-up.sh
- **Verification:** Re-ran the plan's full automated verify block — all checks (`bash -n`, MSYS, tool gate, version, values-flag, smoke, smoke-launchpad) now pass.
- **Committed in:** 5287fd1 (Task 2 commit — fixed before first commit of this file, not a separate follow-up commit)

---

**Total deviations:** 1 auto-fixed (1 blocking/verification-conformance)
**Impact on plan:** No scope creep — purely a literal-vs-variable string match fix required by the plan's own automated verification gate.

## Issues Encountered
None beyond the deviation above.

## User Setup Required
None - no external service configuration required. Live end-to-end install verification (running the script against an actual cluster) is explicitly deferred to Plan 03 per this plan's `<verification>` section.

## Next Phase Readiness
- `infra/observability/values-trimmed.yaml` and `scripts/observability-up.sh` are statically valid and ready for live verification in Plan 03 (requires a running kind cluster).
- Plan 02 (observability-down / docs) can now reference this plan's file paths and conventions.
- No blockers identified. Note: this plan's success criteria explicitly exclude live cluster verification (deferred to Plan 03) — the preflight capacity math, helm install flow, and readiness-wait logic have not yet been exercised against a real cluster.

---
*Phase: 11-observability-stack-install*
*Completed: 2026-07-16*

## Self-Check: PASSED

- FOUND: infra/observability/values-trimmed.yaml
- FOUND: scripts/observability-up.sh
- FOUND: d05946b (git log)
- FOUND: 5287fd1 (git log)
