---
phase: 03-containerization-helm-deployment
plan: 03
subsystem: infra
tags: [makefile, docker, helm, kind, local-registry, build-loop]

# Dependency graph
requires:
  - phase: 03-01
    provides: apps/field-guide-api/Dockerfile (build context for `make build`)
  - phase: 03-02
    provides: charts/field-guide-api/ (Helm chart used by `make deploy`)
provides:
  - Makefile build/load/deploy/undeploy targets wrapping the full local build-to-deploy loop
  - Overridable IMAGE, TAG, RELEASE, CHART variables for flexibility
affects: [03-04, phase-04]

# Tech tracking
tech-stack:
  added: []
  patterns: [inline-one-liner make targets, overridable ?= make variables, doc-comment ## style]

key-files:
  created: []
  modified:
    - Makefile

key-decisions:
  - "Inline one-liner recipes (not script delegation) for build/load/deploy/undeploy — keeps the loop visible and overridable"
  - "Removed `--atomic` reference from comments entirely — grep-c == 0 enforced per CLAUDE.md constraint"
  - "`helm upgrade --install` (idempotent) with `--wait --timeout 180s` — no --atomic (removed from helm install in Helm 4)"

patterns-established:
  - "Overridable variable pattern: IMAGE ?= ..., TAG ?= ..., RELEASE ?= ..., CHART ?= ..."
  - "Inline one-liner Makefile target: single recipe line, no `$$` needed, Git-Bash/WSL2 safe"

requirements-completed: [HELM-02]

# Metrics
duration: 8min
completed: 2026-07-06
---

# Phase 3 Plan 03: Makefile Build-to-Deploy Loop Summary

**Four inline Makefile targets wire `docker build` + `docker push` + `helm upgrade --install` + `helm uninstall` into the `make build && make load && make deploy` loop with overridable IMAGE/TAG/RELEASE/CHART variables**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-07-06T16:16:00Z
- **Completed:** 2026-07-06T16:24:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Added `IMAGE ?=`, `TAG ?=`, `RELEASE ?=`, `CHART ?=` overridable variables to Makefile
- Added `build`, `load`, `deploy`, `undeploy` inline one-liner targets to `.PHONY` and Makefile
- Updated phase comment from "Phase 2" to "Phase 3: build, load, deploy, undeploy"
- Zero `--atomic` occurrences confirmed (Helm 4 compatibility — CLAUDE.md constraint)
- All existing targets (`test`, `cluster-up`, `cluster-down`) verified intact

## Task Commits

Each task was committed atomically:

1. **Task 1: Add build/load/deploy/undeploy Make targets** - `9de03d6` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `Makefile` - Added 4 overridable variables + 4 build-loop targets; updated phase comment and .PHONY

## Decisions Made

- Used inline one-liner recipes (not script delegation) per PATTERNS.md recommendation — keeps the loop commands visible and per-invocation-overridable
- `helm upgrade --install` chosen for idempotency; `--atomic` explicitly excluded (removed from `helm install` in Helm 4; banned in CLAUDE.md)
- Comment text for `deploy` target reworded to avoid any literal `--atomic` string so `grep -c -- '--atomic' Makefile == 0` holds

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed --atomic from deploy target comment**
- **Found during:** Task 1 (acceptance criteria verification)
- **Issue:** Original comment text `(idempotent; never --atomic)` contained the literal `--atomic` string, causing `grep -c -- '--atomic' Makefile` to return 1, failing the acceptance criterion
- **Fix:** Rewrote comment to `(idempotent; helm upgrade --install)` — no literal `--atomic` string
- **Files modified:** Makefile
- **Verification:** `grep -c -- '--atomic' Makefile` returns 0
- **Committed in:** 9de03d6 (same task commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in comment content)
**Impact on plan:** Trivial wording change. No scope creep. Acceptance criteria now fully satisfied.

## Issues Encountered

None beyond the comment-text grep fix documented above.

## User Setup Required

None - Makefile targets require no external service configuration. Prerequisites (kind cluster + registry) established in Phase 2 via `make cluster-up`.

## Next Phase Readiness

- `make build && make load && make deploy` loop is ready for 03-04 end-to-end verification
- All four targets dry-run verified (`make -n`) to produce exact RESEARCH.md Pattern 6 commands
- Phase 4 `make clean` / documentation targets can build on top of this Makefile without conflict

---
*Phase: 03-containerization-helm-deployment*
*Completed: 2026-07-06*
