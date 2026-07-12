---
phase: 09-service-catalog-events-mongodb-crud
plan: 02
subsystem: ui
tags: [flask, jinja2, htmx, wtforms, csrf, pico-css, mongomock]
requires:
  - phase: 09-service-catalog-events-mongodb-crud (plan 01)
    provides: "app.catalog / app.events never-raise helpers, ServiceForm, CSRFProtect singleton, mongomock test harness"
provides:
  - "real /catalog list, /catalog/new (GET+POST), /catalog/<name>, /catalog/<name>/delete (GET+POST) routes"
  - "GET /partials/feed fragment/full-page endpoint mirroring the status-cards/cluster-state HX-Request split"
  - "seven templates: catalog.html, onboard_form.html, detail.html, confirm_delete.html, feed.html, feed_full_page.html, partials/event_row.html, partials/feed_events.html"
  - "shared partials/event_row.html consumed by both /feed and the detail page (D-09)"
affects:
  - 09-03 (charts/launchpad in-cluster MongoDB — no route/template dependency, parallel wave)
  - Phase 10 (make up-all / smoke targets will exercise this demoable surface end-to-end)
tech-stack:
  added: []
  patterns:
    - "module-attribute imports for monkeypatchable seams: from app import catalog, events (Phase 8 BLOCKER 3 discipline extended to Phase 9 routes)"
    - "shared Jinja partial (event_row.html) reused across two render call sites (feed fragment + detail page) via context-inherited `events` module and per-context loop variable naming (events_list/event vs events_for_service)"
    - "two-tier CSRF test posture: conftest app fixture defaults WTF_CSRF_ENABLED=False; exactly one dedicated test overrides it True to prove the wiring is live"
key-files:
  created:
    - apps/launchpad/app/templates/onboard_form.html
    - apps/launchpad/app/templates/detail.html
    - apps/launchpad/app/templates/confirm_delete.html
    - apps/launchpad/app/templates/feed_full_page.html
    - apps/launchpad/app/templates/partials/event_row.html
    - apps/launchpad/app/templates/partials/feed_events.html
  modified:
    - apps/launchpad/app/routes/pages.py
    - apps/launchpad/app/routes/partials.py
    - apps/launchpad/app/templates/catalog.html
    - apps/launchpad/app/templates/feed.html
    - apps/launchpad/app/templates/base.html
    - apps/launchpad/tests/conftest.py
    - apps/launchpad/tests/test_pages.py
    - apps/launchpad/tests/test_partials.py
decisions:
  - "Renamed the /catalog view function from catalog to catalog_list (endpoint pages.catalog -> pages.catalog_list) to avoid shadowing the `from app import catalog` module import mandated by the module-attribute discipline; base.html's active-nav check broadened to request.endpoint.startswith('pages.catalog') so it still highlights for all /catalog* sub-routes"
  - "conftest.py's shared app/client fixture now defaults WTF_CSRF_ENABLED=False (previously left CSRF on by default per the 09-01 handoff note) so the majority of new route/form tests don't need a per-test override; the one CSRF-enabled round-trip test explicitly re-enables it, matching RESEARCH Pitfall 3's two-tier posture"
  - "event_row.html reads events._relative_time via the `events` module passed into template context (not a Jinja global/context-processor) — kept consistent with the plan's module-attribute-only integration surface; loop variable renamed to events_list/event at call sites to avoid colliding with the events module name in the same context"
  - "Table/detail Environment column rendered as plain inline text (no badge/pill), Registered At as server-side strftime('%Y-%m-%d') — per UI-SPEC Table Contract, no new CSS introduced"
metrics:
  duration: "~35 min active execution"
  tasks: 3
  tests: "126 passed, 100% coverage"
  completed: "2026-07-13"
---

# Phase 9 Plan 02: Catalog + Feed User Experience Summary

Real Flask routes and seven Jinja2/Pico templates turning the 09-01 data/form contracts into the full catalog CRUD + 15s-polling activity feed demo surface — register a service, watch it appear in the feed and in a shared detail-page event list, deregister it through a zero-JS confirm page.

## Performance

- **Duration:** ~35 min active execution
- **Completed:** 2026-07-13
- **Tasks:** 3
- **Files modified/created:** 14

## Accomplishments

