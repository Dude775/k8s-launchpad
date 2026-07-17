---
phase: 12-servicemonitor-scraping
reviewed: 2026-07-17T22:12:48Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - infra/observability/servicemonitor-field-guide-api.yaml
  - infra/observability/servicemonitor-launchpad.yaml
  - scripts/observability-up.sh
findings:
  critical: 1
  warning: 4
  info: 2
  total: 7
status: issues_found
---

# Phase 12: Code Review Report

**Reviewed:** 2026-07-17T22:12:48Z
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Reviewed the two out-of-chart ServiceMonitor manifests and the Phase 12 extension of `scripts/observability-up.sh` (Steps 4-7). Cross-references were verified against the charts: both app Services carry `app.kubernetes.io/name: field-guide-api` / `launchpad` labels with a port named `http`; both apps register `/metrics` via prometheus-flask-exporter; `infra/observability/values-trimmed.yaml:73` does set `serviceMonitorSelectorNilUsesHelmValues: false` as the manifests' comments claim; release names (`Makefile:12,18`) collapse fullnames so the Service names match the `job` labels Step 6/7 depend on. The kubectl-wait constraint is honored (all waits are polling GETs), no Helm chart files were touched, and `observability-down.sh` is unchanged.

One BLOCKER: the Step 7 poll loop is not actually a retry loop under `set -o errexit` — a single failed `curl` (connection refused while the port-forward warms up or after it drops, which `kubectl port-forward` is known to do) silently aborts the whole script with no diagnostics, defeating the poll-until-deadline design. The Phase 11 authors guarded every fallible poll with `|| true` (lines 107-110); the Phase 12 curl at line 173 is missing the same guard. Additional warnings cover a dead `pkill` cleanup pattern, an unbounded curl over the documented hang-prone Docker Desktop proxy path, an undetected port-forward bind failure, a latent ServiceMonitor selector over-match onto the MongoDB Services, and a shared 150s deadline that can spuriously fail the second job.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: Step 7 curl poll aborts the script on a single transient failure (errexit) and can hang indefinitely (no timeout)

**File:** `scripts/observability-up.sh:173`
**Issue:** The script runs under `set -o errexit` (line 11). Line 173 is in the *body* of `while true; do ... done`, which is NOT exempt from errexit (only `if`/`while` *conditions* are). A variable assignment from command substitution propagates the substitution's exit status, so if `curl` fails — exit 7 on connection refused, which happens whenever the port-forward is not yet ready after the fixed `sleep 3`, or after `kubectl port-forward` drops (a well-known behavior on connection errors) — the entire script exits immediately with curl's exit code and **zero diagnostic output**. The deadline/retry logic at lines 178-184 never runs. This defeats the documented poll-until-deadline design and contradicts the script's own Phase 11 pattern, where every fallible poll is guarded (`|| true` at line 110, pipeline into `wc -l` at line 111). Separately, `curl` has no `--max-time`: on this host the script itself documents (lines 85-91) that the Docker Desktop proxy path can leave connections hanging with zero progress — a half-open forwarded connection makes `curl -s` block forever, and the deadline check at line 178 is only evaluated *after* curl returns, so the script hangs past its own 150s budget indefinitely.
**Fix:**
```bash
RESPONSE=$(curl -s --max-time 10 -G "http://localhost:9090/api/v1/query" \
  --data-urlencode "query=up{job=\"${job}\"}" || true)
```
`|| true` restores the intended retry semantics under errexit; `--max-time 10` bounds each poll so the 150s deadline is always honored.

## Warnings

### WR-01: pkill stale-port-forward cleanup pattern can never match the actual command line

**File:** `scripts/observability-up.sh:162` (vs. line 164)
**Issue:** The port-forward is launched as `kubectl ${KCTX} port-forward ...`, i.e. the real command line is `kubectl --context=kind-kind port-forward -n observability svc/kube-prometheus-stack-prometheus 9090:9090`. The pkill pattern `"kubectl port-forward -n observability svc/kube-prometheus-stack-prometheus"` requires `port-forward` immediately after `kubectl`, so it matches nothing — the cleanup is dead code. Consequence: a stale forward from a previous interrupted run (or the operator's own manual forward from Task 2 of the plan) keeps port 9090 bound; the new port-forward silently fails to bind (`&>/dev/null`), and Step 7 then polls whatever the *stale* process forwards — potentially a dead pod or an older stack — producing misleading timeouts or, worse, a false PASS against a stale Prometheus. (Note also that Git for Windows' bash does not ship `pkill`, so on plain Git Bash the guarded branch is skipped entirely — the pattern bug makes cleanup ineffective even where pkill exists, e.g. WSL2.)
**Fix:**
```bash
pkill -f "port-forward.*svc/kube-prometheus-stack-prometheus" 2>/dev/null || true
```
A pattern anchored on `port-forward.*svc/<name>` matches regardless of the `--context` flag position.

