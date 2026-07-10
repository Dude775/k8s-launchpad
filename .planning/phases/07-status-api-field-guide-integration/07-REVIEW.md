---
phase: 07-status-api-field-guide-integration
reviewed: 2026-07-10T23:38:58Z
depth: standard
files_reviewed: 19
files_reviewed_list:
  - apps/launchpad/.env.example
  - apps/launchpad/app/__init__.py
  - apps/launchpad/app/config.py
  - apps/launchpad/app/extensions.py
  - apps/launchpad/app/routes/__init__.py
  - apps/launchpad/app/routes/health.py
  - apps/launchpad/app/routes/partials.py
  - apps/launchpad/app/routes/status.py
  - apps/launchpad/app/status.py
  - apps/launchpad/app/templates/partials/status_cards.html
  - apps/launchpad/app/templates/status_full_page.html
  - apps/launchpad/requirements.txt
  - apps/launchpad/requirements-dev.txt
  - apps/launchpad/tests/conftest.py
  - apps/launchpad/tests/test_factory.py
  - apps/launchpad/tests/test_health.py
  - apps/launchpad/tests/test_metrics.py
  - apps/launchpad/tests/test_partials.py
  - apps/launchpad/tests/test_status.py
findings:
  critical: 0
  warning: 4
  info: 4
  total: 8
status: issues_found
---

# Phase 07: Code Review Report

**Reviewed:** 2026-07-10T23:38:58Z
**Depth:** standard
**Files Reviewed:** 19
**Status:** issues_found

## Summary

Phase 7 wires a real `get_platform_status()` aggregation helper shared by
`GET /api/status` (JSON) and `GET /partials/status-cards` (HTML), plus a
MongoDB-only `/health` readiness probe. The implementation is disciplined:
exception isolation is thorough, the outbound field-guide call carries a
mandatory timeout, `/health` correctly avoids the cross-service dependency,
and Jinja2 autoescaping neutralizes the env-sourced `app_version` value. The
full suite (37 tests) passes at 100% line coverage, and I empirically
confirmed the `_metrics_preview` registry-summation logic is correct
(`family.name == "flask_http_request"`, `sample.name ==
"flask_http_request_total"` match the live prometheus_client output).

No BLOCKER-tier defects were found. However, the adversarial pass surfaced a
real user-visible defect that the tests structurally cannot catch: the status
cards emit `--ok` / `--degraded` / `--unknown` modifier classes that have **no
corresponding CSS**, so the color-coded health signal — the entire point of
the cards — does not render. Several test assertions are also too weak to
detect regressions they claim to guard, and there are naming/semantic issues
worth fixing before Phase 8 builds on this contract.

## Warnings

### WR-01: Status-card color modifiers have no CSS — degraded state is invisible

**File:** `apps/launchpad/app/templates/partials/status_cards.html:1,5,9,13` (and `index.html:10`)
**Issue:** Every card is rendered with a state modifier class —
`status-card--ok`, `status-card--degraded`, `status-card--unknown`. These
classes are the sole mechanism by which a degraded platform is visually
distinguished from a healthy one. `app/static/style.css` defines rules for
`#status-cards` but contains **no** `.status-card--ok`, `.status-card--degraded`,
or `.status-card--unknown` rules (confirmed by grep across the stylesheet).
The computed modifier is therefore inert: a MongoDB outage or an unreachable
field-guide-api produces the same visual output as a healthy platform. The
templates (in scope) are emitting a contract that the stylesheet never
fulfills. Tests pass because `test_partials.py` asserts only that the class
*string* appears in the response body, never that it has any rendered effect.
**Fix:** Add the missing modifier rules to `app/static/style.css`, e.g.:
```css
.status-card--ok      { border-left: 4px solid var(--pico-color-green-500, #2e7d32); }
.status-card--degraded{ border-left: 4px solid var(--pico-color-red-500, #c62828); }
.status-card--unknown { border-left: 4px solid var(--pico-muted-border-color, #999); }
```
(style.css is outside this phase's file list but the defect originates in the
in-scope templates; either add the CSS or drop the modifier classes so they
do not imply behavior that does not exist.)

### WR-02: "Version" and "Registered Services" cards colored by unrelated mongo health

**File:** `apps/launchpad/app/templates/partials/status_cards.html:9,13`
**Issue:** The Version card and the Registered Services card both compute their
state modifier from `status.api_health` (`'ok' if status.api_health == 'ok'
else 'degraded'`). `api_health` is derived exclusively from `mongo_status`
(see `status.py:92`). Consequently a MongoDB outage paints the *Version* card
red, implying the application version is somehow "degraded," and paints the
*Registered Services* card red even though a count of 0 is the normal,
expected Phase-7 state. This couples two informational cards to an unrelated
health dimension and will mislead an operator reading the dashboard.
**Fix:** Render informational cards in a neutral state rather than reusing
`api_health`. For example, give Version/Services a static `status-card--info`
(or `--unknown`) modifier, or drop the modifier entirely for cards that do not
represent a health signal.

