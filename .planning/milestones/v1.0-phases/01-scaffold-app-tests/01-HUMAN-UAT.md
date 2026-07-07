---
status: resolved
phase: 01-scaffold-app-tests
source: [01-VERIFICATION.md]
started: 2026-07-05T00:15:00Z
updated: 2026-07-05T01:30:00Z
---

## Current Test

[complete]

## Tests

### 1. `make test` portability on a cold shell

expected: Running `make test` in a fresh Git Bash / WSL2 session installs deps and runs the suite green via the intended developer command.
result: passed — WR-05 fixed (commit ae070b7): Makefile now creates/reuses `.venv` with overridable `PYTHON ?=`. Verified on this host: `make test PYTHON="py -3.12"` → 32 passed, 100% coverage, exit 0.

### 2. CR-01 / CR-02 — POST /entries edge-case failures

expected: Decide whether these are an acceptable Phase 1 known gap or must be fixed before Phase 3 containerization.
result: passed — user chose "fix now": CR-01 fixed (commit 737fba2, non-object body → 400) and CR-02 fixed (commit 4847d43, tags validated as list[str] → 400). Regression tests added; "never 500" invariant holds.

## Summary

total: 2
passed: 2
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps
