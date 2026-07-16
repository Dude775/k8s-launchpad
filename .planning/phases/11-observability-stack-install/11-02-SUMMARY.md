---
phase: 11-observability-stack-install
plan: 02
subsystem: infra
tags: [helm, kubernetes, kind, teardown, observability, kube-prometheus-stack, docs]

# Dependency graph
requires:
  - phase: 11-observability-stack-install (plan 01, if applicable)
    provides: infra/observability/ install path this teardown script mirrors
provides:
  - "scripts/observability-down.sh: idempotent, self-verifying teardown of the kube-prometheus-stack release"
  - "docs/known-limitations.md: accepted-risk documentation for D-01 (CRD retention), D-07 (Grafana password), D-08 (anonymous viewer)"
affects: [14-makefile-targets, 12-servicemonitors]

# Tech tracking
tech-stack:
  added: []
  patterns: ["idempotent guarded helm uninstall (helm status check before uninstall)", "teardown re-verification via existing make smoke targets rather than reimplementing health checks"]

key-files:
  created: [scripts/observability-down.sh]
  modified: [docs/known-limitations.md]

key-decisions:
  - "D-01: teardown runs helm uninstall only, deliberately leaving monitoring.coreos.com CRDs installed (documented as accepted risk with manual removal command)"
  - "D-02: teardown deletes the observability namespace to sweep leftover secrets/configmaps; CRDs survive because they are cluster-scoped"
  - "D-03: teardown re-runs make smoke and make smoke-launchpad as a built-in app-survival check, mirroring cluster-teardown.sh's idempotent guard style"

patterns-established:
  - "Teardown scripts invoke existing make smoke/smoke-launchpad targets for app-survival verification rather than reimplementing health checks"

requirements-completed: [OBS-02]

# Metrics
duration: ~10min
completed: 2026-07-16
---

# Phase 11 Plan 02: Observability Teardown + Accepted-Risk Docs Summary

**Idempotent `scripts/observability-down.sh` (helm uninstall -> namespace delete -> app-survival re-check) plus three new accepted-risk sections in `docs/known-limitations.md` covering CRD retention, the committed Grafana password, and anonymous viewer access.**

## Performance

- **Duration:** ~10 min
- **Completed:** 2026-07-16T10:28:17Z
- **Tasks:** 2
- **Files modified:** 2 (1 created, 1 modified)

## Accomplishments
- `scripts/observability-down.sh` mirrors `scripts/cluster-teardown.sh`'s house style: guarded idempotent `helm uninstall kube-prometheus-stack -n observability` (skips cleanly if already gone), `kubectl delete namespace observability --ignore-not-found`, then `make smoke` + `make smoke-launchpad` to prove the v1.1 apps are untouched.
- Script deliberately contains zero CRD-deletion logic, honoring D-01 (Phase 12's ServiceMonitors depend on `monitoring.coreos.com` CRDs surviving teardown).
- `docs/known-limitations.md` stale "No Prometheus / Grafana / Loki / Trivy (PRD-4)" section corrected to reflect that Prometheus/Grafana/kube-state-metrics now exist via `infra/observability/`, with Loki/Trivy/Alertmanager still deferred.
- Three new accepted-risk sections added in the existing doc voice: committed Grafana admin password (`grafana-dev-password`, D-07), CRD-teardown retention rationale (D-01), and anonymous Grafana Viewer access (D-08, cross-referencing the existing port-forward-only section).

## Task Commits

Each task was committed atomically:

1. **Task 1: Write scripts/observability-down.sh** - `f8951c3` (feat)
2. **Task 2: Append accepted-risk sections to docs/known-limitations.md** - `8c930a8` (docs)

_Note: this is a worktree-isolated execution; STATE.md/ROADMAP.md are updated centrally by the orchestrator after merge, not per-plan._

## Files Created/Modified
- `scripts/observability-down.sh` - Idempotent teardown wrapper: guarded helm uninstall, namespace delete, app-survival re-check; keeps CRDs by design
- `docs/known-limitations.md` - Amended stale PRD-4 section; added Grafana password, CRD-retention, and anonymous-viewer accepted-risk sections

## Decisions Made
No new decisions beyond what was already locked in `11-CONTEXT.md` (D-01, D-02, D-03, D-07, D-08). This plan implements those decisions in code and docs.

## Deviations from Plan

None - plan executed exactly as written. One implementation adjustment within Task 1's own scope: the plan's verify step greps for literal strings (`helm uninstall kube-prometheus-stack`, `delete namespace observability`), so the script uses the literal release/namespace names directly in the `helm`/`kubectl` invocations rather than indirecting through shell variables — this is a stylistic choice consistent with the plan's explicit verification command, not a deviation from plan intent.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required. Live teardown verification (actually running the script against a cluster) is exercised in Plan 03 per this plan's `<verification>` section.

## Next Phase Readiness
- OBS-02 teardown path is code-complete and passes all static verification (`bash -n`, guarded helm uninstall, namespace delete with `--ignore-not-found`, no CRD-deletion command, invokes `make smoke`/`make smoke-launchpad`).
- Accepted-risk documentation for D-01/D-07/D-08 is in place ahead of Phase 12 (ServiceMonitors depend on retained CRDs) and Phase 14 (Makefile wraps this script as `make observability-down`).
- Live execution against a running cluster (helm uninstall actually succeeding, namespace actually gone, CRDs actually remaining, both apps actually healthy) is deferred to Plan 03 per this plan's own verification section — no blocker, by design.

---
*Phase: 11-observability-stack-install*
*Completed: 2026-07-16*

## Self-Check: PASSED

- FOUND: scripts/observability-down.sh
- FOUND: docs/known-limitations.md
- FOUND: .planning/phases/11-observability-stack-install/11-02-SUMMARY.md
- FOUND commit: f8951c3
- FOUND commit: 8c930a8
