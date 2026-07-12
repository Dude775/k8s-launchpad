---
phase: 09-service-catalog-events-mongodb-crud
plan: 03
subsystem: infra
tags: [helm, kubernetes, mongodb, mongo7, kind]

# Dependency graph
requires:
  - phase: 08-helm-chart-k8s-diagnostics
    provides: charts/launchpad/ chart skeleton (Deployment, Service, ConfigMap, Secret, RBAC, _helpers.tpl) with the D-08 accepted NotReady consequence
provides:
  - charts/launchpad/templates/mongodb/{deployment,pvc,secret,service}.yaml — mechanical mirror of the field-guide-api in-cluster MongoDB manifests, database name launchpad
  - launchpad.mongodb.fullname + launchpad.mongodb.selectorLabels helpers in _helpers.tpl (distinct selector identity, no collision with the app Service)
  - SECRET_KEY delivered via the launchpad Secret; EVENTS_TTL_SECONDS delivered via the launchpad ConfigMap; both injected into the Deployment env
  - values.yaml mongodb: block (mongo:7, root auth, 1Gi persistence, db launchpad) and mongoUri rewired to the in-cluster launchpad-mongodb Service (authSource=admin, serverSelectionTimeoutMS=2000)
affects: [09-04, 10-01, phase-10-makefile-smoke]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Helm mongodb mirror pattern: field-guide-api's templates/mongodb/*.yaml + two _helpers.tpl helpers is the canonical shape for any future chart needing an in-cluster mongo:7 sidecar database"

key-files:
  created:
    - charts/launchpad/templates/mongodb/deployment.yaml
    - charts/launchpad/templates/mongodb/pvc.yaml
    - charts/launchpad/templates/mongodb/secret.yaml
    - charts/launchpad/templates/mongodb/service.yaml
  modified:
    - charts/launchpad/templates/_helpers.tpl
    - charts/launchpad/templates/secret.yaml
    - charts/launchpad/templates/configmap.yaml
    - charts/launchpad/templates/deployment.yaml
    - charts/launchpad/values.yaml

key-decisions:
  - "mongoUri hardcodes the default-release-name hostname (launchpad-mongodb) with a values.yaml comment documenting the override path for non-default release names, since mongoUri is a plain value string rather than a Helm template"
  - "EVENTS_TTL_SECONDS delivered via ConfigMap (not Secret) — TTL seconds is not sensitive, per RESEARCH.md A3 precedent"

patterns-established:
  - "Chart mongodb mirroring: any future in-chart mongo:7 sidecar should copy charts/field-guide-api/templates/mongodb/*.yaml + the two _helpers.tpl helpers verbatim, substituting only the fullname prefix and database name"

requirements-completed: [DEP-03]

# Metrics
duration: 12min
completed: 2026-07-12
---

# Phase 09 Plan 03: MongoDB Manifests for launchpad Summary

**Mirrored field-guide-api's in-cluster mongo:7 Deployment/PVC/Secret/Service into charts/launchpad/, added the two mongodb _helpers.tpl helpers, wired SECRET_KEY + EVENTS_TTL_SECONDS into the app Deployment, and rewired mongoUri to the new in-cluster launchpad-mongodb Service — live deploy verified: launchpad pod READY 1/1, resolving the Phase 8 D-08 NotReady consequence.**

## Performance

- **Duration:** 12 min (file changes) + live-deploy verification at the checkpoint
- **Started:** 2026-07-12T20:04:00Z
- **Completed:** 2026-07-12T20:16:00Z (files); Task 3 checkpoint verified and approved afterwards
- **Tasks:** 3 of 3 completed (Task 3 human-verify checkpoint approved with live evidence)
- **Files modified:** 9 (4 created, 5 modified)