### WR-02: Port-forward liveness never checked — bind failure or death burns the full 150s with an empty diagnostic

**File:** `scripts/observability-up.sh:164-167`
**Issue:** `kubectl ... port-forward ... &>/dev/null &` discards all output, and the script never verifies the process survived (`sleep 3` is the only synchronization). If the bind fails (port 9090 already taken — see WR-01) or the forward dies mid-loop, every subsequent poll fails; even with the CR-01 fix applied, the script then burns the entire 150s deadline and fails with `Last response:` followed by an empty string — no hint that the port-forward itself was the problem.
**Fix:** After `sleep 3` (and optionally inside the poll loop), check the process is alive and fail fast with a targeted message:
```bash
sleep 3
if ! kill -0 "${PF_PID}" 2>/dev/null; then
  echo "ERROR: kubectl port-forward exited immediately — is port 9090 already in use?"
  exit 1
fi
```

### WR-03: ServiceMonitor selectors also match the MongoDB Services (latent over-match)

**File:** `infra/observability/servicemonitor-field-guide-api.yaml:14-16`, `infra/observability/servicemonitor-launchpad.yaml:14-16` (interacts with `charts/field-guide-api/templates/mongodb/service.yaml:10-12`, `charts/launchpad/templates/mongodb/service.yaml:10-12`)
**Issue:** Each chart's MongoDB Service includes the full common labels via `include "<chart>.labels"`, so `field-guide-api-mongodb` and `launchpad-mongodb` both carry `app.kubernetes.io/name: field-guide-api` / `launchpad`. The ServiceMonitor `matchLabels` therefore selects the MongoDB Services too. Today this is silently benign only because the MongoDB Service's single port is named `mongodb` and the endpoint filters on `port: http` — no targets are generated. But the selection is an accident of port naming, not intent: any future `http`-named port on those Services (or an endpoint change) would make Prometheus scrape mongod directly, and the manifests' comments do not acknowledge the over-match. Since the constraint is "no chart edits," tighten the ServiceMonitor side.
**Fix:**
```yaml
  selector:
    matchLabels:
      app.kubernetes.io/name: field-guide-api
    matchExpressions:
      - key: app.kubernetes.io/component   # excludes the -mongodb Service (component: mongodb)
        operator: DoesNotExist
```
(Same for `servicemonitor-launchpad.yaml`.)

### WR-04: Shared 150s deadline across both jobs — second job can spuriously fail, and the error message misstates the budget

**File:** `scripts/observability-up.sh:169-179`
**Issue:** `DEADLINE` is computed once (line 169) *before* the `for job in $VERIFY_JOBS` loop, so 150s is a combined budget: if `field-guide-api` legitimately takes ~140s (operator config reload up to ~60s + 15s scrape interval + evaluation lag), `launchpad` gets only ~10s and fails even though it would have passed moments later. The error message "did not reach 1 within 150s" (line 179) is then false for the second job. Plan 12-02's timeout-triage branch would misdiagnose this as slow scraping rather than a budget-accounting bug.
**Fix:** Move the deadline inside the loop so each job gets its own budget (or keep a shared budget and make the message say "combined deadline"):
```bash
for job in $VERIFY_JOBS; do
  DEADLINE=$(( $(date +%s) + 150 ))
  ...
```

## Info

### IN-01: up==1 check passes if ANY series matches — multi-replica semantics

**File:** `scripts/observability-up.sh:173-174`
**Issue:** `up{job="X"}` returns one series per endpoint. With `replicas: 1` (current values) the grep is exact, but at replicas > 1 the check passes when a single pod is scraped while others are down. Harmless today; worth a comment or a `min(up{job=...}) == 1` query (`query=min(up{job=\"${job}\"})`) if replica counts ever grow.
**Fix:** Add a one-line comment documenting the single-replica assumption, or switch the query to `min(up{job="..."})`.

### IN-02: `curl` and `make` are used but not in the prerequisite gate

**File:** `scripts/observability-up.sh:25-30` (vs. lines 173, 192-193)
**Issue:** The tool gate checks only `docker kubectl helm`, but Step 7 requires `curl` and Step 8 requires `make`. On a minimal environment the script fails 5+ minutes in (mid-Step-7/8) instead of at the fast-fail gate. Both tools ship with Git Bash/WSL2 in practice, hence Info.
**Fix:** `for tool in docker kubectl helm curl make; do ...`

---

_Reviewed: 2026-07-17T22:12:48Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
