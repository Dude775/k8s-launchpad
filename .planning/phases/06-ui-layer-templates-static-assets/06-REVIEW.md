---
phase: 06-ui-layer-templates-static-assets
reviewed: 2026-07-11T00:00:00Z
depth: standard
files_reviewed: 14
files_reviewed_list:
  - apps/launchpad/app/__init__.py
  - apps/launchpad/app/routes/__init__.py
  - apps/launchpad/app/routes/pages.py
  - apps/launchpad/app/routes/partials.py
  - apps/launchpad/app/static/style.css
  - apps/launchpad/app/templates/base.html
  - apps/launchpad/app/templates/catalog.html
  - apps/launchpad/app/templates/diagnostics.html
  - apps/launchpad/app/templates/feed.html
  - apps/launchpad/app/templates/index.html
  - apps/launchpad/app/templates/partials/status_cards.html
  - apps/launchpad/tests/test_pages.py
  - apps/launchpad/tests/test_partials.py
  - apps/launchpad/tests/test_static_assets.py
findings:
  critical: 0
  warning: 4
  info: 3
  total: 7
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-07-11
**Depth:** standard
**Files Reviewed:** 14
**Status:** issues_found

## Summary

Phase 6 delivers the UI shell: four page routes, one htmx partial route, a shared
`base.html`, per-page templates, vendored Pico + htmx assets, and companion CSS.
The security-relevant contracts hold up:

- **Autoescaping intact** — no `| safe`, no `{% autoescape false %}`, no
  `Markup()` anywhere in the templates. All interpolated values (`request.endpoint`,
  `url_for(...)`) are auto-escaped by Jinja2.
- **Offline UI-05 guarantee holds** — every asset is referenced via
  `url_for('static', ...)`. The only `http(s)://` strings in the vendored
  `pico.min.css` are the `http://www.w3.org/2000/svg` SVG namespace URIs inside
  inlined data-URI backgrounds (not network fetches) and a `https://picocss.com`
  attribution comment. Neither triggers a runtime request.
- **`partials/status_cards.html` is a true fragment** — no `{% extends "base.html" %}`,
  returns a bare `<article>`; the partial route's degraded stub returns 200 with
  `status="unknown"` and never 500.

No Critical findings. The defects below are correctness/robustness gaps: several
layout classes referenced in the templates have no styling anywhere (unstyled UI),
and two tests use assertions weak enough to pass while a real regression slips through.

## Warnings

### WR-01: Layout and status-card CSS classes are referenced but never defined

**File:** `apps/launchpad/app/templates/base.html:12,13,29,30`, `apps/launchpad/app/templates/index.html:4,10`, `apps/launchpad/app/templates/partials/status_cards.html:2`, `apps/launchpad/app/static/style.css`
**Issue:** The templates use the classes `.layout`, `.main`, `.topbar`, `.status-card`,
and `.status-card--unknown` for the core dashboard layout. `style.css` only defines
rules for `.sidebar a`, `h1/h2/h3`, and Pico custom properties — none of these five
classes are defined there, and they are not Pico built-in classes either (Pico ships
`container`, `grid`, etc., not `layout`/`main`/`topbar`/`status-card`). As a result the
sidebar-vs-main split, the topbar, and the status-card visual treatment (including the
distinct "unknown/degraded" state that UI-03 calls for) render completely unstyled —
a single stacked column with no visual hierarchy. The tests only assert on markup
substrings, so this ships green while the actual rendered dashboard is broken.
**Fix:** Add the missing layout/card rules to `style.css`, e.g.:
```css
.layout { display: flex; min-height: 100vh; }
.sidebar { flex: 0 0 220px; padding: 1rem; }
.main { flex: 1; }
.topbar { padding: .75rem 1rem; border-bottom: 1px solid var(--pico-muted-border-color); }
.status-card { padding: 1rem; border: 1px solid var(--pico-muted-border-color); border-radius: var(--pico-border-radius); }
.status-card--unknown { border-color: var(--pico-del-color); }
```
Adjust to match the UI-SPEC values; the point is that every class emitted by a
template must resolve to a rule.

### WR-02: `test_no_cdn_references` assertions are too narrow to catch a real CDN regression

