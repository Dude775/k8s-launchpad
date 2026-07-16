---
phase: 11-observability-stack-install
plan: 03
subsystem: infra
tags: [kind, kubectl, helm, kube-prometheus-stack, prometheus, grafana, verification]

# Dependency graph
requires:
  - phase: 11-01
    provides: scripts/observability-up.sh, infra/observability/values-trimmed.yaml (trimmed kube-prometheus-stack install)
  - phase: 11-02
    provides: scripts/observability-down.sh (idempotent teardown, CRD-retention policy)
provides:
  - Live proof (on a real kind cluster) that OBS-01/OBS-02 success criteria hold end to end
  - First live-measured resource-headroom figure for the trimmed stack, recorded in docs/known-limitations.md
  - Human-confirmed Prometheus/Grafana UI reachability and D-07/D-08 access behavior
affects: [12-servicemonitors-metrics-wiring, 14-makefile-targets]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Live lifecycle verification: install -> assert -> record -> teardown -> assert, all in one automated gate, mirroring cluster-setup.sh's self-verifying style"

key-files:
  created: []
  modified:
    - docs/known-limitations.md (Measured observability headroom entry; Task 1)
    - scripts/observability-up.sh (fixed during Task 1's live run)
    - scripts/observability-down.sh (fixed during Task 1's live run)

key-decisions:
  - "Final environment state left as torn down (namespace deleted, CRDs retained, v1.1 apps healthy) after Task 2's human verification completed, matching the state Task 1's automated gate already certified"
  - "Two kubectl port-forward processes left running by the prior session (Prometheus 9090, Grafana 3000) were killed as part of Task 2 cleanup"

patterns-established:
  - "Live verification plans that both install AND teardown in the same automated gate, with a human-verify checkpoint sandwiched in between for UI-only checks"

requirements-completed: [OBS-01, OBS-02]

# Metrics
duration: ~55min (spans a continuation resume)
completed: 2026-07-16
---

# Phase 11 Plan 03: Live Observability Stack Verification Summary

**Live-verified the trimmed kube-prometheus-stack installs cleanly, leaves v1.1 apps untouched, and tears down without deleting CRDs — with human-confirmed Prometheus/Grafana UI access completing the OBS-01/OBS-02 proof.**

## Performance

- **Duration:** ~55 min (Task 1 executed by a prior agent; this continuation completed Task 2 and closeout)
- **Completed:** 2026-07-16T12:01:17Z
- **Tasks:** 2/2 completed
- **Files modified:** 3 (docs/known-limitations.md, scripts/observability-up.sh, scripts/observability-down.sh — all committed under Task 1)

## Accomplishments

- Proved the full install -> verify -> teardown lifecycle on a live kind cluster in one automated gate: 4 observability pods reached Running/Ready, no alertmanager pod or node-exporter DaemonSet exist, all 10 `monitoring.coreos.com` CRDs present, `make smoke` + `make smoke-launchpad` PASS both before and after install, teardown leaves the `observability` namespace NotFound while CRDs remain, and the v1.1 apps had 0 restarts throughout.
- Recorded the first live-measured resource-headroom figure in `docs/known-limitations.md`: ~9.71 GiB node-allocatable, ~546 MiB already requested by v1.1 apps, ~9.18 GiB headroom before install; the trimmed stack's actual scheduled requests came to 484 MiB — closely matching the ~516 MiB preflight estimate.
- Human-verified (approved) that both Prometheus (localhost:9090) and Grafana (localhost:3000) load via port-forward, `/targets` shows no disabled scrape jobs (kube-etcd, kube-scheduler, kube-controller-manager, kube-proxy, alertmanager, node-exporter all absent rather than red), admin login with the D-07 password succeeds, and anonymous Viewer read-only access works per D-08.
- Returned the cluster to the same clean, fully-verified end state Task 1's gate certified: observability namespace deleted, CRDs retained, no stray port-forward processes, both v1.1 apps healthy.

## Task Commits

Each task was committed atomically:

1. **Task 1: Run the full install -> verify -> teardown lifecycle and assert every automatable criterion** - `48b06db` (fix)
2. **Task 2: Human verification -- Prometheus + Grafana UIs reachable via port-forward** - no code commit (pure verification checkpoint; user approved, no files changed)

**Plan metadata:** committed alongside this SUMMARY (see final commit)

## Files Created/Modified

- `docs/known-limitations.md` - Measured observability headroom entry appended (Task 1)
- `scripts/observability-up.sh` - fixed during Task 1's live dry-run (see Task 1 commit diff)
- `scripts/observability-down.sh` - fixed during Task 1's live dry-run (see Task 1 commit diff)

## Decisions Made

- **Final cluster state after Task 2:** re-tore-down the observability stack (`bash scripts/observability-down.sh`) after the human-verify checkpoint was approved, restoring the environment to the exact state Task 1's automated gate already certified (namespace NotFound, CRDs retained, v1.1 apps healthy). The plan did not explicitly mandate a post-checkpoint end state, but Task 1's gate is the sole proof artifact for OBS-02 teardown behavior, so leaving the stack installed after a human-only UI check would leave the repo in an unverified, uncertified state. Later phases (12+) will explicitly bring the stack back up via `scripts/observability-up.sh` (Phase 14 will wrap this in a `make` target) when they need it running.
- **Stray process cleanup:** killed two `kubectl port-forward` processes (PIDs 35332, 32916 — Prometheus 9090, Grafana 3000) left running by the prior session's browser verification, per the resume instructions.

## Deviations from Plan

None - Task 1's deviations (script fixes) were already documented and committed by the prior agent under commit `48b06db`. This continuation only completed Task 2 (human-verify checkpoint, approved) and closeout housekeeping (killing stray port-forwards, re-running teardown to restore the certified end state) — no new deviations.

## Known Stubs

None.

## Self-Check: PASSED

- FOUND: docs/known-limitations.md contains `Measured observability headroom: live Phase 11 install (2026-07-16)` (verified via grep)
- FOUND: commit `48b06db` exists in git log (`git log --oneline --grep="11-03"`)
- FOUND: `kubectl get ns observability` returns NotFound after final teardown
- FOUND: `kubectl get crd | grep monitoring.coreos.com` returns 10 CRDs after final teardown
- FOUND: `make smoke` and `make smoke-launchpad` PASS after final teardown
- FOUND: no stray kubectl processes remain (`tasklist | grep kubectl` empty)