- `/catalog` lists services newest-first in a Pico table or renders the D-09 empty-state CTA when none exist
- `/catalog/new` (GET+POST): valid submissions persist via `catalog.register_service`, fire `service_registered`, redirect to `/catalog`; invalid/duplicate submissions re-render the same form full-page with inline errors, preserved values, and no write (D-06)
- `/catalog/<name>` shows the full registration plus that service's related events, rendered through the same `partials/event_row.html` the feed uses
- `/catalog/<name>/delete` (GET+POST): a zero-JS server-rendered confirm page, then a CSRF-protected POST that removes the document and fires `service_deregistered`
- `/partials/feed` mirrors the established status-cards/cluster-state fragment-vs-full-page split; `/feed` polls it every 15s with the visibility guard (D-11)
- One CSRF-enabled test proves missing/invalid token → 400 and a scraped token → not-400, live end-to-end through the real CSRFProtect wiring

## Task Commits

Each task was committed atomically (Task 3's templates were committed together with Task 1 since Task 1's route tests directly depend on them; the code itself remains scoped and traceable to its originating task in this summary):

1. **Task 1: Catalog CRUD routes** (+ Task 3 templates: catalog.html, onboard_form.html, detail.html, confirm_delete.html, partials/event_row.html) - `4e9c197` (feat)
2. **Task 2: /partials/feed route + feed polling shell + shared event-row partials** - `c64a786` (feat)

## Files Created/Modified

- `apps/launchpad/app/routes/pages.py` - real catalog_list/catalog_new/catalog_detail/catalog_delete_confirm/catalog_delete routes via `from app import catalog, events` module-attribute calls
- `apps/launchpad/app/routes/partials.py` - added `GET /partials/feed` fragment/full-page branch via `from app import events`
- `apps/launchpad/app/templates/catalog.html` - table (Name link/Environment/Owner/Registered At) or D-09 empty-state CTA
- `apps/launchpad/app/templates/onboard_form.html` - single-column WTForms form, hidden_tag CSRF, inline errors, autofocus-on-first-error, no htmx
- `apps/launchpad/app/templates/detail.html` - Registration + Related Events (shared event_row.html), Deregister link
- `apps/launchpad/app/templates/confirm_delete.html` - zero-JS destructive confirm page, raw csrf_token hidden input
- `apps/launchpad/app/templates/feed.html` - visibility-guarded 15s poll targeting `#activity-feed`
- `apps/launchpad/app/templates/feed_full_page.html` - full-page wrapper for direct `/feed` navigation
- `apps/launchpad/app/templates/partials/event_row.html` - shared glyph/label/service-link/relative-time row, consumed by feed + detail
- `apps/launchpad/app/templates/partials/feed_events.html` - empty-state vs populated event list fragment
- `apps/launchpad/app/templates/base.html` - active-nav check broadened for the `pages.catalog_list` endpoint rename
- `apps/launchpad/tests/conftest.py` - `app` fixture now defaults `WTF_CSRF_ENABLED=False`
- `apps/launchpad/tests/test_pages.py` - 15 new tests: empty/seeded catalog, form GET/valid-POST/invalid-POST/duplicate-POST, detail 200/404, delete confirm 200/404, delete POST+event, CSRF round-trip
- `apps/launchpad/tests/test_partials.py` - 7 new tests: feed fragment/full-page, empty state, glyph/label/link per event type

## Decisions Made

- Renamed `pages.catalog` view function to `catalog_list` to resolve the unavoidable name collision with the mandated `from app import catalog` module import; route path `/catalog` itself is unchanged. `base.html`'s active-nav check now matches any `pages.catalog*` endpoint so the Catalog nav item still highlights correctly across all sub-routes (list/new/detail/delete).
- `conftest.py`'s shared `app`/`client` fixture now defaults `WTF_CSRF_ENABLED=False` (see Deviations — this was a blocking gap left by 09-01's handoff note, closed here since the majority of this plan's tests are form-posting route tests).
- `event_row.html` receives the `events` module itself (not just data) as template context so it can call `events._relative_time(event.ts)` — consistent with keeping all business logic in the never-raise helper layer, never duplicated in Jinja.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `catalog` view function name collides with the mandated `catalog` module import**
- **Found during:** Task 1 implementation
- **Issue:** The plan's read_first note said to "keep /catalog and /feed route paths and function names," but the plan's own action text also mandates `from app import catalog, events` (module-attribute discipline). A view function named `catalog()` in the same module as `import catalog` is a direct name collision — Python would resolve `catalog` to whichever binding executes last, silently breaking either the route or the module calls.
- **Fix:** Renamed the view function to `catalog_list` (endpoint `pages.catalog_list`); the URL path `/catalog` is unchanged. Updated `base.html`'s `url_for`/`request.endpoint` references to match, and broadened the active-nav check to `request.endpoint.startswith('pages.catalog')` so it still highlights for `/catalog/new`, `/catalog/<name>`, etc.
- **Files modified:** apps/launchpad/app/routes/pages.py, apps/launchpad/app/templates/base.html
- **Commit:** 4e9c197