**File:** `apps/launchpad/tests/test_static_assets.py:22-26`
**Issue:** The UI-05 no-CDN guard checks only four hardcoded substrings:
`https://unpkg.com`, `https://cdn.`, `src="http://`, `href="http://`. This misses
the realistic regression vectors: a `https://cdn.jsdelivr.net` link (matches
`https://cdn.` — OK) but also `https://esm.sh`, `https://fonts.googleapis.com`,
`https://ajax.googleapis.com`, `https://code.jquery.com`, or a protocol-relative
`//unpkg.com/...` reference would all pass the test. It also only checks `http://`
for `src=`/`href=`, so any `https://` CDN on a domain other than `cdn.*`/`unpkg.com`
sails through. The test gives false confidence that the offline contract is enforced.
**Fix:** Assert on the structural invariant instead of a denylist — every asset URL
must be same-origin/`/static/`:
```python
import re
# no absolute external URLs in href/src at all
assert not re.search(r'(?:href|src)\s*=\s*["\'](?:https?:)?//', body), path
# every stylesheet/script points at /static/
for m in re.finditer(r'(?:href|src)\s*=\s*["\']([^"\']+)["\']', body):
    url = m.group(1)
    assert url.startswith("/static/") or url.startswith("#"), f"{path}: {url}"
```

### WR-03: `test_active_nav_per_route` does not prove the *correct* link is active

**File:** `apps/launchpad/tests/test_pages.py:29-33`
**Issue:** The test requests `/catalog` and asserts only that `aria-current="page"`
appears somewhere in the body. Because `base.html` emits `aria-current="page"` on
whichever nav item matches `request.endpoint`, the assertion passes for *any* route
that highlights *any* link. A bug that highlighted the Dashboard link on the
`/catalog` page (e.g. a wrong endpoint comparison) would still pass. UI-02 requires
the active link to match the current page.
**Fix:** Assert the marker lands on the Catalog link specifically:
```python
resp = client.get("/catalog")
body = resp.get_data(as_text=True)
assert re.search(r'href="/catalog"[^>]*aria-current="page"', body), body
# and that a non-current link is NOT marked
assert not re.search(r'href="/"[^>]*aria-current="page"', body)
```

### WR-04: No test asserts the offline contract for the htmx partial route

**File:** `apps/launchpad/tests/test_static_assets.py:18-26`, `apps/launchpad/tests/test_partials.py`
**Issue:** `test_no_cdn_references` iterates only the four page routes
(`/`, `/catalog`, `/diagnostics`, `/feed`). The htmx-swapped fragment at
`/partials/status-cards` — which in Phase 7 will render real per-metric cards that
could plausibly introduce an external icon/asset URL — is never checked against the
no-CDN contract, and `test_partials.py` only checks the degraded string plus absence
of `<html`. The one route whose content is most likely to grow untrusted/dynamic
markup has the weakest offline coverage.
**Fix:** Add `/partials/status-cards` to the no-CDN loop (or add a dedicated
partial-route assertion), so the UI-05 guarantee is enforced on the fragment too.

## Info

### IN-01: `app/routes/__init__.py` re-exports duplicate the deferred imports in the factory

**File:** `apps/launchpad/app/routes/__init__.py:3-7`, `apps/launchpad/app/__init__.py:50-52`
**Issue:** `routes/__init__.py` eagerly imports `health_bp`, `pages_bp`, and
`partials_bp` at package-import time, while `create_app()` deliberately defers the
same imports (per the module docstring: "so this module is importable before the
route files exist"). The eager package `__init__` partially defeats that intent — any
`import app.routes` (or the `from app.routes import ...` re-export) pulls all three
route modules eagerly. It is harmless today because all three files exist, but it is
an inconsistency worth noting against the stated deferral rationale.
**Fix:** Either drop the eager re-exports from `routes/__init__.py` (callers already
import from the concrete submodules) or accept the eager import and simplify the
factory to `from app.routes import health_bp, pages_bp, partials_bp`. Pick one
convention.

### IN-02: `status_cards.html` `{% else %}` branch is an empty placeholder that renders nothing

**File:** `apps/launchpad/app/templates/partials/status_cards.html:6-8`
**Issue:** When `status != "unknown"` the template renders only a Jinja comment and
no markup, so a future caller passing any non-`"unknown"` status (before Phase 7
fills the branch) would swap an empty fragment into `#status-cards`, silently
blanking the section with no fallback. This is intentional Phase-6 scaffolding, but
the empty branch is a latent trap for the Phase 7 hand-off.
**Fix:** Leave a visible placeholder (or an explicit `{% raise %}`-style guard is not
available in stock Jinja, so at minimum) render a neutral card in the `else` branch
until Phase 7 populates it, so an unexpected status never yields a blank swap.

### IN-03: `index.html` omits an explicit `{% block title %}`

**File:** `apps/launchpad/app/templates/index.html`
**Issue:** Unlike `catalog.html`, `diagnostics.html`, and `feed.html`, the landing
page does not override `{% block title %}`, so it falls back to the base default
`"Dashboard"`. That happens to read correctly for the landing page, but it relies on
the default rather than declaring intent, making the title coupling implicit.
**Fix:** Add `{% block title %}Dashboard{% endblock %}` to `index.html` for symmetry
and to decouple the page title from the base default.

---

_Reviewed: 2026-07-11_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
