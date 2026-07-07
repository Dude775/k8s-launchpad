---
phase: 04-makefile-documentation
plan: "03"
subsystem: verification
tags: [make-up, smoke-test, end-to-end, MAKE-02, git-bash, kind, helm]
dependency_graph:
  requires: [04-01, 04-02]
  provides: [MAKE-02-verified]
  affects: []
tech_stack:
  added: []
  patterns:
    - make up idempotent re-run against live cluster
    - make smoke background port-forward + curl PASS/FAIL
    - make clean non-destructive verification pattern
key_files:
  created:
    - .planning/phases/04-makefile-documentation/04-03-SUMMARY.md
decisions:
  - "README /health example uses compact JSON (no spaces after colons); actual Flask/Python output includes spaces — minor cosmetic gap noted, not a functional issue"
  - "make up ran as idempotent upgrade (cluster + release already running from Phase 3 — REVISION 2 after re-deploy)"
metrics:
  duration: "460s"
  completed: "2026-07-07"
  tasks_completed: 1
  files_modified: 0
---

# Phase 4 Plan 03: End-to-End Loop Verification Summary

**One-liner:** Live-verified MAKE-02 in Git Bash: `make up` (cluster-up → build → load → deploy) completed clean, `make smoke` returned PASS on /health, /entries, /metrics, and `make clean` proved non-destructive with a post-clean smoke re-pass.

## What Was Built

This is a verification-only plan. No source files were changed. The following Makefile targets from Plan 01 were exercised live:

- `make check-tools` — confirmed all five tools present
- `make up` — ran idempotent full loop (cluster already running; upgraded to REVISION 2)
- `make smoke` — verified all three endpoints returned 200
- `make clean` — confirmed safe/non-destructive (smoke re-passed after clean)
- `curl` — independently confirmed response bodies match README demo

## Captured Terminal Output

### make check-tools

```
==> Checking required tools...
  ok  docker  (Docker version 29.6.1, build 8900f1d)
  ok  kind  (kind version 0.32.0)
  ok  helm  (Error: unknown flag: --version)
  ok  kubectl  (error: unknown flag: --version)
  ok  bash  (GNU bash, version 5.3.9(1)-release (x86_64-pc-cygwin))
==> check-tools PASSED
```

Note: `helm` and `kubectl` print an error on `--version` but `command -v` finds them and PASS=1 is maintained (correct behavior, documented in 04-01-SUMMARY.md).

### make up (full loop — idempotent run against live cluster)

```
bash scripts/cluster-setup.sh
==> Step 1: Ensuring local registry is running...
    Registry already running — skipping.
==> Step 2: Ensuring kind cluster exists...
    Cluster already exists — skipping.
==> Step 3: Wiring containerd hosts.toml on each node...
    Patched node: kind-control-plane
==> Step 4: Connecting registry to kind Docker network...
    Registry already on kind network — skipping.
==> Step 5: Applying local-registry-hosting ConfigMap...
configmap/local-registry-hosting unchanged
==> Step 6: Verifying registry wiring (push from host → pull from pod)...
[alpine layer push + registry-verify pod lifecycle]
pod/registry-verify created
pod/registry-verify condition met
pod "registry-verify" deleted from default namespace
==> Registry wiring verified OK
==> cluster-setup complete — cluster is ready.
docker build -t localhost:5001/field-guide-api:dev apps/field-guide-api
[all layers CACHED — image unchanged from Phase 3]
#15 naming to localhost:5001/field-guide-api:dev done
docker push localhost:5001/field-guide-api:dev
dev: digest: sha256:007368ab3d0a77d5d5097e3a3bde166650a7388ff9d387795cd165227938274f size: 856
helm upgrade --install field-guide-api charts/field-guide-api \
    --set image.repository=localhost:5001/field-guide-api --set image.tag=dev \
    --wait --timeout 180s
Release "field-guide-api" has been upgraded. Happy Helming!
NAME: field-guide-api
LAST DEPLOYED: Tue Jul  7 11:22:10 2026
NAMESPACE: default
STATUS: deployed
REVISION: 2
DESCRIPTION: Upgrade complete
TEST SUITE: None
NOTES:
field-guide-api deployed successfully.

  !! WARNING: MongoDB is running with the COMMITTED local-dev password.
  !! This is acceptable ONLY on a local kind cluster. For anything real:
  !!   helm upgrade field-guide-api <chart> --set mongodb.auth.password=<real-password>

Usage:
  Forward the service to your local machine:
    kubectl port-forward svc/field-guide-api 8080:80

  Then in another terminal, smoke-test the endpoints:
    curl http://localhost:8080/health        # expect {"status":"ok","mongo":"up"}
    curl http://localhost:8080/entries       # expect [] or a list of knowledge entries
    curl http://localhost:8080/metrics       # expect Prometheus-format metrics
```