## Accomplishments
- Four mongodb manifests (`deployment.yaml`, `pvc.yaml`, `secret.yaml`, `service.yaml`) mechanically mirrored from `charts/field-guide-api/templates/mongodb/` into `charts/launchpad/templates/mongodb/`, database name `launchpad`, `Recreate` strategy and unauthenticated `mongosh` ping readinessProbe preserved verbatim
- `launchpad.mongodb.fullname` and `launchpad.mongodb.selectorLabels` helpers added to `_helpers.tpl` with a distinct `-mongodb` name suffix (no selector collision with the app Service)
- `SECRET_KEY` (Secret) and `EVENTS_TTL_SECONDS` (ConfigMap) now flow into the Deployment env via `secretKeyRef`/`configMapKeyRef`
- `values.yaml` gained a `mongodb:` block (mirrors field-guide-api's shape, db `launchpad`), a `secretKey` dev default, `config.eventsTtlSeconds: "604800"`, and `mongoUri` rewired from the `localhost:27017` placeholder to `mongodb://root:launchpad-dev-password@launchpad-mongodb:27017/launchpad?authSource=admin&serverSelectionTimeoutMS=2000`
- `helm lint charts/launchpad/` passes with no warnings; `helm template launchpad charts/launchpad/` renders two Deployments (app + mongodb), a `mongo:7` image, a 27017 ClusterIP Service named `launchpad-mongodb`, and the app Secret/ConfigMap/Deployment carrying `SECRET_KEY`/`EVENTS_TTL_SECONDS`
- `charts/field-guide-api/` left completely untouched (`git status --short charts/field-guide-api/` prints nothing)
- **Live deploy verified (Task 3, D-08 resolution):** fresh kind cluster via `make cluster-up`; image built and pushed to `localhost:5001/launchpad:latest`; `helm upgrade --install launchpad charts/launchpad/` — `launchpad-6584676689-49gfq` READY 1/1 Running and `launchpad-mongodb-746bfccbbd-hcwqg` READY 1/1 Running within ~47s; `/health` via port-forward returned HTTP 200 `{"status": "ok", "mongo": "up"}`; `/api/status` returned `{"api_health": "ok", "mongo_status": "up", "service_count": 0, ...}` with no 500 on a fresh DB

## Task Commits

Each task was committed atomically:

1. **Task 1: Mirror the four mongodb manifests + add the two _helpers.tpl helpers** - `76e963a` (feat)
2. **Task 2: Rewire Secret/ConfigMap/Deployment env + values.yaml mongodb block + mongoUri target** - `cdf9daa` (feat)
3. **Task 3: Live manual deploy — launchpad pod flips to READY 1/1** - no commit (verification-only checkpoint; VERIFIED live: both pods READY 1/1 Running, `/health` 200, `/api/status` clean on a fresh DB)

**Plan metadata:** `c09e3fd` (initial SUMMARY) + follow-up commit recording the Task 3 verification outcome

## Files Created/Modified
- `charts/launchpad/templates/mongodb/deployment.yaml` - mongo:7 Deployment, Recreate strategy, mongosh ping readinessProbe, MONGO_INITDB_ROOT_* via secretKeyRef
- `charts/launchpad/templates/mongodb/pvc.yaml` - ReadWriteOnce PVC sized from `.Values.mongodb.persistence.size`
- `charts/launchpad/templates/mongodb/secret.yaml` - MONGO_INITDB_ROOT_USERNAME/PASSWORD stringData from `.Values.mongodb.auth.*`
- `charts/launchpad/templates/mongodb/service.yaml` - ClusterIP Service on 27017, selector via `launchpad.mongodb.selectorLabels`
- `charts/launchpad/templates/_helpers.tpl` - added `launchpad.mongodb.fullname` + `launchpad.mongodb.selectorLabels`; removed the stale "no mongodb helpers here" comment
- `charts/launchpad/templates/secret.yaml` - added `SECRET_KEY` to stringData
- `charts/launchpad/templates/configmap.yaml` - added `EVENTS_TTL_SECONDS` to data
- `charts/launchpad/templates/deployment.yaml` - added SECRET_KEY/EVENTS_TTL_SECONDS env entries; updated stale readinessProbe header comment
- `charts/launchpad/values.yaml` - added `mongodb:` block, `secretKey`, `config.eventsTtlSeconds`; rewired `mongoUri` to the in-cluster Service

## Decisions Made
- `mongoUri` is a plain value string (not a Helm template expression), so it hardcodes the default-release-name-derived hostname `launchpad-mongodb`; a values.yaml comment documents that a non-default release name requires an explicit `--set mongoUri=...` override — this mirrors field-guide-api's existing MONGO_URI discipline and avoids introducing template-string interpolation into values.yaml (which Helm does not evaluate).
- `EVENTS_TTL_SECONDS` placed in the ConfigMap, not the Secret — TTL seconds is not sensitive information (RESEARCH.md A3 precedent already established this for non-credential config).

## Deviations from Plan

None - plan executed exactly as written. Task 3's live-deploy verification was performed at the checkpoint on the user's behalf (build → load → deploy against a fresh kind cluster) and all acceptance criteria passed on the first run.

## Issues Encountered

None — `helm lint` and `helm template` verification passed on the first attempt after both edits landed, and the live deploy succeeded on the first run (both pods ready within ~47s).

## User Setup Required

None - no external service configuration required. The Task 3 live-deploy verification has been completed and approved.

## Next Phase Readiness

- DEP-03 delivered: launchpad has its own in-cluster mongo:7 database, and the app pod reaches READY 1/1 against it (Phase 8 D-08 consequence closed)
- The `services`/`events` collections now have a real database to target — 09-01's index creation runs against live Mongo on pod start
- Ready for Phase 10 (DEP-04/05): Makefile targets and smoke tests can now assume a Ready launchpad pod

---
*Phase: 09-service-catalog-events-mongodb-crud*
*Completed: 2026-07-12*
