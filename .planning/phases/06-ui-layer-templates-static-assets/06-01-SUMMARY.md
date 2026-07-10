---
phase: 06-ui-layer-templates-static-assets
plan: 01
subsystem: ui
tags: [htmx, pico-css, static-assets, offline, flask-static]

# Dependency graph
requires:
  - phase: 05-monorepo-scaffold-app-factory
    provides: launchpad Flask app factory, app/static and app/templates default resolution, 100%-coverage pytest harness
provides:
  - Vendored htmx 2.0.10 (app/static/vendor/htmx.min.js) and Pico CSS 2.1.1 (app/static/vendor/pico.min.css), committed to git, zero-CDN offline guarantee (UI-05)
  - Companion override stylesheet app/static/style.css (Pico CSS custom-property theming: primary/destructive colors, light+dark scheme, active-nav rule, heading weight, sidebar touch target)
  - Filesystem-presence test (tests/test_static_assets.py::test_vendored_assets_exist_on_disk)
affects: [06-02-templates-blueprints, phase-9-catalog-ui]

# Tech tracking
tech-stack:
  added: [htmx.org@2.0.10 (vendored), "@picocss/pico@2.1.1 (vendored)"]
  patterns: ["Pico CSS custom-property override in a companion stylesheet loaded after pico.min.css", "Static assets vendored via one-time download + git commit, never fetched at runtime"]

key-files:
  created:
    - apps/launchpad/app/static/vendor/htmx.min.js
    - apps/launchpad/app/static/vendor/pico.min.css
    - apps/launchpad/app/static/style.css
    - apps/launchpad/tests/test_static_assets.py
  modified: []

key-decisions:
  - "Resolved RESEARCH.md Open Question 1 (active sidebar-nav visibility) by adding an explicit .sidebar a[aria-current=\"page\"] override in style.css rather than relying on Pico's default nav styling"
  - "Pinned heading weight to 600 (not Pico's default 700) and enforced no 300/500/700 font-weights anywhere in style.css, per UI-SPEC Typography contract"
  - "Human checkpoint T-06-SC (supply-chain provenance) approved — vendored htmx/pico bytes verified as genuine minified libraries of expected size before commit"

patterns-established:
  - "Pattern 1: Companion stylesheet override — theme via CSS custom properties in a small style.css loaded after the vendored framework CSS, no build step, no SASS"

requirements-completed: [UI-05]

# Metrics
duration: 9min
completed: 2026-07-10
---

# Phase 6 Plan 1: Vendor Offline Assets + Style Overrides Summary

**Vendored htmx 2.0.10 + Pico CSS 2.1.1 offline into app/static/vendor/, with a companion style.css applying the platform's blue accent theme, dark-mode variant, active-nav rule, and WCAG touch-target spacing.**

## Performance

- **Duration:** 9 min (Task 2 continuation segment; Task 1 vendoring completed in a prior agent run)
- **Started:** 2026-07-10T21:11:41Z (approx, per STATE.md Task 1 session)
- **Completed:** 2026-07-10T21:20:41Z
- **Tasks:** 2 (Task 1 + human-verify checkpoint completed in prior run; Task 2 completed in this continuation)
- **Files modified:** 4 (2 vendored assets, 1 test file — Task 1; 1 stylesheet — Task 2)

## Accomplishments
- Vendored htmx 2.0.10 (51,238 bytes) and Pico CSS 2.1.1 (83,319 bytes) into `app/static/vendor/`, both human-verified as genuine minified libraries (checkpoint T-06-SC approved) — satisfies UI-05's zero-CDN offline requirement
- Authored `app/static/style.css` with all required Pico custom-property overrides: blue accent (`#2563eb` light / `#3b82f6` dark), red destructive color, active-nav visibility fix, 600-weight headings, 44px sidebar touch targets
- Added `tests/test_static_assets.py::test_vendored_assets_exist_on_disk` filesystem-presence test

## Task Commits

Each task was committed atomically:

1. **Task 1: Vendor htmx.min.js + pico.min.css and add filesystem-presence tests** - `ce6a8ce` (feat) — completed in prior agent run, human checkpoint T-06-SC approved before this continuation began
2. **Task 2: Author style.css companion override sheet** - `b93cea9` (feat)

**Plan metadata:** (this commit, following SUMMARY)

## Files Created/Modified
- `apps/launchpad/app/static/vendor/htmx.min.js` - Vendored htmx 2.0.10, served offline via Flask static handler
- `apps/launchpad/app/static/vendor/pico.min.css` - Vendored Pico CSS 2.1.1, served offline via Flask static handler
- `apps/launchpad/app/static/style.css` - Companion stylesheet: Pico custom-property color overrides (light/dark), active-nav rule, heading weight, sidebar touch target
- `apps/launchpad/tests/test_static_assets.py` - Filesystem-presence assertions for the two vendored assets

## Decisions Made
- Active-nav visibility (RESEARCH Open Question 1) resolved proactively with an explicit `.sidebar a[aria-current="page"]` CSS rule rather than waiting to inspect Pico's shipped nav styling — cheap, removes ambiguity, zero JS needed.
- No font-weights other than 400 (Pico's body default) and 600 (this file's heading override) appear anywhere in `style.css`, per UI-SPEC Typography contract.

## Deviations from Plan

None — plan executed exactly as written. Task 2's `style.css` matches the 06-PATTERNS.md style.css block verbatim.

## Issues Encountered

None. The human-verify checkpoint (T-06-SC, supply-chain provenance) was approved by the user prior to this continuation agent's start; both vendored files were confirmed as genuine, correctly-sized minified htmx/Pico builds before the Task 1 commit.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `app/static/vendor/htmx.min.js`, `app/static/vendor/pico.min.css`, and `app/static/style.css` are all present, committed, and ready to be referenced via `url_for('static', ...)` in Plan 02's `base.html` shell template.
- Plan 02 (pages + partials blueprints, base shell + 4 pages + status-cards fragment) can proceed immediately — no blockers.
- The `test_no_cdn_references` test (also part of UI-05) is deferred to Plan 02 as planned, since it depends on rendered templates that do not yet exist.

---
*Phase: 06-ui-layer-templates-static-assets*
*Completed: 2026-07-10*

## Self-Check: PASSED

All created files verified present on disk; both task commits (`ce6a8ce`, `b93cea9`) verified present in git log.