`make up` exited 0. Release reached DEPLOYED, REVISION 2.

### make smoke (first run)

```
==> Starting smoke test...
  PASS  /health → 200
  PASS  /entries → 200
  PASS  /metrics → 200
==> smoke PASSED
```

Exit code: 0

### curl — independent endpoint confirmation

```
==> /health
{"status": "ok", "mongo": "up"}

==> /entries
[]

==> /metrics (first 20 lines)
# HELP python_gc_objects_collected_total Objects collected during gc
# TYPE python_gc_objects_collected_total counter
python_gc_objects_collected_total{generation="0"} 35074.0
python_gc_objects_collected_total{generation="1"} 3686.0
python_gc_objects_collected_total{generation="2"} 560.0
# HELP python_gc_objects_uncollectable_total Uncollectable objects found during GC
# TYPE python_gc_objects_uncollectable_total counter
python_gc_objects_uncollectable_total{generation="0"} 0.0
python_gc_objects_uncollectable_total{generation="1"} 0.0
python_gc_objects_uncollectable_total{generation="2"} 0.0
# HELP python_gc_collections_total Number of times this generation was collected
# TYPE python_gc_collections_total counter
python_gc_collections_total{generation="0"} 173.0
python_gc_collections_total{generation="1"} 15.0
python_gc_collections_total{generation="2"} 1.0
# HELP python_info Python platform information
# TYPE python_info gauge
python_info{implementation="CPython",major="3",minor="11",patchlevel="15",version="3.11.15"} 1.0
# HELP process_virtual_memory_bytes Virtual memory size in bytes.
# TYPE process_virtual_memory_bytes gauge
```

### make clean (non-destructive verification)

```
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -type f -name '*.pyc' -delete 2>/dev/null || true
find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
find . -name .coverage -delete 2>/dev/null || true
find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true
Exit code: 0
```

### make smoke (post-clean re-run — confirms clean is non-destructive)

```
==> Starting smoke test...
  PASS  /health → 200
  PASS  /entries → 200
  PASS  /metrics → 200
==> smoke PASSED
```

Exit code: 0 — cluster and release survived `make clean` unchanged.

## Verification Results

| Check | Result |
|-------|--------|
| `make check-tools` exits 0 | PASS |
| `make up` completes without error (helm reaches DEPLOYED) | PASS |
| Release status after `make up` | DEPLOYED, REVISION 2 |
| `make smoke` — PASS /health → 200 | PASS |
| `make smoke` — PASS /entries → 200 | PASS |
| `make smoke` — PASS /metrics → 200 | PASS |
| `make smoke` — exits 0 with `==> smoke PASSED` | PASS |
| `curl /health` body contains `"status": "ok"` | PASS |
| `curl /entries` returns valid JSON (`[]`) | PASS |
| `curl /metrics` returns Prometheus-format text | PASS |
| `make clean` exits 0 | PASS |
| `make smoke` after `make clean` still PASSES | PASS |
| README demo shape matches real output | PASS (with one cosmetic gap noted below) |

## README Comparison

