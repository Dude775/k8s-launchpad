---
phase: 06-ui-layer-templates-static-assets
plan: 02
subsystem: ui
tags: [flask, jinja2, htmx, pico-css, blueprints, server-rendered]

# Dependency graph
requires:
  - phase: 06-ui-layer-templates-static-assets (Plan 01)
    provides: vendored htmx.min.js (2.0.10), vendored pico.min.css (2.1.1), app/static/style.css Pico override companion stylesheet
provides:
  - pages_bp blueprint (GET /, /catalog, /diagnostics, /feed)
  - partials_bp blueprint (GET /partials/status-cards htmx fragment stub)
  - base.html two-column shell (sidebar nav + topbar + content block)
  - four page templates (index, catalog, diagnostics, feed) extending base.html
  - status_cards.html fragment (degraded "Status unavailable" stub, Phase 7 fills real data)
  - test_pages.py, test_partials.py, extended test_static_assets.py (100% coverage)
affects: [07-status-check-engine, 08-diagnostics, 09-catalog-and-feed]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Deferred blueprint imports inside create_app() with `# noqa: PLC0415`, registered after health_bp"
    - "Server-side active-nav detection via request.endpoint comparison in Jinja (no JS)"
    - "htmx fragment routes are contract-frozen: fragment-only by design, documented in docstring, never wrapped in base.html conditionally on HX-Request"
    - "Route contract stays stable across phases: same route evolves in place (pages.py catalog/diagnostics/feed fill in Phase 8/9; partials.py status_cards fills in Phase 7)"

key-files:
  created:
    - apps/launchpad/app/routes/pages.py
    - apps/launchpad/app/routes/partials.py
    - apps/launchpad/app/templates/base.html
    - apps/launchpad/app/templates/index.html
    - apps/launchpad/app/templates/catalog.html
    - apps/launchpad/app/templates/diagnostics.html
    - apps/launchpad/app/templates/feed.html
    - apps/launchpad/app/templates/partials/status_cards.html
    - apps/launchpad/tests/test_pages.py
    - apps/launchpad/tests/test_partials.py
  modified:
    - apps/launchpad/app/routes/__init__.py
    - apps/launchpad/app/__init__.py
    - apps/launchpad/tests/test_static_assets.py

key-decisions:
  - "Followed 06-PATTERNS.md/06-RESEARCH.md exact target code verbatim for pages.py, partials.py, base.html, index.html, status_cards.html — no deviation needed"
  - "hx-trigger string kept byte-exact to UI-SPEC/RESEARCH pinned contract: 'load, every 15s [document.visibilityState === 'visible'], visibilitychange[document.visibilityState === 'visible'] from:document'"

patterns-established:
  - "Fragment-only htmx routes get an explicit docstring warning against ever growing an HX-Request-conditional base.html wrap"
  - "Every route module opens with a module docstring documenting the exact route contract and forward-looking phase notes, mirroring health.py"

requirements-completed: [UI-01, UI-02, UI-03, UI-04]

# Metrics
duration: 22min
completed: 2026-07-10
---

# Phase 6 Plan 2: Dashboard UI Shell — Blueprints, Templates, Tests Summary

**Two-blueprint Flask/Jinja2 dashboard shell (pages_bp + partials_bp) with a sidebar-nav base.html shell, htmx-polling status cards (15s interval, tab-visibility guard), and a degraded-stub status-cards fragment route, all covered at 100% test coverage.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-07-10T21:26:27Z
- **Completed:** 2026-07-10T21:32:26Z
- **Tasks:** 3
- **Files modified:** 13 (10 created, 3 modified)

## Accomplishments
- `GET /`, `/catalog`, `/diagnostics`, `/feed` all render inside the shared `base.html` shell with correct active-nav highlighting via `aria-current="page"` (server-computed, no JS)
- Landing page status-cards section is sourced from `GET /partials/status-cards` via htmx `hx-get`, never a hardcoded status string (UI-03)
- htmx polling contract implemented byte-exact to the pinned spec: `every 15s` interval with `[document.visibilityState === 'visible']` guard plus a `visibilitychange` resume trigger (UI-04)
- `/partials/status-cards` always returns HTTP 200 with the "Status unavailable" degraded fragment — never 500, never a full page — ready for Phase 7 to swap in real data in place
- Full `apps/launchpad` test suite: 21 passed, 100% coverage (`pages.py`/`partials.py` both at 100%)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add pages + partials blueprints and register them in the factory** - `24359fb` (feat)
2. **Task 2: Author the base shell + four page templates + status-cards fragment** - `7b70f25` (feat)
3. **Task 3: Write route/partial/no-CDN tests to 100% coverage** - `54cbb73` (test)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified
- `apps/launchpad/app/routes/pages.py` - `pages_bp` blueprint: GET /, /catalog, /diagnostics, /feed
- `apps/launchpad/app/routes/partials.py` - `partials_bp` blueprint: GET /partials/status-cards htmx fragment stub
- `apps/launchpad/app/routes/__init__.py` - extended barrel to re-export pages_bp, partials_bp
- `apps/launchpad/app/__init__.py` - extended deferred-import registration block for both new blueprints
- `apps/launchpad/app/templates/base.html` - two-column shell: sidebar nav (4 links, active-state via aria-current) + topbar + content block; url_for-based asset links (pico.min.css, style.css after it, htmx.min.js deferred)
- `apps/launchpad/app/templates/index.html` - landing page with htmx-polling `#status-cards` section, server-rendered loading fallback
- `apps/launchpad/app/templates/catalog.html` - thin placeholder extending base.html (Phase 9 fills in)
- `apps/launchpad/app/templates/diagnostics.html` - thin placeholder extending base.html (Phase 8 fills in)
- `apps/launchpad/app/templates/feed.html` - thin placeholder extending base.html (Phase 9 fills in)
- `apps/launchpad/app/templates/partials/status_cards.html` - fragment-only degraded "Status unavailable" card, no base.html extends
- `apps/launchpad/tests/test_pages.py` - UI-01/02/03/04 route-level assertions (5 tests)
- `apps/launchpad/tests/test_partials.py` - degraded-state contract assertion (1 test)
- `apps/launchpad/tests/test_static_assets.py` - extended with `test_no_cdn_references` across all four routes

## Decisions Made
- Implemented all templates and routes verbatim against 06-PATTERNS.md's exact target code blocks (which were themselves already project-vetted from 06-RESEARCH.md Pattern 2/3) — no deviation from the pinned copy, hx-trigger string, or route shapes was needed.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Windows shell (`python -c "..."` via the Bash tool) mangled multi-line inline Python for verification commands; worked around by writing verification scripts to the session scratchpad and running them via `PYTHONPATH=. .venv/Scripts/python.exe <script>`. No project files were affected — verification-only workaround.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 7 (status-check engine) can edit `partials.py::status_cards()` in place to call real `/api/status` internals — route path, template name, and the htmx `hx-get` target in `index.html` are frozen and unchanged.
- Phase 8 (diagnostics) and Phase 9 (catalog, feed) can fill in `diagnostics.html` / `catalog.html` / `feed.html` content in place — route names and template names are frozen and unchanged.
- Manual (non-automatable) verification steps remain for the human reviewer per the plan's `<verification>` block: network-disconnected browser load with zero outbound requests, and the htmx polling-pause devtools 3-step check (Pitfall 2). These are phase-gate checklist items, not automatable in pytest without a browser harness.

---
*Phase: 06-ui-layer-templates-static-assets*
*Completed: 2026-07-10*
