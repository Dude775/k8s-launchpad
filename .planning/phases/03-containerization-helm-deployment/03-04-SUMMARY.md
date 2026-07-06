---
phase: 03-containerization-helm-deployment
plan: 04
subsystem: infra
tags: [verification, kind, docker, helm, mongodb, gunicorn, smoke-test]

# Dependency graph
requires:
  - phase: 03-01
    provides: apps/field-guide-api/Dockerfile + .dockerignore (non-root gunicorn image)
  - phase: 03-02
    provides: charts/field-guide-api/ Helm chart (app + embedded mongo:7 manifests)
  - phase: 03-03
    provides: Makefile build/load/deploy/undeploy targets
provides:
  - Live end-to-end proof of the full build-to-deploy loop on a real kind cluster
  - Requirement verification evidence for IMG-01, IMG-02, HELM-01, HELM-02, HELM-03
affects: [phase-04]

# Tech tracking
tech-stack:
  added: []
  patterns: [in-pod endpoint verification via kubectl exec python3 urllib (port-forward fallback)]

key-files:
  created: []
  modified: []

key-decisions:
  - "Endpoint smoke tests verified via kubectl exec + python3 urllib inside the pod — kubectl port-forward fails on this Windows/Docker Desktop/kind host (namespace dial refused); equivalent verification, documented as tooling limitation not app bug"
  - "App pod targeted by label selector -l app.kubernetes.io/name=field-guide-api — bare `deploy/field-guide-api` exec can resolve to the mongodb pod"
  - "Worktree venv recreated with py -3 (Python 3.12.10) — stale pyenv 3.7.4 shim produced a broken pip-less venv"

patterns-established:
  - "Live acceptance gate protocol: single foreground make/helm/kubectl commands, no concurrent docker calls (mirrors 02-02)"

requirements-completed: [IMG-01, IMG-02, HELM-01, HELM-02, HELM-03]

# Metrics
duration: ~45min
completed: 2026-07-06
---

# Phase 3 Plan 04: Live End-to-End Build-to-Deploy Verification Summary

**Full loop proven live on kind: cluster-up → build (9.85kB context) → push to localhost:5001 → helm lint clean → deploy (app + mongo Running) → non-root gunicorn UID 10001 → /health 200 mongo up, POST+GET entry round-trip, Prometheus /metrics → clean uninstall (PVC gone) → 32 tests 100% coverage**

## Performance

- **Duration:** ~45 min (includes ~2 min cluster creation + image pulls)
- **Completed:** 2026-07-06
- **Tasks:** 1 (blocking human-verify checkpoint — approved)
- **Files modified:** 0 (verification-only plan)

## Verification Evidence

All commands run inline as single foreground calls from the executor worktree root (02-02 protocol — no concurrent docker/kind/kubectl commands).

| # | Check | Command | Result | Requirement |
|---|-------|---------|--------|-------------|
| 1 | Cluster + registry up | `make cluster-up` | Exit 0; "==> Registry wiring verified OK" (host-push → in-pod-pull verified) | CLUS (regression) |
| 2 | Image build | `make build` | `localhost:5001/field-guide-api:dev` built; build context transfer **9.85kB** — .dockerignore effective | IMG-01 |
| 3 | Registry push | `make load` | `docker push localhost:5001/field-guide-api:dev` succeeded (digest sha256:1293ed58...) | — |
| 4 | Chart lint | `helm lint charts/field-guide-api` | 1 chart linted, **0 failed** (only INFO: icon recommended) | HELM-01 |
| 5 | Deploy | `make deploy` | `helm upgrade --install --wait` reached Ready; `field-guide-api` + `field-guide-api-mongodb` pods both 1/1 Running | HELM-02, HELM-03 |
| 6 | Non-root runtime | `kubectl exec <app-pod> -- id -u` | **10001** | IMG-01 |
| 7 | Gunicorn PID 1 | `kubectl exec <app-pod> -- cat /proc/1/cmdline` | `gunicorn --bind 0.0.0.0:8000 --workers 1 --threads 4 --access-logfile - --error-logfile - wsgi:app` (not `flask run`) | IMG-02 |
| 8a | Health | `GET /health` (in-pod python3 urllib) | HTTP 200 `{"status": "ok", "mongo": "up"}` — proves `?authSource=admin` MONGO_URI works, no AuthenticationFailed in logs | HELM-02 |
| 8b | CRUD round-trip | `POST /entries` then `GET /entries` | POST → 201 with created doc (id `6a4bf00e7c3018f3919e4959`); GET → 200 returning the entry — MongoDB write/read proven in-cluster | HELM-02 |
| 8c | Metrics seam | `GET /metrics` | Prometheus-format text (`python_gc_*`, `process_*`, `flask_exporter_info`) — PRD-4 scrape seam live | HELM-02 |
| 9 | Clean uninstall | `make undeploy` then `kubectl get pvc,deploy,svc,secret,configmap -l app.kubernetes.io/instance=field-guide-api` | "No resources found in default namespace" — **PVC removed** with all chart resources | HELM-03 |
| 10 | Regression gate | `make test PYTHON="py -3"` | **32 passed, 100% coverage** (threshold 95%) | TEST (regression) |