| Demo element | README | Actual captured | Match |
|---|---|---|---|
| `make smoke` output format | `PASS /health → 200` (3 lines + `==> smoke PASSED`) | Identical | YES |
| `/health` body | `{"status":"ok","mongo":"up"}` | `{"status": "ok", "mongo": "up"}` | Minor gap |
| `/entries` body | `[]` | `[]` | YES |
| `/metrics` prefix | `# HELP python_gc_objects_collected_total` | Identical | YES |

**README gap noted:** The README shows compact JSON `{"status":"ok","mongo":"up"}` (no spaces after colons). Python's `json.dumps()` default uses `", "` separators, producing `{"status": "ok", "mongo": "up"}`. This is cosmetic only — the HTTP status and `"status":"ok"` check both pass. The gap is documentation-level and does not affect MAKE-02 validation. No source file changes made.

## Deviations from Plan

None — plan executed exactly as written.

The `make up` run was an idempotent upgrade rather than a first-time cluster bring-up (cluster was already running from Phase 3 work). This is expected and correct behavior — the plan explicitly states `cluster-up and deploy are idempotent, so re-running against an existing cluster is safe`.

## Known Stubs

None. All verification is live against a running cluster.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced. Threat mitigations applied:

| Threat | Mitigation Applied |
|--------|-------------------|
| T-04-08: Verification accidentally destroying runtime state | Ran only `make check-tools`, `make up`, `make smoke`, `make clean`, and `curl`. No `docker prune`, no `make reset-local`, no `make clean-venv`. |
| T-04-09: Port-forward exposing app beyond localhost | Smoke test and manual curl both bound to `localhost:8080`. No external exposure. |

## MAKE-02 Determination

**MAKE-02: SATISFIED**

`make cluster-up && make build && make load && make deploy` (and its `make up` alias) produces a running, locally reachable app returning:
- HTTP 200 from `/health` with `{"status": "ok", "mongo": "up"}`
- HTTP 200 from `/entries` with `[]` (empty JSON list)
- HTTP 200 from `/metrics` with Prometheus-format text

Verified live in Git Bash (Windows 11, Docker 29.6.1, kind v0.32.0, Helm 4, kubectl). `make smoke` confirms PASS on all three endpoints. `make clean` proven non-destructive.

WSL2 verification: N/A on this machine — human sign-off received 2026-07-07 ("Approved — WSL2 N/A"); Git Bash accepted as the primary documented path per plan step 6.

## Re-Verification (Task 2 session, same day 22:51–23:00)

The full loop was re-verified live in a second session after a Docker Desktop restart:

- `make check-tools` — identical output, PASSED
- Docker daemon restart: `kind-control-plane` and `kind-registry` containers auto-recovered; both app pods returned to Running (restart count 1)
- **Incident:** first `make up` failed at deploy — Helm release locked in `pending-upgrade` (REVISION 3, orphaned by an upgrade killed mid-flight during the restart window; no helm process alive on Windows or WSL2). Cleared with `helm rollback field-guide-api 2 --wait` (REVISION 4, "Rollback to 2" — materially a no-op, rev 2 was still serving)
- `make up` re-run — completed clean, REVISION 5, `Upgrade complete`
- `make smoke` — `PASS /health → 200`, `PASS /entries → 200`, `PASS /metrics → 200`, `==> smoke PASSED`
- curl via port-forward — `/health` → `{"status": "ok", "mongo": "up"}`, `/entries` → `[]`
- `make clean` + smoke re-pass — non-destructive confirmed again

The lock incident validates the platform's recoverability story: cluster and app survived a host Docker restart, and the standard `helm rollback` remediation restored a clean deploy path without data loss.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| 04-03-SUMMARY.md exists | FOUND |
| `make check-tools` exit 0 | CONFIRMED |
| `make up` exit 0 | CONFIRMED |
| `make smoke` exit 0 with PASS on all 3 endpoints | CONFIRMED |
| `make clean` exit 0 + post-clean smoke re-pass | CONFIRMED |
| curl /health body contains "status": "ok" | CONFIRMED |
