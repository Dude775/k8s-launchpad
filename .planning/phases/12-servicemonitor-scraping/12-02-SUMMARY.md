---
phase: 12-servicemonitor-scraping
plan: 02
subsystem: infra
tags: [kubernetes, prometheus, servicemonitor, live-verification, lifecycle]

# Dependency graph
requires:
  - phase: 12-servicemonitor-scraping
    provides: "Plan 12-01: two standalone ServiceMonitor manifests + observability-up.sh Steps 4-7 (CRD guard, apply, presence check, up==1 self-verify)"
  - phase: 11-observability-stack
    provides: "observability-up.sh Steps 0-3 install flow, observability-down.sh teardown, values-trimmed.yaml, CRD retention policy (11/D-01)"
provides:
  - "OBS-03 proven live: up{job=\"field-guide-api\"} == 1 and up{job=\"launchpad\"} == 1 on a real kind cluster (D-10)"
  - "Operator-approved D-11 checkpoint: both scrape jobs State = UP on the Prometheus Targets page, recent scrapes, zero errors"
  - "Full up -> verify -> checkpoint -> down lifecycle proven, including ServiceMonitor re-apply on reinstall (D-12)"
  - "Certified phase end state: torn down (observability namespace deleted, monitoring CRDs retained)"
affects: [13-dashboards]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Live-lifecycle certification: object creation is never proof — a live up==1 query plus independent human Targets-page confirmation certifies scraping"
    - "Certified torn-down end state between phases: namespace-sweep teardown with cluster-scoped CRD retention lets the next phase start clean with one observability-up"

key-files:
  created: []
  modified: []

key-decisions:
  - "Happy path held: Step 7 self-verify passed on first run with no timeout, so the conditional timeout-triage edit to observability-up.sh (deadline bump) was never needed — zero repo files modified by this plan"
  - "Pre-existing observability namespace (leftover from a prior session) was upgraded in place by helm upgrade --install (REVISION 2) rather than torn down first — idempotency worked as designed and the final teardown restored the certified end state regardless"

patterns-established: []

requirements-completed: [OBS-03]

# Metrics
duration: ~20min (including operator checkpoint wait)
completed: 2026-07-18
---

# Phase 12 Plan 02: Live ServiceMonitor Scraping Lifecycle Summary

**OBS-03 proven live on the real kind cluster: automated up==1 self-verify PASS for both apps, operator-approved Targets-page confirmation (D-11), and full teardown to the certified torn-down end state (D-12) — with zero repo file changes.**

## Performance

- **Duration:** ~20 min (including operator checkpoint wait)
- **Started:** 2026-07-18T00:43:00+03:00
- **Completed:** 2026-07-18T01:03:00+03:00
- **Tasks:** 3 completed (2 auto + 1 human-verify checkpoint)
- **Files modified:** 0 (happy path — conditional timeout-triage branch never triggered)

## Accomplishments

- **Task 1 (up + self-verify):** `bash scripts/observability-up.sh` ran Steps 0-8 against the live kind cluster and exited 0. Step 7 reported `PASS up{job="field-guide-api"} == 1` and `PASS up{job="launchpad"} == 1` with no timeout. Both ServiceMonitor objects confirmed present via `kubectl -n observability get servicemonitor field-guide-api launchpad`. An independent curl check (separate port-forward on 9091, outside the script) confirmed both queries return `"value":[...,"1"]` with the expected default job labels (D-05/A1 assumption held — no jobLabel correction needed). Step 8 smoke checks passed for both v1.1 apps.
- **Task 2 (D-11 operator checkpoint):** Operator ran the Prometheus port-forward, opened http://localhost:9090/targets, and approved: both `field-guide-api` and `launchpad` scrape jobs showed State = UP with recent Last Scrape and no errors.
- **Task 3 (teardown to certified end state):** `bash scripts/observability-down.sh` exited 0 — helm release uninstalled, `observability` namespace deleted (sweeping both ServiceMonitors as a side effect, D-04 — no explicit ServiceMonitor delete step exists). Verified: namespace NotFound, `servicemonitors.monitoring.coreos.com` CRD still present (retained per 11/D-01), `kubectl get servicemonitor -A` returns no resources, `helm list -n observability` empty, all 4 v1.1 app pods Running with 0 restarts, and the down script's trailing `make smoke` / `make smoke-launchpad` passed.

## D-12 Lifecycle Proof

The full **up -> verify -> checkpoint -> down** lifecycle completed on a live cluster. Notably, the observability namespace pre-existed from a prior session when Task 1 ran: `helm upgrade --install` upgraded the release in place (REVISION 2) and `kubectl apply` created the ServiceMonitors fresh — proving the ServiceMonitors re-apply cleanly on reinstall. **The certified end state of Phase 12 is torn down**: Phase 13 starts from a clean slate and one `observability-up` run restores the entire stack including both ServiceMonitors.

## Task Commits

No task commits — the happy path modified zero repository files:

1. **Task 1: Run observability-up and confirm up==1 self-verify** — no commit (live-cluster work only; the conditional `scripts/observability-up.sh` deadline edit was never triggered)
2. **Task 2: Operator confirms both jobs UP on Targets page (D-11)** — human-verify checkpoint, approved by operator ("approved")
3. **Task 3: Tear down to certified end state (D-12)** — no commit (live-cluster work only; `observability-down.sh` byte-for-byte unmodified per D-04)

## Files Created/Modified

None. `git diff --quiet scripts/observability-up.sh` and `git diff --quiet scripts/observability-down.sh` both pass — this plan's success criterion of "no repo files modified on the happy path" held.

## Decisions Made

- Treated the pre-existing observability namespace (leftover from an earlier session) as a valid Task 1 starting point rather than tearing down first — the scripts are explicitly idempotent, `helm upgrade --install` handled it correctly, and the plan's D-12 requirement (torn-down end state) is about the *end* state, which Task 3 delivered.
- Did not apply the RESEARCH Open Question 1 deadline bump — Step 7 passed well within the 150s window, so the conditional edit branch was never entered.

## Deviations from Plan

None - plan executed exactly as written. The timeout-triage branch (A1 spot-check, deadline raise) and the D-05/A1 jobLabel-correction contingency were both prepared for but never needed.

## Issues Encountered

- The executor session was interrupted by an API error between the Task 3 teardown and SUMMARY authoring. On resume, the certified end state was independently re-verified from scratch (namespace NotFound, CRD retained, helm list empty, ServiceMonitors gone, app pods healthy) before writing this summary — no re-execution of teardown was needed.

## User Setup Required

None. The stack is torn down; to bring it back for Phase 13, run `bash scripts/observability-up.sh` (requires the kind cluster + v1.1 apps, i.e. `make up-all` first).

## Next Phase Readiness

- Phase 12 is complete: OBS-03 proven live (automated + human-verified), lifecycle self-healing proven, end state certified torn down.
- Phase 13 (dashboards) can start clean: one `observability-up` restores Prometheus + Grafana + both ServiceMonitors with scraping verified automatically by Step 7.
- Outstanding research flag for Phase 13 (from STATE.md) still applies: capture a live `/metrics` dump from both apps before authoring PromQL.

---
*Phase: 12-servicemonitor-scraping*
*Completed: 2026-07-18*

## Self-Check: PASSED

SUMMARY.md present on disk; summary commit db36252 confirmed in git log. No task commits expected (zero repo files modified on the happy path); live-cluster end state independently re-verified (namespace NotFound, CRD retained, helm list empty, v1.1 app pods healthy).