**2. [Rule 3 - Blocking] conftest's default `app`/`client` fixture left CSRF enabled, failing nearly every new form-posting test**
- **Found during:** Task 1 test-writing (first test run against `/catalog/new` POST returned 400 instead of the expected redirect/re-render)
- **Issue:** The 09-01 SUMMARY explicitly flagged this: "Route tests should set WTF_CSRF_ENABLED=False per-test (fixture default leaves CSRF on)." Applying that per-test would mean adding the override to nearly every new test in this plan (most POST /catalog/new and POST /catalog/<name>/delete tests), which is exactly the anti-pattern RESEARCH Pitfall 3 warns against in the other direction (blanket-disabling would hide a CSRF regression) — but a fixture-level default with one deliberate override is the documented two-tier posture the plan itself expects ("the default app/client fixtures in conftest.py keep WTF_CSRF_ENABLED=False for convenience... ONE dedicated test... overrides it").
- **Fix:** Added `"WTF_CSRF_ENABLED": False` to the `create_app()` overrides in conftest.py's `app` fixture, with an inline comment explaining the two-tier posture. `test_onboard_form_rejects_missing_csrf_token` and `test_catalog_new_get_renders_fresh_csrf_token` explicitly re-enable it via `app.config["WTF_CSRF_ENABLED"] = True` to prove the wiring is live.
- **Files modified:** apps/launchpad/tests/conftest.py
- **Commit:** 4e9c197

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both fixes were necessary to make the plan's own stated contracts (module-attribute import discipline; two-tier CSRF test posture) actually work together — no scope creep, no architectural change.

## Issues Encountered

None beyond the two deviations above — the 09-01 data/form/CSRF contracts (`catalog.register_service`, `events.record_event`, `ServiceForm`, `CSRFProtect`) were consumed exactly as documented, with no interface changes needed.

## Verification Evidence

- Full suite: `python -m pytest --cov=app --cov-report=term-missing --cov-fail-under=100` → **126 passed, TOTAL coverage 100%**
- `grep -n "from app import catalog, events" app/routes/pages.py` → present; no `from app.catalog import` / `from app.events import` direct-name imports anywhere in app/ (docstring mentions excluded)
- `grep -n "every 15s" app/templates/feed.html` → present; `every 10s` absent
- Manual end-to-end round trip verified live (register -> catalog list shows it -> detail page shows registration + service_registered event -> feed fragment shows `+` glyph + link -> confirm page renders -> POST delete removes it -> catalog empty state returns)
- CSRF round trip verified live: missing/invalid token -> 400; token scraped from a prior GET -> not 400

## Known Stubs

None — every template renders real data from `catalog`/`events` helper calls; no hardcoded empty values or placeholder copy flow into any page beyond the UI-SPEC's own locked empty-state strings.

## Threat Flags

None — all new surface (POST /catalog/new, POST /catalog/<name>/delete, service.description/name rendering, /catalog/<name> path lookup) is covered by the plan's own threat register (T-09-06..09); no new endpoints, auth paths, or schema changes beyond what the register anticipated.

## Next Phase Readiness

- CAT-01..05 and FEED-01/02 are fully implemented and test-covered; the live-demo moment (register in one tab, watch it appear in the polling feed) is exercised end-to-end in tests and manually verified.
- 09-03 (in-cluster MongoDB manifests) has no dependency on this plan's routes/templates and can proceed independently — it only needs `charts/launchpad/templates/mongodb/` and the Secret/ConfigMap wiring.
- No blockers for Phase 10 (`make up-all` / smoke) — the demoable surface this plan built is exactly what that phase will exercise against a real in-cluster MongoDB instead of mongomock.

---
*Phase: 09-service-catalog-events-mongodb-crud*
*Completed: 2026-07-13*