### WR-03: `field_guide_reachable` conflates network reachability with app health

**File:** `apps/launchpad/app/status.py:77-78`
**Issue:** `field_guide_reachable = resp.status_code == 200`. If
field-guide-api is fully reachable over the network but returns a non-200
(e.g. its own readiness returns 503 because *its* MongoDB is down), this
platform reports `field_guide_reachable: False` and renders "unreachable."
The field name and the card label ("unreachable") assert a network fact, but
the value actually encodes "field-guide-api returned HTTP 200." An operator
debugging a network partition vs. a downstream-dependency failure is given
misleading information. This value feeds the public `/api/status` JSON
contract that Phase 8 will consume, so the semantic should be nailed down now.
**Fix:** Either (a) rename to `field_guide_healthy` to match the actual
semantics, or (b) treat any HTTP response (regardless of status code) as
"reachable" and expose the downstream health separately:
```python
resp = requests.get(f"{base_url}/health", timeout=FIELD_GUIDE_TIMEOUT_SECONDS)
field_guide_reachable = True                     # got an HTTP response at all
field_guide_healthy = resp.status_code == 200
```

### WR-04: Blueprint registration is duplicated across two import surfaces

**File:** `apps/launchpad/app/__init__.py:57-65` and `apps/launchpad/app/routes/__init__.py:3-8`
**Issue:** `app/routes/__init__.py` imports and re-exports all four blueprints
(`health_bp`, `pages_bp`, `partials_bp`, `status_bp`) at package-import time,
while `app/__init__.py` deliberately performs its own *deferred* per-module
imports inside `create_app()` and never uses the `app.routes` re-exports. The
module docstring in `__init__.py` explains the deferred pattern exists so the
package is importable "before the route files exist" — but `app/routes/__init__.py`
eagerly importing every route module defeats that guarantee: any
`from app.routes import X` (or importing the package at all) will fail if a
single route module is missing or has an import error. The two import
surfaces can also silently drift (one lists blueprints the other does not).
The re-export module is currently unused by production code.
**Fix:** Either delete the eager re-exports in `app/routes/__init__.py` (make it
an empty package marker, consistent with the deferred-import rationale), or
have `create_app()` consume `from app.routes import health_bp, ...` and remove
the duplicated per-module imports — pick one import surface, not both.

## Info

### IN-01: Weak substring assertions in partials tests give false confidence

**File:** `apps/launchpad/tests/test_partials.py:46`
**Issue:** `test_status_cards_shows_mongo_version_and_service_count` asserts
`assert "up" in body`. The substring "up" matches far more than the mongo
status value (it is a common fragment). This assertion would pass even if the
mongo card were removed, as long as any "up" appears anywhere in the HTML. The
test's stated purpose ("shows a mongo up/down card") is not actually verified.
**Fix:** Assert on the specific rendered element, e.g. `assert
"status-card--ok" in body` combined with a scoped check like `assert "MongoDB"
in body`, or assert the exact `<p>up</p>` text within the mongo card.

### IN-02: `int(total)` silently truncates fractional counter values

**File:** `apps/launchpad/app/status.py:47`
**Issue:** `return {"http_requests_total": int(total)}` truncates toward zero.
For the `flask_http_request_total` counter this is currently harmless (values
are whole increments), but `int()` on a summed float is a lossy narrowing that
would misreport if any contributing sample were fractional. Low risk given the
metric type, noted for correctness awareness.
**Fix:** Consider `round(total)` if a whole-number preview is desired, or keep
the summed float; document the intent either way.

### IN-03: Docstring references modules not present in this phase's tree

**File:** `apps/launchpad/app/status.py:9-11` and `apps/launchpad/app/__init__.py:13-14`
**Issue:** Docstrings reference `app/k8s.py` ("mirrors app/k8s.py's shape")
and a "future diagnostics route (D-05)". `app/k8s.py` does exist, so these are
accurate today, but the `partials.py` docstring (lines 10-19) carries a long
historical justification of a Phase-6-vs-Phase-7 contract change that will
become stale narrative once Phase 8 lands. Heavy inline phase-archaeology in
docstrings tends to rot.
**Fix:** Trim historical rationale to a one-line pointer to the phase plan;
keep docstrings describing current behavior, not the change history.

### IN-04: `service_count` degraded-vs-empty is indistinguishable in the JSON contract

**File:** `apps/launchpad/app/status.py:82-89`
**Issue:** `service_count` returns `0` both when the services collection is
genuinely empty (the normal Phase-7 state) and when `count_documents({})`
raises and is swallowed by the `except`. A consumer of `/api/status` cannot
tell "no services registered" from "the query failed." Acceptable for Phase 7
per the plan, but Phase 8/9 consumers should be aware the sentinel is
overloaded.
**Fix:** If future phases need to distinguish these, return `None` (or a
separate `services_query_ok` flag) on failure rather than collapsing to `0`.

---

_Reviewed: 2026-07-10T23:38:58Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