Additional observed-normal behavior (matched RESEARCH.md pitfalls exactly):
- App `/health` returned 503 for ~40s after start until mongo readiness flipped, then 200 continuously (self-converging, no init containers — Pitfall as predicted)
- kube-probe log showed 400+ consecutive 200s on `/health` during the session
- Image pulled by kubelet from `localhost:5001` via containerd mirror in 3.78s (51.3MB image)

## Deviations from Plan

### Verification-method substitutions (no code changes)

**1. [Tooling limitation] kubectl port-forward fails on this host — endpoints verified via kubectl exec instead**
- **Found during:** Task 1 step 8
- **Issue:** `kubectl port-forward svc/field-guide-api 8080:80` consistently failed with `failed to connect to localhost:8000 inside namespace ... connection refused` on Windows + Docker Desktop + kind, despite the pod serving 200s to kube-probe on the same port. Known Windows port-forward/namespace limitation, NOT an app or chart bug (pod logs prove gunicorn listening on 0.0.0.0:8000 and serving).
- **Fix:** Verified all three endpoints equivalently from inside the pod via `kubectl exec <pod> -- python3 -c "urllib.request.urlopen(...)"` (slim image has no wget/curl). Same network path the readiness probe uses.
- **Approved:** User accepted this substitution at the checkpoint.

**2. [Rule 3 - Blocking] Worktree venv was broken (Python 3.7.4, no pip) — recreated with py -3**
- **Found during:** Task 1 step 10 (`make test`)
- **Issue:** The executor worktree's `apps/field-guide-api/.venv` had been created by a stale pyenv 3.7.4 shim and lacked pip, so `make test` failed with WinError 2 / "No module named pip".
- **Fix:** Removed the worktree `.venv` and re-ran `make test PYTHON="py -3"` (Python 3.12.10, matching the main checkout's venv). 32 passed, 100% coverage. Main repo venv untouched.
- **Files modified:** none (venv is gitignored)

**3. [Precision note] `kubectl exec deploy/field-guide-api` resolved to the mongodb pod on first attempt**
- **Found during:** Task 1 step 7
- **Issue:** The plan's suggested `kubectl exec deploy/field-guide-api -- id -u` initially returned `0` from a mongod process — the bare deploy selector had resolved to the wrong pod.
- **Fix:** Re-ran using the label selector `-l app.kubernetes.io/name=field-guide-api` against the app pod directly → UID `10001`, PID 1 = gunicorn. IMG-01/IMG-02 verified against the correct container.

---

**Total deviations:** 3 (2 verification-method substitutions, 1 blocking env fix). Zero source/chart/Makefile changes — the artifacts from 03-01/02/03 worked as shipped.

## Issues Encountered

- Docker Hub was healthy this session — the optional `kind load docker-image mongo:7` pre-seed (Pitfall 6 dodge) was not needed; mongo:7 pulled cleanly.
- Transient `Control server error: [Errno 13] Permission denied: '/home/app'` in gunicorn startup log (non-root user has no writable home). Harmless — gunicorn served traffic normally throughout. Candidate polish item for Phase 4 (set `HOME=/tmp` or `--worker-tmp-dir`), logged as observation only.

## User Setup Required

None.

## Cluster State at Completion

- kind cluster **UP** (`kind-control-plane` Ready, v1.36.1)
- `kind-registry` container **UP** on localhost:5001
- Helm release **uninstalled** — zero `field-guide-api` resources in the cluster (verified empty labeled query)

## Phase 3 Success Criteria — All Proven Live

1. Gunicorn non-root container (UID 10001, gunicorn PID 1) — criteria 1 ✓
2. `helm lint` clean + `helm install` of app + mongodb — criterion 2 ✓
3. App reachable, `/health` 200 mongo up, `/entries` CRUD round-trip — criterion 3 ✓
4. Plain mongo:7 manifests, clean `helm uninstall` incl. PVC — criterion 4 ✓
5. Generic values.yaml — proven by 03-02's render checks (per plan)

## Next Phase Readiness

- The core value loop `make cluster-up && make build && make load && make deploy` is proven end to end — PRD-1's central promise holds
- Phase 4 (README + polish) can document the exact commands verified here
- Deferred observation: gunicorn `/home/app` permission warning (cosmetic) — optional Phase 4 polish

## Self-Check: PASSED

- SUMMARY.md exists at .planning/phases/03-containerization-helm-deployment/03-04-SUMMARY.md ✓
- No task commits expected (verification-only plan, files_modified: []) ✓
- All 8 acceptance criteria evidence recorded above ✓

---
*Phase: 03-containerization-helm-deployment*
*Completed: 2026-07-06*
