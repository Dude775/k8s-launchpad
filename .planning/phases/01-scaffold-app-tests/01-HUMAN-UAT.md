---
status: partial
phase: 01-scaffold-app-tests
source: [01-VERIFICATION.md]
started: 2026-07-05T00:15:00Z
updated: 2026-07-05T00:15:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. `make test` portability on a cold shell

expected: Running `make test` in a fresh Git Bash / WSL2 session installs deps and runs the 28-test suite green via the intended developer command. Currently `Makefile:10` uses bare `pip`/`pytest` with no venv (REVIEW WR-05); on this host bare `pip` resolves to a broken Python 3.7.4. Either confirm `make test` works in your intended shell, or apply the WR-05 venv fix.
result: [pending]

### 2. CR-01 / CR-02 — POST /entries edge-case failures

expected: Decide whether these are an acceptable Phase 1 known gap or must be fixed before Phase 3 containerization. Confirmed behavior: non-dict JSON body (`[1,2]`, `"str"`) → HTTP 500; `tags: 5` → HTTP 500; `tags: "abc"` → silently stored as `["a","b","c"]` (data corruption). The code's own invariant (`entries.py:18-22`) says malformed input must never 500.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
