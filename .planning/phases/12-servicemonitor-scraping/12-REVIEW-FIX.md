---
phase: 12-servicemonitor-scraping
fixed_at: 2026-07-20T01:08:00Z
review_path: .planning/phases/12-servicemonitor-scraping/12-REVIEW.md
iteration: 1
findings_in_scope: 5
fixed: 5
skipped: 0
status: all_fixed
---

# Phase 12: Code Review Fix Report

**Fixed at:** 2026-07-20T01:08:00Z
**Source review:** .planning/phases/12-servicemonitor-scraping/12-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 5 (1 Critical, 4 Warning; Info findings IN-01/IN-02 excluded by fix_scope=critical_warning)
- Fixed: 5
- Skipped: 0

## Fixed Issues

### CR-01: Step 7 curl poll aborts the script on a single transient failure (errexit) and can hang indefinitely (no timeout)

**Files modified:** `scripts/observability-up.sh`
**Commit:** bca6cd5
**Applied fix:** Guarded the Step 7 curl command substitution with `|| true` so a transient connection-refused (port-forward warm-up/drop) no longer kills the script under `set -o errexit`, restoring the poll-until-deadline semantics. Added `--max-time 10` so a half-open connection through the Docker Desktop proxy cannot block past the 150s deadline. Added a comment mirroring the Phase 11 guard pattern (Step 3, lines 110-111).

### WR-01: pkill stale-port-forward cleanup pattern can never match the actual command line

**Files modified:** `scripts/observability-up.sh`
**Commit:** fe37525
**Applied fix:** Replaced the dead pattern `"kubectl port-forward -n observability svc/..."` (never matches because the real command line is `kubectl --context=kind-kind port-forward ...`) with `"port-forward.*svc/kube-prometheus-stack-prometheus"`, which matches regardless of flag position. Added a comment explaining why the pattern is anchored this way.

### WR-02: Port-forward liveness never checked — bind failure or death burns the full 150s with an empty diagnostic

**Files modified:** `scripts/observability-up.sh`
**Commit:** d905460
**Applied fix:** After the `sleep 3` synchronization, added a `kill -0 "${PF_PID}"` liveness check that fails fast with a targeted message ("is port 9090 already in use?") instead of burning the full deadline and reporting an empty `Last response:`.

### WR-03: ServiceMonitor selectors also match the MongoDB Services (latent over-match)

**Files modified:** `infra/observability/servicemonitor-field-guide-api.yaml`, `infra/observability/servicemonitor-launchpad.yaml`
**Commit:** 143ac5e
**Applied fix:** Added `matchExpressions: [{key: app.kubernetes.io/component, operator: DoesNotExist}]` to both ServiceMonitor selectors. Verified against the charts before applying: both MongoDB Services carry `app.kubernetes.io/component: mongodb` (`charts/*/templates/mongodb/service.yaml:12`) while neither app Service sets a component label (only pod templates do), so the app Services remain selected and the MongoDB Services are excluded regardless of future port naming. No chart files touched (additive-only constraint honored). Both manifests validated with `kubectl apply --dry-run=client`.

### WR-04: Shared 150s deadline across both jobs — second job can spuriously fail, and the error message misstates the budget

**Files modified:** `scripts/observability-up.sh`
**Commit:** f111373
**Applied fix:** Moved the `DEADLINE` computation inside the `for job in $VERIFY_JOBS` loop so each job gets its own 150s budget, making the "did not reach 1 within 150s" error message accurate per job. Added a comment documenting the per-job budget rationale.

## Skipped Issues

None — all in-scope findings were fixed.

---

_Fixed: 2026-07-20T01:08:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
