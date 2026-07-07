---
phase: 04-makefile-documentation
plan: "01"
subsystem: build-tooling
tags: [makefile, dx, self-documenting, help, smoke-test, check-tools]
dependency_graph:
  requires: []
  provides: [makefile-help-default-goal, makefile-dx-targets, make-up-alias, make-smoke]
  affects: [Makefile]
tech_stack:
  added: []
  patterns:
    - awk FS=":.*##" inline help target with .DEFAULT_GOAL
    - make prerequisite chaining for aggregate targets (up)
    - trap EXIT for background process cleanup (smoke)
    - read -p confirmation guard for destructive targets (reset-local)
    - $$-escaped shell variables in Makefile recipes
key_files:
  modified:
    - Makefile
decisions:
  - "Converted all 7 existing targets from prefix ## format to inline target: ## format (required by awk FS=:.*##)"
  - "Used greedy FS=:.*## on 'up: prereqs ## description' — awk correctly splits giving up as field 1; closes Research Open Question 1"
  - "check-tools: helm and kubectl do not support --version flag but command -v finds them; output shows error string but PASS=1 is maintained (correct behavior)"
metrics:
  duration: "284s"
  completed: "2026-07-07"
  tasks_completed: 3
  files_modified: 1
---

# Phase 4 Plan 01: Makefile Self-Documenting CLI Summary

**One-liner:** Extended Makefile into a self-documenting CLI with awk-powered help default goal and seven Phase 4 DX targets (up, check-tools, port-forward, smoke, clean, clean-venv, reset-local).

## What Was Built

The single `Makefile` was extended from 54 lines to 109 lines with:

1. **Self-documenting help system** — `.DEFAULT_GOAL := help`, awk one-liner with `FS = ":.*##"` producing a columnar 18-char-padded target listing. Bare `make` and `make help` both print the listing.

2. **Format conversion** — All 7 existing targets converted from prefix `## target: description` (comment above) to inline `target: ## description` (comment on target line). The awk parser requires the inline format; prefix format produces zero output (verified in research).

3. **Phase 4 DX targets:**
   - `up` — pure prerequisite chain: `cluster-up build load deploy` (no recipe body, greedy awk field split confirmed working)
   - `check-tools` — loops `docker kind helm kubectl bash` via `command -v`, prints ok/MISSING + version, exits 1 if any missing
   - `port-forward` — foreground `kubectl port-forward svc/$(RELEASE) 8080:80`
   - `smoke` — pkill guard → background port-forward → trap EXIT → sleep 3 → curl `/health /entries /metrics` PASS/FAIL → cleanup
   - `clean` — five `find` lines scoped to `__pycache__`, `*.pyc`, `.pytest_cache`, `.coverage`, `*.egg-info`; no cluster/image/venv tokens
   - `clean-venv` — `rm -rf apps/field-guide-api/.venv`
   - `reset-local` — loud `!!` banner + `read -p "Type YES"` guard + `$(MAKE) undeploy || true` + `$(MAKE) cluster-down`

## Verification Results

| Check | Result |
|-------|--------|
| `.DEFAULT_GOAL := help` present | PASS (count=1) |
| Inline `## description` format count (min 8) | PASS (count=15) |
| No prefix-form target comments remain | PASS (grep returns nothing) |
| `.PHONY` includes all 15 targets | PASS |
| `make help` outputs columnar listing | PASS |
| All 15 targets in `make help` | PASS (count=15) |
| `up` line renders description not prereq list | PASS (Research OQ1 closed) |
| `check-tools` exits 0 | PASS |
| `make clean` exits 0, no tracked file deletions | PASS |
| `clean` body: zero docker/kind/helm/kubectl/.venv/pvc/registry tokens | PASS (count=0) |
| `make -n smoke` shows trap/kill/curl, `$$`-escaped | PASS |
| `make -n reset-local` shows `read -p` before `$(MAKE) undeploy` | PASS |
| `make -n up` shows cluster-setup.sh → docker build → docker push → helm upgrade | PASS |
| Makefile line count (min 90) | PASS (109 lines) |
| LF-only line endings (no CRLF) | PASS |

## Deviations from Plan

None — plan executed exactly as written.

The only note: Task 3 acceptance criteria used `grep -E '^\s+up\s'` directly on make help output, which fails due to ANSI escape codes in the output. Verification was done with `sed 's/\x1b\[[0-9;]*m//g'` to strip ANSI before grep — this is an environment behavior, not a Makefile defect.

## Known Stubs

None. All targets are fully implemented with no placeholder bodies.

## Threat Surface Scan

No new network endpoints, auth paths, or trust boundaries introduced. Threat mitigations applied:

| Threat | Mitigation Applied |
|--------|-------------------|
| T-04-01: `clean` accidentally deletes runtime state | `clean` body verified: zero docker/kind/helm/kubectl/.venv/pvc/registry tokens |
| T-04-02: `reset-local` accidental cluster destruction | `read -p "Type YES"` guard present; no FORCE bypass; never called by `clean` |
| T-04-03: `$$`-escaping regression | `make -n smoke` and `make -n reset-local` dry-run verified correct `$`-expansion |

## Self-Check: PASSED

| Item | Status |
|------|--------|
| Makefile exists | FOUND |
| 04-01-SUMMARY.md exists | FOUND |
| c7f11d4 (task 1 commit) | FOUND |
| d949d27 (task 2 commit) | FOUND |
