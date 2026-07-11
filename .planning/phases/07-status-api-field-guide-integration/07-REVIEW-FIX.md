---
phase: 07-status-api-field-guide-integration
fixed_at: 2026-07-11T03:03:00Z
review_path: .planning/phases/07-status-api-field-guide-integration/07-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 07: Code Review Fix Report

**Fixed at:** 2026-07-11T03:03:00Z
**Source review:** .planning/phases/07-status-api-field-guide-integration/07-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (all 4 Warnings; 4 Info findings out of scope per `critical_warning`)
- Fixed: 4
- Skipped: 0

All fixes were applied inside an isolated git worktree and each was verified by
running the full launchpad pytest suite (37 tests) at the enforced 100% coverage
gate (`pytest.ini --cov-fail-under=100`) before commit. Every commit passed the
gitleaks pre-commit hook.

## Fixed Issues

### WR-01: Status-card color modifiers have no CSS — degraded state is invisible

**Files modified:** `apps/launchpad/app/static/style.css`, `apps/launchpad/tests/test_partials.py`
**Commit:** c977206
**Applied fix:** Added `.status-card--ok`, `.status-card--degraded`,
`.status-card--unknown`, and `.status-card--info` modifier rules (left-border
color signal, Pico `-500` color vars with literal fallbacks) to `style.css`,
matching the existing custom-rule conventions in that file. The modifier classes
emitted by the in-scope templates now render a visible health signal. Also
strengthened `test_status_cards_degraded_when_field_guide_unreachable` to scope
the degraded modifier to the Field Guide API card (`status-card--degraded">\n
<header>Field Guide API</header>`) instead of merely asserting the class string
appears somewhere in the body — closing the false-confidence gap the review
called out.

### WR-02: "Version" and "Registered Services" cards colored by unrelated mongo health

**Files modified:** `apps/launchpad/app/templates/partials/status_cards.html`
**Commit:** eec9b76
**Applied fix:** The Version and Registered Services cards derived their color
modifier from `api_health` (computed solely from `mongo_status`), so a MongoDB
outage painted the app version and a normal `service_count == 0` red. Both cards
now render a static `status-card--info` neutral modifier (CSS added in WR-01) and
no longer imply a health dimension they do not represent.

### WR-03: `field_guide_reachable` conflates network reachability with app health

**Files modified:** `apps/launchpad/app/status.py`, `apps/launchpad/app/routes/status.py`, `apps/launchpad/app/templates/partials/status_cards.html`, `apps/launchpad/tests/test_status.py`, `apps/launchpad/tests/test_partials.py`
**Commit:** 1d15d96
**Applied fix:** Chose review option (a) — renamed the key
`field_guide_reachable` → `field_guide_healthy` across the `/api/status` JSON
contract, the `get_platform_status()` aggregation helper, the status-cards
template (card label now `healthy`/`unhealthy`), and the tests. This preserves
the documented six-key contract (option (b), adding a separate key, would have
broken `test_status_returns_exactly_six_keys` and the six-key assertion in
`test_api_status_...`). Added a clarifying comment that the value encodes
"field-guide-api returned HTTP 200", not bare network reachability. Added a
positive `"unhealthy"` label assertion to the partials degraded test to cover
the template's new label branch.

**NOTE — requires human verification:** This is a public JSON contract change
that Phase 8 will consume. The rename is mechanically complete and the full
suite is green, but a human should confirm (1) the `field_guide_healthy` name is
the intended Phase-8 contract (vs. the option-(b) reachable+healthy split), and
(2) no external artifact/plan doc outside `apps/launchpad/` still references the
old `field_guide_reachable` key. Grep across `apps/launchpad/` confirmed zero
remaining `field_guide_reachable` references in source and tests.

### WR-04: Blueprint registration is duplicated across two import surfaces

**Files modified:** `apps/launchpad/app/routes/__init__.py`
**Commit:** 1be1009
**Applied fix:** `app/routes/__init__.py` eagerly imported and re-exported all
four blueprints at package-import time, defeating the deferred per-module import
pattern `create_app()` deliberately uses (so the package stays importable before
route files exist). The re-exports were unused by both production and tests
(`conftest.py` imports the submodule `app.routes.health`, not the re-exported
name). Reduced the file to an empty package marker with a comment explaining the
single-import-surface rationale. Coverage of `app/routes/__init__.py` went from
5 statements to 0; suite remains at 100%.

## Skipped Issues

None — all in-scope findings were fixed. The four Info findings (IN-01 through
IN-04) were out of scope for this `critical_warning` pass. Note: IN-01's
suggested strengthening (weak `assert "up" in body` substring) was partially
addressed opportunistically as part of WR-01's test scoping for the degraded
card, but the specific `test_status_cards_shows_mongo_version_and_service_count`
assertion in IN-01 was left unchanged since it is out of scope.

---

_Fixed: 2026-07-11T03:03:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
