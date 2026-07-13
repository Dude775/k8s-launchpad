---
phase: 10-makefile-integration-smoke-docs
plan: 02
subsystem: docs
tags: [readme, docs, screenshots, makefile, troubleshooting, known-limitations]

# Dependency graph
requires:
  - phase: 10-makefile-integration-smoke-docs
    plan: 01
    provides: "up-all, smoke-all, smoke-launchpad, port-forward-launchpad, verify-ttl Makefile targets live-verified in this plan's checkpoint"
provides:
  - "README headlined around the browser demo (make up-all -> port-forward-launchpad -> localhost:8081 -> smoke-all)"
  - "Five real captured screenshots in docs/screenshots/ embedded in README (dashboard, catalog, onboard-form, diagnostics, feed)"
  - "Real captured /health output replacing the typed compact-JSON debt (D-13)"
  - "docs/troubleshooting.md launchpad port 8081 / stale-forward / launchpad-mongodb NotReady rows"
  - "docs/known-limitations.md WR-01 mongoUri entry + TTL-verified-live entry, closing Phase 9 FEED-03 flag"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Markdown image embeds for docs/screenshots/*.png as the README's primary demo evidence (no CI screenshot automation — human-captured, Claude-embedded)"

key-files:
  created:
    - docs/screenshots/dashboard.png
    - docs/screenshots/catalog.png
    - docs/screenshots/onboard-form.png
    - docs/screenshots/diagnostics.png
    - docs/screenshots/feed.png
  modified:
    - README.md
    - docs/troubleshooting.md
    - docs/known-limitations.md

key-decisions:
  - "Merged the WR-01 mongoUri known-limitations entry with the existing Committed Dev Password entry via cross-reference rather than duplicating the override command verbatim under two headings"
  - "PROJECT.md's degraded-CSS claim was already corrected in a prior session (Phase 7 fix c977206 already recorded at line 119) — no edit needed, verified via grep rather than re-writing"
  - "Field-guide-api's original one-command flow (make cluster-up && make build && make load && make deploy) preserved verbatim, relocated into a new Developer Loop / API Workload section rather than deleted"

patterns-established: []

requirements-completed: [DOCS-01]

# Metrics
duration: 33min
completed: 2026-07-14
---

# Phase 10 Plan 2: Makefile Smoke Docs Summary

**README restructured around the live launchpad browser demo with five real captured screenshots and real terminal output, plus launchpad-specific troubleshooting and known-limitations entries closing the Phase 9 FEED-03 TTL flag.**

## Performance

- **Duration:** 33 min (Task 1 checkpoint + Tasks 2-3, this continuation)
- **Started:** 2026-07-14T00:11:00Z (Task 1 checkpoint approval)
- **Completed:** 2026-07-13T23:44:47Z (SUMMARY authored; commit timestamps 02:43-02:44 local)
- **Tasks:** 3 (1 checkpoint + 2 auto)
- **Files modified:** 8 (README.md, docs/troubleshooting.md, docs/known-limitations.md, 5 new PNGs)

## Accomplishments
- Live full-stack demo verified end-to-end: `make up-all`, `make smoke-all`, `make smoke-launchpad`, `curl /health`, `make verify-ttl` all confirmed against a real running kind cluster
- Five real PNG screenshots captured from the live dashboard at `localhost:8081` (dashboard, catalog, onboard form, diagnostics, activity feed) — no secrets visible, human-reviewed
- README headline demo replaced: leads with `make up-all` -> `make port-forward-launchpad` -> `http://localhost:8081` -> `make smoke-all`, with the real captured epilogue and smoke-all PASS output
- `/health` compact-JSON cosmetic debt (D-13) fixed — README now shows the real captured `{"status": "ok", "mongo": "up"}` output instead of a hand-typed value
- Field-guide-api's original PRD-1 flow preserved intact in a new "Developer Loop / API Workload" section (not deleted)
- `docs/troubleshooting.md` gained two launchpad-specific rows: stale port 8081 forward (including the `taskkill //PID` fallback for native `kubectl.exe` on Windows) and `launchpad-mongodb` NotReady
- `docs/known-limitations.md` gained the WR-01 committed `mongoUri` entry (cross-referencing the existing password entry, no duplicated override command) and a TTL-verified-live entry that closes the Phase 9 FEED-03 flag
- Confirmed `.planning/PROJECT.md` already correctly records the Phase 7 degraded-CSS fix — no stale claim remained

## Task Commits

Each task was committed atomically:

1. **Task 1: Live demo bring-up + real captures** - checkpoint (no code commit; produced `docs/screenshots/*.png` as untracked artifacts, committed in Task 2)
2. **Task 2: Restructure README headline + demo flow + embed real screenshots + /health fix** - `0dfd15b` (docs)
3. **Task 3: Append launchpad troubleshooting rows + known-limitations entries** - `1d0dc86` (docs)

**Plan metadata:** (this commit, SUMMARY.md)

## Files Created/Modified
- `README.md` - headline/Quickstart rewritten around `make up-all` browser demo; new Demo Flow section with 5 embedded real screenshots; `/health` example shows real captured output; field-guide-api flow relocated to Developer Loop / API Workload section; Architecture/Prerequisites/Security Note/Repository Layout preserved
- `docs/screenshots/dashboard.png` - landing page status cards (MongoDB up, API reachable, version dev, 0 registered services)
- `docs/screenshots/catalog.png` - empty-state service catalog with onboarding CTA
- `docs/screenshots/onboard-form.png` - Register-a-Service form
- `docs/screenshots/diagnostics.png` - platform checks + cluster state (4 pods Running, 4 deployments ready)
- `docs/screenshots/feed.png` - activity feed with "Platform started" event
- `docs/troubleshooting.md` - two new rows: launchpad stale port-forward (8081) and launchpad-mongodb NotReady
- `docs/known-limitations.md` - WR-01 mongoUri entry (merged with Committed Dev Password entry) + TTL-verified-live entry

## Decisions Made
- Cross-referenced rather than duplicated the committed-password override command between the "Committed Dev Password" and "WR-01 — Committed Local-Dev mongoUri Defaults" entries in known-limitations.md, per the plan's explicit dedupe instruction
- Left `.planning/PROJECT.md` untouched after confirming via grep that the degraded-CSS claim was already corrected in a prior session (line 119 already records the Phase 7 fix, commit c977206) — re-verified rather than blindly re-editing
- Documented the Windows-specific `taskkill //PID` fallback (discovered live during the Task 1 checkpoint) in the stale-forward troubleshooting row, since `pkill -f` doesn't always reach a native `kubectl.exe` started from a different Git Bash shell

## Deviations from Plan

None - plan executed exactly as written. All acceptance criteria and automated verification strings matched on first implementation pass for both Task 2 and Task 3.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required. The live demo (Task 1) was verified by the human directly against a real kind cluster; no further setup is needed to view the README's embedded screenshots.

## Next Phase Readiness

- Phase 10 (Makefile Integration + Smoke + Docs) is now feature-complete: both plans (10-01 Makefile targets, 10-02 live verification + docs) delivered and live-verified
- README is now portfolio-demoable on GitHub without running anything — real screenshots + real terminal output throughout
- Phase 9 FEED-03 "verify live" flag closed via the documented `verify-ttl` target and known-limitations entry
- WR-01 (committed local-dev `mongoUri`) remains a genuinely open, now-documented limitation — not blocking, scoped to a future PRD if ever addressed
- No blockers for milestone completion review

---
*Phase: 10-makefile-integration-smoke-docs*
*Completed: 2026-07-14*

## Self-Check: PASSED

All 9 claimed files found on disk (README.md, docs/troubleshooting.md, docs/known-limitations.md,
5 screenshot PNGs, this SUMMARY.md). Both task commits (`0dfd15b`, `1d0dc86`) confirmed present
in git log.
