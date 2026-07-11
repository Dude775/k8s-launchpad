---
phase: 08-helm-chart-k8s-diagnostics
plan: 02
subsystem: diagnostics
tags: [flask, kubernetes-client, htmx, jinja2, pytest, rbac]

# Dependency graph
requires:
  - phase: 08-01
    provides: "Helm chart with launchpad ServiceAccount + namespace-scoped Role/RoleBinding (RBAC) that this plan's cluster_state.py reads through"
  - phase: 05
    provides: "app/k8s.py lazy get_k8s_clients() accessor returning (None, None) outside a cluster"
  - phase: 06
    provides: "base.html shell, pages_bp/partials_bp blueprints, status-cards fragment pattern"
  - phase: 07
    provides: "get_platform_status() + /partials/status-cards HX-Request fragment/full-page branch, reused verbatim as the pattern for cluster-state"
provides:
  - "get_cluster_state() never-raises helper with four distinct return shapes (outside-cluster, success, 403-forbidden, unreachable)"
  - "GET /partials/cluster-state route (fragment for htmx, full page otherwise) added to the existing partials_bp blueprint"
  - "GET /diagnostics two-section page: Platform Checks (15s poll, reused) + Cluster State (10s poll, new)"
  - "DIAG-01 and DIAG-02 requirements satisfied"
affects: [09-catalog-crud, 10-makefile-smoke]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Bare never-raises helper (NO Blueprint) with per-branch dict return shapes, mirroring app/status.py"
    - "Module-attribute dependency access (from app import k8s -> k8s.get_k8s_clients()) instead of a from-import, so test fixtures that monkeypatch the module attribute actually reach the caller"
    - "HX-Request fragment-vs-full-page route branch, mirrored byte-for-byte across partials.py routes"

key-files:
  created:
    - apps/launchpad/app/cluster_state.py
    - apps/launchpad/app/templates/partials/cluster_state.html
    - apps/launchpad/app/templates/cluster_state_full_page.html
    - apps/launchpad/tests/test_cluster_state.py
  modified:
    - apps/launchpad/app/routes/partials.py
    - apps/launchpad/app/templates/diagnostics.html
    - apps/launchpad/tests/test_partials.py

key-decisions:
  - "get_cluster_state() catches ApiException before urllib3.exceptions.HTTPError (ApiException is not an HTTPError subclass) so a 403 is never misclassified as unreachable"
  - "Age formatting (_pod_age) is a small internal helper with its own except Exception (formatting-only, never around the K8s network calls) so a malformed/mocked timestamp never crashes the whole helper"
  - "cluster_state_full_page.html mirrors status_full_page.html exactly (separate file, not a diagnostics.html reuse) for template-name symmetry with the status-cards pattern"

patterns-established:
  - "Any future read-only K8s aggregation helper should follow cluster_state.py's shape: module-level timeout constant, module-attribute import of app.k8s, ApiException-then-HTTPError catch order, dict-only return (no raised exceptions)"

requirements-completed: [DIAG-01, DIAG-02]

# Metrics
duration: 25min
completed: 2026-07-11
---

# Phase 08 Plan 02: Cluster State Diagnostics Summary

**Read-only Kubernetes pods/deployments panel on /diagnostics via a never-raises get_cluster_state() helper, degrading across outside-cluster/403/unreachable states without ever 500ing, at 100% test coverage.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-07-11T23:03:00Z
- **Completed:** 2026-07-11T23:28:15Z
- **Tasks:** 3
- **Files modified:** 7 (4 created, 3 modified)

