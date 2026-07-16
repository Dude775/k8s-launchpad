---
phase: 11-observability-stack-install
plan: 04
subsystem: infra
tags: [helm, kube-prometheus-stack, kube-state-metrics, resource-limits, kind]

# Dependency graph
requires:
  - phase: 11-observability-stack-install (plan 03)
    provides: Certified torn-down end state of the trimmed kube-prometheus-stack install, plus the D-09 verification gap (kube-state-metrics BestEffort) this plan closes
provides:
  - Corrected infra/observability/values-trimmed.yaml with kube-state-metrics resources under the chart-consumed top-level `kube-state-metrics:` subchart key
  - Live-confirmed proof that the kube-state-metrics pod carries a 32Mi/10m request with Burstable QoS
  - Restored certified torn-down end state (observability namespace absent, 10 monitoring.coreos.com CRDs retained, v1.1 apps healthy)
  - Corrected docs/known-limitations.md "Measured observability headroom" note (~516 MiB total, no component described as BestEffort)
affects: [12-servicemonitors-scrape-wiring, 13-grafana-dashboards, phase-11-milestone-verification]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Helm subchart values placement: camelCase condition-flag keys (e.g. kubeStateMetrics.enabled) are separate from the hyphenated top-level subchart dependency values key (e.g. kube-state-metrics:) that the bundled subchart actually consumes — resources/config must go under the hyphenated key, not the camelCase one."

key-files:
  created: []
  modified:
    - infra/observability/values-trimmed.yaml
    - docs/known-limitations.md

key-decisions:
  - "Kept kubeStateMetrics.enabled: true as the pure condition flag; added a new top-level kube-state-metrics: key (with dashes) carrying the resources block — matches the chart's actual dependency-values consumption model (11-REVIEW.md WR-01)."
  - "Did not attempt to bound Grafana's two bundled sidecar containers in this gap-closure plan — explicitly out of scope (D-09 gap was kube-state-metrics only); documented as the sole remaining unset-resources component."

patterns-established: []

requirements-completed: [OBS-01]

# Metrics
duration: 15min
completed: 2026-07-16
---

# Phase 11 Plan 04: kube-state-metrics resource bound gap closure Summary

**Moved kube-state-metrics resource requests/limits to the chart-consumed top-level `kube-state-metrics:` subchart values key, live-verified the pod now carries 32Mi/10m (Burstable QoS, not BestEffort), and restored the certified torn-down Phase 11 end state.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-07-16T18:52:00Z (approx)
- **Completed:** 2026-07-16T19:12:15Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Fixed the D-09 verification gap: kube-state-metrics resource bounds now actually reach the pod spec (previously silently ignored under the wrong `kubeStateMetrics.resources` key)
- Live-verified via `kubectl` jsonpath that the pod carries `resources.requests.memory=32Mi`, `resources.requests.cpu=10m`, and `status.qosClass=Burstable`
- Full install→teardown lifecycle re-run: `observability-up.sh` exit 0 (Step 4 `make smoke` + `make smoke-launchpad` both PASSED), `observability-down.sh` exit 0 (post-teardown smoke tests both PASSED again)
- Restored the certified Phase 11 end state: observability namespace NotFound, all 10 `monitoring.coreos.com` CRDs retained, both v1.1 apps healthy with zero restarts throughout
- Corrected `docs/known-limitations.md` headroom note: 484 MiB → ~516 MiB total, removed the inaccurate "kube-state-metrics ... BestEffort" claim, scoped the remaining-unbounded caveat to only Grafana's two sidecar containers

## Task Commits

Each task was committed atomically:

1. **Task 1: Move kube-state-metrics resources to the correct subchart values key** - `59044ce` (fix)
2. **Task 2: Live-verify the applied bound, restore torn-down end state, update docs** - `c8e2f17` (docs)

**Plan metadata:** (this commit, following SUMMARY.md creation)

## Files Created/Modified
- `infra/observability/values-trimmed.yaml` - Removed the nested `resources:` block from the camelCase `kubeStateMetrics:` condition-flag key; added it under a new top-level hyphenated `kube-state-metrics:` subchart values key (same 10m/32Mi request, 50m/64Mi limit); updated header comment to accurately describe the two-key mechanism
- `docs/known-limitations.md` - Updated the "Measured observability headroom" note: 484 MiB → ~516 MiB total (now includes kube-state-metrics' 32Mi), corrected the BestEffort claim to note only Grafana's sidecars remain on chart-default resources

## Live Verification Evidence (proof artifact for closed D-09 gap)

Captured during the live install re-run (`bash scripts/observability-up.sh`, chart 87.16.1):

```
kubectl --context=kind-kind get pod -n observability -l app.kubernetes.io/name=kube-state-metrics \
  -o jsonpath='{.items[0].spec.containers[0].resources.requests.memory}'
=> 32Mi

kubectl --context=kind-kind get pod -n observability -l app.kubernetes.io/name=kube-state-metrics \
  -o jsonpath='{.items[0].spec.containers[0].resources.requests.cpu}'
=> 10m

kubectl --context=kind-kind get pod -n observability -l app.kubernetes.io/name=kube-state-metrics \
  -o jsonpath='{.items[0].status.qosClass}'
=> Burstable
```

Post-teardown confirmation:
- `kubectl --context=kind-kind get ns observability` → `Error from server (NotFound)`
- `kubectl --context=kind-kind get crd | grep -c monitoring.coreos.com` → `10`
- `make smoke` and `make smoke-launchpad` both PASSED (0 restarts on both v1.1 apps throughout the full lifecycle)

## Decisions Made
- Kept the camelCase `kubeStateMetrics:` key as pure condition flag (`enabled: true` only) and introduced the hyphenated `kube-state-metrics:` top-level key for the actual subchart values — this matches how kube-prometheus-stack's Chart.yaml declares the bundled dependency, per 11-REVIEW.md WR-01's root-cause analysis.
- Left Grafana's bundled sidecar containers unbounded (chart default) — explicitly out of scope per the plan; documented as the sole remaining unset-resources item in known-limitations.md.

## Deviations from Plan

None - plan executed exactly as written. Both tasks' verification commands and acceptance criteria passed on the first attempt with no auto-fixes required.

## Issues Encountered

None. The cluster and both v1.1 apps were already up and healthy at the start of this plan (age ~5.5h from a prior session), so no `make cluster-up` / `make up-all` precondition step was needed before running `observability-up.sh`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- D-09 must-have truth #4 (Phase 11 verification gap) now passes: every kept-enabled observability component carries explicit resource requests/limits that the chart actually applies.
- OBS-01's "conservative resource limits / nothing unbounded" clause is delivered as written for kube-state-metrics.
- The certified Phase 11 end state (torn down, CRDs retained, v1.1 apps healthy) is restored and ready for Phase 12 (ServiceMonitors) to build on.
- No blockers. Phase 11 verification should now re-check must-have truth #4 against this fix.

## Self-Check: PASSED

- FOUND: infra/observability/values-trimmed.yaml (top-level `kube-state-metrics:` key present)
- FOUND: docs/known-limitations.md (contains "kube-state-metrics", "516", no longer contains "i.e. BestEffort")
- FOUND commit 59044ce in `git log --oneline --all`
- FOUND commit c8e2f17 in `git log --oneline --all`

---
*Phase: 11-observability-stack-install*
*Completed: 2026-07-16*
