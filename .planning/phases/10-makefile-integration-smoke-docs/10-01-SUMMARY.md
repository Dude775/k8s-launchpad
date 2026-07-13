---
phase: 10-makefile-integration-smoke-docs
plan: 01
subsystem: infra
tags: [makefile, helm, kubectl, mongosh, kind, bash]

# Dependency graph
requires:
  - phase: 08-helm-chart-k8s-diagnostics
    provides: charts/launchpad Helm chart, LP_* Makefile variable seam, manual deploy loop live-verified
  - phase: 09-service-catalog-events-mongodb-crud
    provides: in-chart launchpad MongoDB (readinessProbe passes), events TTL index seam (EVENTS_TTL_SECONDS), FEED-03 "verify live via smoke" flag
provides:
  - "up-all: one-command cluster + both-apps bring-up (up + build-launchpad + load-launchpad + deploy-launchpad) with D-09 epilogue"
  - "smoke-launchpad: PASS/FAIL HTTP smoke on /, /health, /api/status via localhost:8081"
  - "smoke-all: aggregate of smoke (field-guide-api) + smoke-launchpad"
  - "verify-ttl: tiered TTL verification (default index-existence check; TTL_DEEP=1 live expiry round-trip)"
  - "grouped ##@-section make help (Cluster / field-guide-api / launchpad / Housekeeping)"
  - "undeploy-launchpad, launchpad-aware clean-venv and reset-local"
affects: [10-02, README, docs/troubleshooting.md, docs/known-limitations.md]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "##@ Section awk-based grouped make help (community Carvel/Kubebuilder convention)"
    - "kubectl exec + mongosh --eval PASS/FAIL verification target (verify-ttl) composed from check-tools loop shape + smoke trap/cleanup shape"
    - "TTL_DEEP=1 opt-in slow-path gate keeps live-expiry round-trip out of the default fast smoke path"

key-files:
  created: []
  modified:
    - Makefile

key-decisions:
  - "up-all reuses the untouched v1.0 up aggregate then chains the launchpad trio (D-01) — up itself stays field-guide-only"
  - "deploy-launchpad mirrors deploy exactly with --wait --timeout 180s, no --atomic (Helm 4 deprecation avoided per CLAUDE.md)"
  - "smoke-launchpad endpoint loop uses an empty-string first element (\"\" health api/status) to cover the / root path in the single-segment curl loop"
  - "verify-ttl pod selector app.kubernetes.io/name=launchpad-mongodb confirmed directly against charts/launchpad/templates/_helpers.tpl launchpad.mongodb.selectorLabels before finalizing"
  - "TTL_DEEP=1 deep mode inserts a probe doc and polls up to 18x5s=90s for MongoDB's TTL monitor to remove it, bounded so it never hangs indefinitely"
  - "Repeated ##@ field-guide-api marker used twice (test target, then build/load/deploy/undeploy/up group) rather than reordering targets — avoids touching working target bodies purely for cosmetic grouping"

patterns-established:
  - "Grouped make help via ##@ Section markers + awk substr($0,5) rule — reusable for any future target group"

requirements-completed: [DEP-04, DEP-05]

# Metrics
duration: 12min
completed: 2026-07-13
---

# Phase 10 Plan 1: Makefile Integration Summary

**Filled all six launchpad Makefile stubs with real docker/helm/kubectl recipes and added up-all/smoke-all/undeploy-launchpad/verify-ttl so `make up-all` brings up both apps and `make smoke-all` proves both reachable with one command.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-13T20:56:00Z
- **Completed:** 2026-07-13T21:08:00Z
- **Tasks:** 3
- **Files modified:** 1 (Makefile)

## Accomplishments
- Five guarded launchpad stubs (`build-launchpad`, `load-launchpad`, `deploy-launchpad`, `port-forward-launchpad`, `smoke-launchpad`) replaced with real bodies mirroring their field-guide-api analogs, using `LP_*` variables throughout
- `up-all` (cluster + both apps, one command) and `smoke-all` (both apps' smoke tests) aggregates added, with a D-09 reviewer-guiding echo epilogue on `up-all`
- `make help` rewritten to the standard `##@`-grouped awk pattern — all six launchpad targets and all field-guide-api targets render under labeled sections
- `verify-ttl` added: deterministic default mode asserts the `events.ts` TTL index exists via `kubectl exec` + `mongosh getIndexes`, with an opt-in `TTL_DEEP=1` slow live-expiry round-trip kept out of the fast smoke path
- `clean-venv` and `reset-local` extended for full launchpad parity (both venvs removed, both Helm releases undeployed before cluster teardown)

## Task Commits

Each task was committed atomically:

1. **Task 1: Fill the six launchpad targets + up-all/smoke-all/undeploy-launchpad + .PHONY** - `ea8adf0` (feat)
2. **Task 2: Grouped ##@ help + extended clean-venv/reset-local** - `c063320` (feat)
3. **Task 3: verify-ttl target (index-existence default, TTL_DEEP=1 deep mode)** - `6813645` (feat)

**Plan metadata:** (this commit, SUMMARY.md)

## Files Created/Modified
- `Makefile` - filled 5 launchpad stub bodies; added up-all, smoke-all, undeploy-launchpad, verify-ttl; rewrote help to grouped ##@ sections; extended clean-venv and reset-local; updated .PHONY

## Decisions Made
- Confirmed the launchpad mongodb pod selector label (`app.kubernetes.io/name: launchpad-mongodb`) directly against `charts/launchpad/templates/_helpers.tpl` `launchpad.mongodb.selectorLabels` before writing `verify-ttl` — matches plan expectation exactly, no divergence
- `TTL_DEEP=1` deep-mode body (no in-repo analog) composed as: insert a probe event doc, then poll every 5s up to 18 iterations (90s cap) via `mongosh countDocuments`, PASS when the count reaches 0 (TTL monitor removed it), FAIL with exit 1 if the 90s bound is exceeded
- Kept the `##@ field-guide-api` marker appearing twice in the file (once above `test`, once above `build`/`load`/`deploy`/`undeploy`/`up`) rather than reordering existing targets purely for cosmetic single-section grouping — `make help` output still groups correctly since awk just prints headers in encounter order, and this avoids touching stable target bodies

## Deviations from Plan

None - plan executed exactly as written. All acceptance criteria and automated verification strings matched on first implementation pass (the one grep mismatch during self-verification was a shell-escaping artifact in my own ad-hoc check command, not a defect in the Makefile — `make help` confirmed the `##@` awk rule renders correctly).

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. Live cluster verification (kubectl/helm reaching a running kind cluster) is deferred to Plan 02's checkpoint per the plan's `<verification>` section ("live-verified in Plan 02's checkpoint").

## Next Phase Readiness

- `Makefile` is fully wired for Plan 02 (README/docs/screenshots) to reference `make up-all` → `make port-forward-launchpad` → `http://localhost:8081` → `make smoke-all` as the reviewer demo flow
- `make -n up-all` sanity-expanded cleanly (cluster-up → build/load/deploy field-guide-api → build/load/deploy launchpad → epilogue) with no live cluster required
- `make help` output live-verified in Git Bash: all six launchpad targets and all field-guide-api targets present with one-line descriptions, grouped under Cluster / field-guide-api / launchpad / Housekeeping headers
- Live `make up-all` / `make smoke-launchpad` / `make verify-ttl` execution against a real kind cluster is the responsibility of Plan 02's checkpoint (cluster state was not asserted live in this plan per the environment note — Docker/kind may or may not be running on this host)

---
*Phase: 10-makefile-integration-smoke-docs*
*Completed: 2026-07-13*
