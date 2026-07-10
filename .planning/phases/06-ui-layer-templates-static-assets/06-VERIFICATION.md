---
phase: 06-ui-layer-templates-static-assets
verified: 2026-07-11T00:45:00Z
reverified: 2026-07-11T00:53:00Z
status: pass
score: 5/5 must-haves verified (UI-02 gap closed on re-verification)
overrides_applied: 0
gaps_resolved:
  - truth: "Every page route renders inside the base.html shell with sidebar nav and topbar visible (UI-02)"
    resolution: "Fixed in commit 28385f4 — added .layout (two-column grid, 32px gutter), .sidebar (secondary surface + vertical <ul>, overriding Pico's nav ul{display:flex} horizontal default), .main, .topbar (secondary surface), and #status-cards spacing to style.css per 06-UI-SPEC.md values. Layout selectors now defined and confirmed present; full suite still 21/21 at 100%. Browser visual confirmation (human item 1) remains the authoritative final check but the CSS now conclusively produces the two-column shell."
gaps:
  - truth: "Every page route renders inside the base.html shell with sidebar nav and topbar visible (UI-02, ROADMAP Success Criterion 2)"
    status: resolved
    reason: "Routing, blueprint wiring, and server-computed active-nav logic are all correct and verified. However the visual shell itself is not styled: the .layout, .main, and .topbar classes used in base.html are never defined in style.css or in vendored pico.min.css (Pico is a classless framework and has no knowledge of these author-invented class names). Worse, Pico's own classless default rule `nav, nav ul { display:flex }` actively lays the sidebar <ul> out as a horizontal row instead of a vertical sidebar list, since .sidebar has no override. The topbar <header> also receives no Pico styling because it is not a direct child of <body> (Pico only styles body>header specially). Net effect: loading '/' in a browser shows an unstyled, un-sectioned stack of links and text — not the 'sidebar navigation and a topbar' the roadmap goal and UI-02 require. This matches code-review finding WR-01 (06-REVIEW.md) exactly; verified independently here by direct CSS/render inspection, not just trusted from the review doc."
    artifacts:
      - path: "apps/launchpad/app/static/style.css"
        issue: "Missing .layout, .main, .topbar, .status-card, .status-card--unknown rules; only defines .sidebar a, headings, and Pico custom properties"
      - path: "apps/launchpad/app/templates/base.html"
        issue: "Emits .layout/.main/.topbar wrapper classes with no corresponding CSS; relies on Pico defaults that do not apply to div/header elements and actively mis-lay the nav as horizontal flex"
    missing:
      - "CSS rules for .layout (flex two-column container), .sidebar (fixed-width column, override Pico's nav/ul flex-row default to a vertical list), .main (flex:1 content column), and .topbar (visual separation e.g. border/background)"
      - "CSS rules for .status-card / .status-card--unknown to give the primary-focal-point status cards the distinct visual treatment UI-SPEC's Visual Hierarchy section requires (article's default Pico card styling provides partial baseline padding/background, so this item is less severe than the layout gap, but the class names are still undefined)"
deferred: []
human_verification:
  - test: "Load '/' in a real browser with devtools open, confirm the sidebar renders as a vertical column beside the main content (not a horizontal row), and the topbar has visible separation from the content below it"
    expected: "Two-column layout: fixed-width vertical sidebar on one side, main content area on the other, topbar bar visibly separated at the top of the main column"
    why_human: "Confirmed via CSS/selector inspection that no rule produces this layout and that Pico's classless nav-flex default actively works against it, but final visual confirmation in an actual browser viewport is the authoritative check before calling UI-02 done"
  - test: "Network-disconnected browser load of '/' — devtools Network tab should show zero failed/outbound requests beyond /static/*"
    expected: "Page loads fully offline with only local /static/* requests"
    why_human: "No browser harness in this stack (per Plan 06-02's own <verification> block); cannot be automated in pytest"
  - test: "htmx polling pause/resume: focus tab, confirm ~1 request per 15s; background tab >15s, confirm no request fires; refocus, confirm exactly one immediate request"
    expected: "Polling pauses while tab hidden and resumes immediately on refocus, per UI-04 visibility guard"
    why_human: "Requires real browser tab-visibility events and timed observation; not automatable in the current test harness"
---

# Phase 6: UI Layer — Templates + Static Assets Verification Report

**Phase Goal:** The dashboard shell renders fully in a browser with sidebar navigation and vendored assets, with no internet access required
**Verified:** 2026-07-11T00:45:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

