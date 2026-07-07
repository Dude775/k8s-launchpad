---
phase: 02-cluster-infrastructure
fixed_at: 2026-07-05T13:05:00Z
review_path: .planning/phases/02-cluster-infrastructure/02-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 02: Code Review Fix Report

**Fixed at:** 2026-07-05T13:05:00Z
**Source review:** .planning/phases/02-cluster-infrastructure/02-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (fix_scope: critical_warning — CR-01, WR-01, WR-02, WR-03)
- Fixed: 4
- Skipped: 0

## Fixed Issues

### CR-01: kubectl commands are not pinned to the kind context — can mutate/delete resources on the wrong cluster

**Files modified:** `scripts/cluster-setup.sh`
**Commit:** 3a561a9
**Applied fix:** Added `KCTX='--context=kind-kind'` near the top of the script (with a comment explaining the idempotent re-run hazard) and applied `${KCTX}` to all five kubectl invocations: the Step 5 ConfigMap `apply`, both `delete pod registry-verify` calls, `run registry-verify`, and the `wait` on pod phase. Per-command `--context` was chosen over `kubectl config use-context` so the user's global kubectl state is never mutated, exactly as the review recommended.

### WR-01: Step 1 idempotency breaks when the registry container exists but is stopped

**Files modified:** `scripts/cluster-setup.sh`
**Commit:** 29bef32
**Applied fix:** Inside the `.State.Running != 'true'` branch, added an inner `docker inspect` existence check: if the container exists but is stopped, run `docker start "${reg_name}"` instead of `docker run` (which would fail on the name conflict and abort under errexit). The original multi-line `docker run` invocation, loopback-only port binding (`127.0.0.1:5001`), and the "already running — skipping" path are preserved unchanged.

### WR-02: Prerequisite gate checks only `kind`; `docker` and `kubectl` are equally hard dependencies

**Files modified:** `scripts/cluster-setup.sh`
**Commit:** 40c8426
**Applied fix:** Extended the prerequisite gate: after the existing kind check (kept intact to preserve its winget/download install hints), added a `for tool in docker kubectl` loop failing fast with a clear PATH error, plus a `docker info` check that fails with "Docker daemon is not running." before any work happens. Adapted from the review's suggestion — the review's generic loop would have dropped the kind-specific install message, so kind's dedicated check was retained.

### WR-03: Step 6 verification failure leaves the pod behind and produces no diagnostics

**Files modified:** `scripts/cluster-setup.sh`
**Commit:** abdfc4b
**Applied fix:** Wrapped the `kubectl wait` in an `if !` block: on timeout it prints an explicit error, dumps the pod's Events section via `kubectl describe pod registry-verify | sed -n '/Events:/,$p'`, deletes the leftover pod with `--ignore-not-found`, and exits 1. The success path still deletes the pod as before. All kubectl calls in the block use `${KCTX}` (builds on CR-01).

## Verification

- Tier 1: re-read every modified section; fix text present, surrounding code intact.
- Tier 2: `bash -n scripts/cluster-setup.sh` passed after each of the four fixes.
- Line endings confirmed LF-only (no CRLF introduced); no docker/kind/kubectl commands were executed during fixing.
- Observable behavior preserved: idempotency guards, loopback-only registry binding, `errexit` without `pipefail` (IN-01 comment left as-is — Info scope), `export MSYS_NO_PATHCONV=1`.

---

_Fixed: 2026-07-05T13:05:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