## Accomplishments
- `get_cluster_state()` reads pods/deployments scoped to `POD_NAMESPACE` via the in-cluster ServiceAccount, with `_request_timeout=5` on every list call
- Four distinct, never-conflated return states: outside-cluster (muted), success (mapped tables), 403 (access-denied), unreachable (timeout/other API error)
- `/partials/cluster-state` route added to the existing `partials_bp`, mirroring the `status_cards` HX-Request fragment/full-page split byte-for-byte
- `/diagnostics` now renders two stacked sections — Platform Checks (reused, 15s poll) and Cluster State (new, 10s poll with visibility guard)
- Test suite at 52 tests / 100% coverage, including a source-grep gate enforcing `_request_timeout=` on every `list_namespaced_*` call and a regression guard on the module-attribute import discipline

## Task Commits

Each task was committed atomically:

1. **Task 1: Create app/cluster_state.py — get_cluster_state() with three exception branches** - `6191ebd` (feat)
2. **Task 2: Add /partials/cluster-state route + templates + two-section diagnostics.html** - `ac41db1` (feat)
3. **Task 3: Branch tests for cluster_state + partial route tests at 100% coverage** - `263ad19` (test)

**Plan metadata:** (this commit, pending)

## Files Created/Modified
- `apps/launchpad/app/cluster_state.py` - `get_cluster_state()` never-raises helper; `_pod_age`/`_map_pod`/`_map_deployment` internal mappers
- `apps/launchpad/app/routes/partials.py` - added `cluster_state()` route to `partials_bp`
- `apps/launchpad/app/templates/partials/cluster_state.html` - fragment: muted/error panels + pods/deployments tables
- `apps/launchpad/app/templates/cluster_state_full_page.html` - full-page wrapper mirroring `status_full_page.html`
- `apps/launchpad/app/templates/diagnostics.html` - two-section page (Platform Checks + Cluster State, 10s poll)
- `apps/launchpad/tests/test_cluster_state.py` - branch-per-outcome tests + `_pod_age` edge cases + timeout source-grep gate
- `apps/launchpad/tests/test_partials.py` - fragment/full-page tests for `/partials/cluster-state`

## Decisions Made
- Followed the plan's module-attribute import discipline (`from app import k8s`) exactly as specified — this was the plan-check BLOCKER 3 regression guard, verified both by source-grep assertion and by the fixture-reachability of the actual passing tests.
- Kept `ApiException` and `urllib3.exceptions.HTTPError` as two separate `except` clauses in that order (not combined), per the plan's explicit ordering requirement.

## Deviations from Plan

None - plan executed exactly as written. The 100% coverage gate required a few extra unit tests beyond what the plan's `<action>` text enumerated (dedicated `_pod_age` branch tests for hours/days/future-clock-skew/malformed-timestamp), but these are direct fulfillment of the plan's explicit instruction to reach `--cov-fail-under=100` on "the `or []` / `or 0` coalesce lines and the age-derivation helper" — not a scope change.

## Issues Encountered
- Initial verification command for Task 1 failed because the module's own docstring contained the literal negative-example string `from app.k8s import get_k8s_clients` (explaining what NOT to do) — this false-positived the source-grep regression check. Reworded the docstring to describe the anti-pattern without containing the literal import string; verification then passed cleanly. No functional code change.
- Coverage gate initially reported 97-99% due to untested branches in `_pod_age` (days/hours/negative-clamp/exception paths) — added five dedicated `_pod_age` unit tests to close every branch, reaching 100%.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- DIAG-01 and DIAG-02 both satisfied; `/diagnostics` is feature-complete for this milestone's diagnostics scope.
- Phase 08-01's RBAC (ServiceAccount/Role/RoleBinding) is the runtime dependency this plan reads through in-cluster — not re-verified live here (that's Phase 08-01's/Phase 10's smoke-test responsibility), but the namespace-scoped `list_namespaced_*` calls match the Role's granted verbs.
- No blockers for Phase 09 (catalog CRUD) or Phase 10 (Makefile smoke targets).

---
*Phase: 08-helm-chart-k8s-diagnostics*
*Completed: 2026-07-11*

## Self-Check: PASSED

All 7 created/modified source files verified present on disk; all 4 task/summary commit hashes (6191ebd, ac41db1, 263ad19, 77a495d) verified present in git log.