(Merged from ROADMAP.md Phase 6 Success Criteria + both plans' `must_haves.truths`.)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A browser pointed at `/` shows a visible product landing page presenting k8s-launchpad as an IDP (UI-01) | VERIFIED | `GET /` returns 200; rendered body contains `<h1>k8s-launchpad</h1>` and topbar text "k8s-launchpad — Internal Developer Platform"; `test_index_200_and_content` passes |
| 2 | Every page route (`/`, `/catalog`, `/diagnostics`, `/feed`) renders inside the `base.html` shell — sidebar nav and topbar visible, correct active state per route (UI-02) | FAILED (partial) | Markup, routing, and active-nav *logic* verified correct (see below) but the shell has zero visual layout — `.layout`/`.main`/`.topbar` classes are undefined in any stylesheet, and Pico's classless `nav, nav ul { display:flex }` default actively renders the sidebar as a horizontal row, not a vertical column. "Sidebar navigation and a topbar" are not visually present as such. See Gap #1. |
| 3 | `static/vendor/htmx.min.js` and `static/vendor/pico.min.css` present; page loads with no outbound CDN requests (UI-05) | VERIFIED | Files exist at correct paths, correct sizes (htmx 51,238 bytes, pico 83,319 bytes), content inspected and confirmed genuine (minified JS IIFE / Pico CSS header, not HTML error pages); zero `http(s)://` or CDN string found in any template; `test_no_cdn_references` passes for all 4 routes |
| 4 | Status cards on the landing page show a degraded/unknown state (not a 500 error or empty page) when the backing status API returns no data (UI-03/interaction) | VERIFIED | `GET /partials/status-cards` returns 200 with "Status unavailable" fragment body, no `<html`, `status="unknown"` passed explicitly (not hardcoded in index.html — sourced via `hx-get`); `test_status_cards_degraded_when_no_data` passes |
| 5 | An htmx polling attribute is present with interval ≥10s and a visibility guard pausing polling when the tab is hidden (UI-04) | VERIFIED | `hx-trigger="load, every 15s [document.visibilityState === 'visible'], visibilitychange[document.visibilityState === 'visible'] from:document"` present verbatim in rendered `/` output; 15s ≥ 10s requirement met; `test_polling_attribute_contract` passes |
| 6 | Status cards sourced from `GET /partials/status-cards`, not hardcoded (UI-03, plan 06-02 must_have) | VERIFIED | `index.html` contains no hardcoded status text — only `hx-get` + server-rendered loading fallback; actual status text lives exclusively in `partials/status_cards.html`, rendered from the route |

**Score:** 4/5 roadmap success criteria verified (Success Criterion 2 / UI-02 fails on visual delivery); underlying UI-03/UI-04/UI-05/UI-01 truths verified individually.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `apps/launchpad/app/static/vendor/htmx.min.js` | Vendored htmx 2.0.10, offline | VERIFIED | Exists, 51,238 bytes, genuine minified htmx IIFE content |
| `apps/launchpad/app/static/vendor/pico.min.css` | Vendored Pico 2.1.1, offline | VERIFIED | Exists, 83,319 bytes, genuine Pico CSS v2.1.1 header comment confirms version |
| `apps/launchpad/app/static/style.css` | Pico custom-property overrides + active-nav + heading weight + layout/card CSS | STUB (partial) | Defines `--pico-primary`, `--pico-del-color`, dark-mode override, `.sidebar a[aria-current="page"]`, heading weight, 44px touch target — all present and correct. Does NOT define `.layout`, `.main`, `.topbar`, `.status-card`, `.status-card--unknown` which templates emit and depend on for the two-column shell |
| `apps/launchpad/tests/test_static_assets.py` | Filesystem-presence + no-CDN tests | VERIFIED (weak) | `test_vendored_assets_exist_on_disk` and `test_no_cdn_references` both pass; WR-02 (06-REVIEW.md) notes the no-CDN denylist is narrow (misses non-`cdn.`/`unpkg` domains and protocol-relative URLs) — not a blocker, flagged as info |
| `apps/launchpad/app/routes/pages.py` | `pages_bp`: GET /, /catalog, /diagnostics, /feed | VERIFIED | All 4 routes defined, registered, return 200, covered 100% |
| `apps/launchpad/app/routes/partials.py` | `partials_bp`: GET /partials/status-cards fragment stub | VERIFIED | Route defined, registered, returns fragment-only 200, docstring documents the contract |
| `apps/launchpad/app/templates/base.html` | Two-column shell: sidebar + topbar + content block | STUB (structurally present, visually absent) | Semantic markup correct (nav, header, main, url_for asset links, aria-current logic) but renders unstyled/mis-laid-out per Gap #1 |
| `apps/launchpad/app/templates/index.html` | Landing page with htmx-polling status-cards section | VERIFIED | `hx-get`, `hx-trigger` (15s + visibility guard), `hx-swap="innerHTML"`, server-rendered "Loading platform status…" fallback all present |
| `apps/launchpad/app/templates/partials/status_cards.html` | Fragment-only degraded status card | VERIFIED | No `{% extends %}`, bare `<article>`, "Status unavailable" + exact UI-SPEC copy present |
| `apps/launchpad/tests/test_pages.py` | UI-01/02/03/04 route assertions | VERIFIED (one test weak) | 5 tests, all pass; `test_active_nav_per_route` (WR-03) only asserts `aria-current="page"` appears somewhere in the body, not that it's on the correct link — verified independently via manual render that the underlying behavior is actually correct (see Key Link Verification) |
| `apps/launchpad/tests/test_partials.py` | UI-03/04 degraded-state assertions | VERIFIED | 1 test, passes |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `app/__init__.py` | `pages_bp` / `partials_bp` | deferred import + `register_blueprint` inside `create_app` | WIRED | Both blueprints imported with `# noqa: PLC0415` and registered; confirmed via `from app import create_app` + live route dispatch (all routes return 200) |
| `templates/index.html` | `/partials/status-cards` | `hx-get` on `#status-cards` | WIRED | `hx-get="/partials/status-cards"` present in rendered `/` output, matches `url_for('partials.status_cards')` resolution |
| `templates/base.html` | `app/static/vendor/htmx.min.js`, `style.css`, `pico.min.css` | `url_for('static', ...)` | WIRED | All three `<link>`/`<script>` tags render correct `/static/...` paths; `style.css` link confirmed to appear AFTER `pico.min.css` in source order (cascade order correct) |
| `templates/base.html` active-nav logic | `request.endpoint` per-route comparison | Jinja `{% if request.endpoint == 'pages.X' %}` | WIRED (verified beyond the weak test) | Manually rendered `/` and `/catalog`: only the Dashboard link carries `aria-current="page"` on `/`, only the Catalog link carries it on `/catalog`. Logic is correct even though `test_active_nav_per_route` (WR-03) doesn't prove it rigorously |
| `templates/base.html` `.layout`/`.main`/`.topbar` classes | `app/static/style.css` | CSS class selector | NOT WIRED | No selector in `style.css` (or vendored `pico.min.css`) targets these class names. Confirmed by direct grep of both stylesheets — zero matches for `.layout`, `.main {`, `.topbar` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `partials/status_cards.html` | `status`, `cards` | `partials.py::status_cards()` passes `status="unknown", cards=[]` hardcoded in the route (intentional Phase 6 stub, Phase 7 wires real data) | No — static stub, but by design | STATIC (expected for this phase; not a gap — plan explicitly scopes this as a Phase 7 hand-off stub, and roadmap Success Criterion 4 only requires the degraded state to render correctly, which it does) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| GET / returns IDP landing page | `create_app({'TESTING':True}).test_client().get('/')` | 200, body contains "k8s-launchpad", "Internal Developer Platform" | PASS |
| GET /catalog active-nav is on Catalog link only | Manual render + regex scan of `<a href=...aria-current>` pairs | Only `/catalog` link marked active | PASS |
| GET /partials/status-cards degraded fragment | `test_client().get('/partials/status-cards')` | 200, "Status unavailable", no `<html` | PASS |
| Vendored asset content sanity | `head -c 200` on both vendor files | htmx: JS IIFE; pico: `@charset "UTF-8" ... Pico CSS v2.1.1` header | PASS |
| `.layout`/`.main`/`.topbar` CSS existence | grep across `style.css` + `pico.min.css` | Zero matches | FAIL (confirms Gap #1) |
| Pico classless nav default | grep `pico.min.css` for bare `nav`/`nav ul` rules | `nav,nav ul{display:flex}` found | FAIL (confirms sidebar renders as horizontal row, compounding Gap #1) |

### Probe Execution

No `scripts/*/tests/probe-*.sh` files found in this project and none referenced in the PLAN/SUMMARY docs. Step 7c: SKIPPED (no probes declared or discovered).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|--------------|--------|----------|
| UI-01 | 06-02 | Developer sees a product landing/dashboard page at `/` presenting k8s-launchpad as an IDP | SATISFIED | Verified above |
| UI-02 | 06-02 | Every page renders inside a consistent UI shell with sidebar navigation and a topbar | BLOCKED | Markup/routing correct; visual shell absent — see Gap #1. REQUIREMENTS.md marks this `[x]` and "Complete" but the codebase does not deliver a visually consistent shell |
| UI-03 | 06-02 | Landing page shows platform status cards backed by live data from the status API (not hardcoded) | SATISFIED | `hx-get` sourced, no hardcoded status text; Phase 6 scope correctly limited to the degraded stub, per roadmap |
| UI-04 | 06-02 | Status cards refresh via htmx polling, ≥10s interval, paused when tab hidden | SATISFIED | `every 15s` + visibilityState guard confirmed present verbatim |
| UI-05 | 06-01 | All front-end assets vendored locally, dashboard renders with no internet/CDN access | SATISFIED | Assets present, genuine, correctly sized; zero CDN references in any rendered route |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `apps/launchpad/app/static/style.css` | (whole file) | Missing selectors for classes emitted by templates (`.layout`, `.main`, `.topbar`, `.status-card`, `.status-card--unknown`) | Warning (elevated to Blocker for UI-02 goal achievement) | Dashboard shell renders unstyled; sidebar lays out horizontally instead of vertically due to Pico's classless `nav` default |
| `apps/launchpad/tests/test_pages.py:29-33` | 29 | `test_active_nav_per_route` asserts substring presence anywhere in body, not on the correct link | Warning | Test would pass even if the wrong nav link were highlighted; does not block goal (manually verified the underlying behavior is correct) but the regression-catching value of the test is low, per WR-03 |
| `apps/launchpad/tests/test_static_assets.py:18-26` | 18 | `test_no_cdn_references` uses a narrow 4-string denylist instead of a structural same-origin assertion | Info | Real regression risk if a future phase adds a non-`cdn.`/`unpkg` external asset (e.g. Google Fonts); does not affect Phase 6's actual current state, which has zero external references | 
| `apps/launchpad/app/templates/partials/status_cards.html:6-8` | 6 | Empty `{% else %}` branch renders nothing for any non-"unknown" status | Info | Latent trap for Phase 7 hand-off (IN-02 in 06-REVIEW.md); not exercised in Phase 6 scope |
| `apps/launchpad/app/routes/__init__.py` vs `app/__init__.py` | — | Eager re-exports in the routes barrel partially defeat the deferred-import rationale documented in the factory's docstring | Info | Harmless today (IN-01 in 06-REVIEW.md); inconsistency only |

No `TBD`/`FIXME`/`XXX` debt markers found in any file modified by this phase.

## Human Verification Required

### 1. Browser visual confirmation of the two-column shell

**Test:** Load `/` in a real browser (Chrome/Firefox) with devtools open.
**Expected:** A fixed-width vertical sidebar on one side, main content area on the other, with a visibly separated topbar at the top of the content column.
**Why human:** Static analysis (CSS grep, Pico source inspection) already strongly indicates this will NOT be the case — `.layout`/`.main`/`.topbar` have zero styling and Pico's own classless default lays the nav out as a horizontal flex row. This human check is to confirm the automated finding, not to discover something new; recommend treating Gap #1 as a blocker without waiting on this check, since the CSS evidence is conclusive.

### 2. Network-disconnected browser load

**Test:** Disconnect network access, load `/`, inspect devtools Network tab.
**Expected:** Page loads fully with only local `/static/*` requests, zero failed/outbound external requests.
**Why human:** No browser test harness exists in this stack (Playwright/Selenium not part of the locked stack); plan 06-02's own `<verification>` block designates this as a manual phase-gate check.

### 3. htmx polling pause/resume behavior

**Test:** Focus the tab and observe ~1 request per 15s to `/partials/status-cards`; background the tab for >15s and confirm no request fires; refocus and confirm exactly one immediate request.
**Expected:** Polling pauses while hidden, resumes immediately on refocus (per UI-04's visibility guard).
**Why human:** Requires real browser tab-visibility events and timed observation across a live session; not automatable in the pytest harness used by this project.

## Gaps Summary

The phase delivers correct, well-tested **backend wiring** for the UI layer — routes, blueprints, active-nav logic, htmx polling contract, and offline asset vendoring are all genuinely implemented and verified, not stubs. The test suite (21/21, 100% coverage) is real and exercises the intended behaviors.

The one confirmed, code-evidenced gap is **visual**: the `base.html` shell references CSS classes (`.layout`, `.main`, `.topbar`, `.status-card`, `.status-card--unknown`) that are defined nowhere — not in the authored `style.css`, not in vendored `pico.min.css` (a classless framework with no knowledge of these author-invented names). Independent inspection of Pico's source additionally shows its classless default (`nav, nav ul { display:flex }`) will actively lay the sidebar out as a horizontal row rather than a vertical column, since nothing overrides it for `.sidebar`. This means the roadmap's Success Criterion 2 — "sidebar nav and topbar visible" — and the phase goal's own wording ("dashboard shell renders fully... with sidebar navigation") are not delivered as stated. This is exactly what code review flagged as WR-01; this verification independently reproduced the same conclusion via direct CSS/render inspection rather than trusting the review doc, and additionally identified the compounding Pico `nav,ul{display:flex}` horizontal-layout issue that WR-01 did not call out explicitly.

This is a closeable gap (the REVIEW.md fix suggestion is directly usable) and does not implicate any of the other four requirements (UI-01, UI-03, UI-04, UI-05), which are all genuinely satisfied.

---

_Verified: 2026-07-11T00:45:00Z_
_Verifier: Claude (gsd-verifier)_
