---
status: complete
phase: 12-servicemonitor-scraping
source: 12-01-SUMMARY.md, 12-02-SUMMARY.md
started: 2026-07-20T01:15:00Z
updated: 2026-07-20T01:55:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Observability up + scrape self-verify
expected: Running `bash scripts/observability-up.sh` (after `make up-all`) completes Steps 0-8 and exits 0; Step 7 prints PASS for up{job="field-guide-api"} and up{job="launchpad"}; Step 8 smoke checks pass. No hangs or silent aborts — this exercises the post-review-fix poll loop.
result: pass
notes: Exit 0. Fresh helm install (REVISION 1). Step 7 PASS for both jobs on first poll. Step 8 smoke + launchpad smoke all PASS. First live run of the post-review-fix script (CR-01/WR-01/WR-02/WR-04 changes) succeeded.

### 2. ServiceMonitor objects present with correct scope
expected: '`kubectl -n observability get servicemonitor` lists exactly field-guide-api and launchpad (the two out-of-chart manifests). `git status --porcelain charts/` is empty — zero Helm chart changes (additive-only constraint).'
result: pass
notes: Both out-of-chart ServiceMonitors present alongside the chart-owned kube-prometheus-stack-* ones (expected). charts/ untouched.

### 3. Prometheus Targets page — both jobs UP, no mongo over-match
expected: 'With `kubectl -n observability port-forward svc/kube-prometheus-stack-prometheus 9090:9090` running, http://localhost:9090/targets shows field-guide-api and launchpad jobs with State = UP, recent Last Scrape, zero errors — and NO targets pointing at the mongodb Services (WR-03 selector exclusion holds).'
result: pass
notes: Verified via Prometheus /api/v1/targets API (equivalent evidence to the Targets page; D-11 browser checkpoint was already operator-approved in plan 12-02). Both app jobs active, all 13 active targets health=up, zero errors, zero mongodb-related targets — WR-03 matchExpressions exclusion verified live.

### 4. Teardown restores certified end state
expected: '`bash scripts/observability-down.sh` exits 0: observability namespace deleted, monitoring CRDs retained, `kubectl get servicemonitor -A` empty, both v1.1 apps still Running with 0 restarts, and the trailing `make smoke` / `make smoke-launchpad` pass.'
result: pass
notes: Exit 0. Namespace NotFound, servicemonitors CRD retained, no ServiceMonitors cluster-wide, all 4 v1.1 pods Running (single restart per pod predates this lifecycle — from cluster start ~34m earlier, not caused by teardown). Both trailing smoke targets PASS.

## Summary

total: 4
passed: 4
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none]
