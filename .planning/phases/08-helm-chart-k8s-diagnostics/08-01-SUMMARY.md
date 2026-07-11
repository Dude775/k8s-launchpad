---
phase: 08-helm-chart-k8s-diagnostics
plan: 01
subsystem: infra
tags: [helm, kubernetes, rbac, kind, docker]

# Dependency graph
requires:
  - phase: 03
    provides: "charts/field-guide-api/ — the analog chart mirrored into charts/launchpad/ (structure, checksum annotations, securityContext, probe shapes)"
  - phase: 07
    provides: "app/config.py env var names (MONGO_URI, FIELD_GUIDE_BASE_URL, APP_VERSION, FLASK_DEBUG) and the /health own-Mongo readiness contract the readinessProbe targets"
provides:
  - "charts/launchpad/ — complete, helm lint-clean Helm chart (Chart.yaml, values.yaml, Deployment, Service, ConfigMap, Secret, RBAC, NOTES.txt)"
  - "launchpad.* _helpers.tpl naming that does not collide with field-guide-api selectors when both charts share a namespace"
  - "ServiceAccount launchpad + namespace-scoped Role (launchpad-read) + RoleBinding granting only get/list/watch on pods+deployments — the RBAC identity Plan 02's cluster_state.py reads through in-cluster"
  - "Live-verified: launchpad pod reaches Running via the manual deploy loop (docker build + kind load + helm install)"
affects: [09-mongodb-manifests, 10-makefile-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Chart mirroring: copy an already-proven chart verbatim, swap only the helper-name prefix and the deployment-specific env/RBAC wiring, rather than authoring a chart from scratch"
    - "RBAC three-document rbac.yaml (ServiceAccount + Role + RoleBinding in one file, --- separated) with literal (non-templated) ServiceAccount name so serviceAccountName: launchpad in the Deployment is a stable literal binding, not a helper-derived value"

key-files:
  created:
    - charts/launchpad/Chart.yaml
    - charts/launchpad/.helmignore
    - charts/launchpad/values.yaml
    - charts/launchpad/templates/_helpers.tpl
    - charts/launchpad/templates/deployment.yaml
    - charts/launchpad/templates/service.yaml
    - charts/launchpad/templates/configmap.yaml
    - charts/launchpad/templates/secret.yaml
    - charts/launchpad/templates/rbac.yaml
    - charts/launchpad/templates/NOTES.txt
  modified: []

key-decisions:
  - "Task 1's literal repo-wide grep verify (! grep -rq 'field-guide-api' .) was interpreted against acceptance-criteria intent (helper/label collision), not literally — values.yaml's config.fieldGuideBaseUrl: http://field-guide-api is a mandated functional default (K8s Service DNS name), not leaked analog boilerplate"
  - "D-09 manual deploy loop accepted as SC #2 verification for Phase 8; make build-launchpad/load-launchpad/deploy-launchpad targets remain deferred to Phase 10 (DEP-04), not added here"
  - "D-08 confirmed live: readinessProbe left unweakened at /health:8000; the pod reached Running with READY 0/1 (NotReady) because launchpad's own MongoDB does not exist until Phase 9 (DEP-03) — this is the designed/expected outcome, not a defect"

patterns-established:
  - "Any future launchpad-adjacent chart work should treat charts/launchpad/_helpers.tpl selectorLabels (app.kubernetes.io/name: launchpad) as the load-bearing collision guard against charts/field-guide-api/ when both run in the same namespace"

requirements-completed: [DEP-01, DEP-02]

# Metrics
duration: unrecorded (continuation agent — original session duration not captured)
completed: 2026-07-12
---

# Phase 08 Plan 01: Helm Chart + RBAC Summary

**charts/launchpad/ Helm chart (lint-clean, collision-free) with least-privilege namespace-scoped RBAC, live-verified to reach pod Running via the manual deploy loop**

## Performance

- **Duration:** unrecorded (continuation agent completing after an approved human-verify checkpoint; original task execution duration not captured in this session)
- **Tasks:** 3 (2 auto + 1 checkpoint:human-verify)
- **Files modified:** 10 (all created)

## Accomplishments
- `charts/launchpad/` mirrors `charts/field-guide-api/` verbatim minus the `mongodb/` subchart (D-06), with every `field-guide-api.*` helper renamed to `launchpad.*` — the distinct `app.kubernetes.io/name: launchpad` selector label is what prevents a Service selector collision when both charts run in the same namespace (SC #1)
- `rbac.yaml` provisions a `ServiceAccount` (literal name `launchpad`), a namespace-scoped `Role` (`launchpad-read`, never `ClusterRole`) granting only `get`/`list`/`watch` on `pods` (core group) and `deployments` (`apps` group), and a `RoleBinding` — the exact least-privilege identity Plan 02's `cluster_state.py` reads through in-cluster (SC #4, DEP-02)
- `deployment.yaml` sets `serviceAccountName: launchpad`, injects `POD_NAMESPACE` via the Downward API (D-05), sources `MONGO_URI` exclusively via `secretKeyRef` (never a ConfigMap or plaintext literal), and keeps the `/health:8000` readinessProbe unweakened (D-08)
- `helm lint charts/launchpad/` passes with 0 errors, 0 warnings (one informational `icon is recommended` notice only)
- `helm template launchpad charts/launchpad/` renders with no `app.kubernetes.io/name: field-guide-api` anywhere, and the Role rules render with exactly the two intended rule blocks (get/list/watch only, no write verbs)
- Manual deploy loop (D-09) executed and approved by the operator: `helm install launchpad charts/launchpad/` → `STATUS: deployed`; `kubectl get pods -l app.kubernetes.io/name=launchpad -w` → pod reached `Running` (`READY 0/1`, expected/accepted per D-08 until Phase 9 supplies launchpad's own MongoDB)

## Task Commits

Each task was committed atomically:

1. **Task 1: Mirror field-guide-api chart into charts/launchpad/ with launchpad.* naming (8 files)** - `98263d9` (feat)
2. **Task 2: Add deployment.yaml + rbac.yaml; helm lint + template collision gates passed** - `039ad73` (feat)
3. **Task 3: checkpoint:human-verify — manual deploy loop (D-09)** - APPROVED by operator, no code commit (verification-only checkpoint)

**Plan metadata:** (this commit, pending)

## Files Created/Modified
- `charts/launchpad/Chart.yaml` - Chart metadata (`name: launchpad`, `apiVersion: v2`)
- `charts/launchpad/.helmignore` - copied verbatim from the field-guide-api analog
- `charts/launchpad/values.yaml` - `image.repository: localhost:5001/launchpad`, `config.fieldGuideBaseUrl`/`appVersion`/`flaskDebug`, top-level `mongoUri` local-dev placeholder; no `mongodb:` block, no `externalMongoUri`
- `charts/launchpad/templates/_helpers.tpl` - `launchpad.name`/`fullname`/`chart`/`labels`/`selectorLabels`; mongodb helpers deleted (no subchart in this chart)
- `charts/launchpad/templates/deployment.yaml` - `serviceAccountName: launchpad`, `POD_NAMESPACE` Downward API env, MONGO_URI via `secretKeyRef`, unweakened `/health:8000` readinessProbe, `tcpSocket:8000` livenessProbe
- `charts/launchpad/templates/service.yaml` - `launchpad.*` helper includes; port 80 → targetPort 8000
- `charts/launchpad/templates/configmap.yaml` - `FIELD_GUIDE_BASE_URL`, `APP_VERSION`, `FLASK_DEBUG` (no `MONGO_URI`, no `MONGO_DBNAME`)
- `charts/launchpad/templates/secret.yaml` - `type: Opaque`, single `stringData.MONGO_URI` placeholder ending `?serverSelectionTimeoutMS=2000`
- `charts/launchpad/templates/rbac.yaml` - `ServiceAccount` (`launchpad`) + namespace-scoped `Role` (`launchpad-read`) + `RoleBinding`, three YAML documents separated by `---`
- `charts/launchpad/templates/NOTES.txt` - reworded for launchpad; mongodb-password warning block removed

## Decisions Made
- The Task 1 acceptance-criteria grep gate (`grep -r 'field-guide-api' charts/launchpad/` returns nothing) was verified against its stated intent — no leftover analog helper/label references — rather than as a literal repo-wide string ban. `values.yaml`'s `config.fieldGuideBaseUrl: http://field-guide-api` is the mandated functional default wiring launchpad to field-guide-api's in-cluster Service DNS name (per plan Task 1 action text: "replace ... `mongoDbName` with `fieldGuideBaseUrl` (default `http://field-guide-api`)"), not a copy-paste leftover. The load-bearing collision-guard criteria (helper renames, `_helpers.tpl` selectorLabels, no `mongodb.fullname`/`mongodb.selectorLabels`, rendered output never emitting `app.kubernetes.io/name: field-guide-api`) were all independently verified and pass.
- D-09 (manual deploy loop, no new Makefile targets) and D-08 (readinessProbe stays unweakened, NotReady accepted) were both honored exactly as scoped — no scope creep into Phase 10's Makefile work.

## Deviations from Plan

### Auto-fixed Issues

**1. [Interpretation, not a Rule 1-4 fix] Task 1 grep-gate literal vs. intent**
- **Found during:** Task 1 acceptance-criteria review (continuation agent, retrospective)
- **Issue:** The plan's automated verify command (`! grep -rq 'field-guide-api' .`) would technically fail against `values.yaml`'s `fieldGuideBaseUrl: http://field-guide-api` value, even though that value is explicitly mandated by the same task's `<action>` text.
- **Resolution:** No code change needed — the literal string is correct and required. Documented here so the apparent conflict between the automated verify command and the action text is not mistaken for an unresolved gate failure. The actual collision-prevention intent (helper renames, `_helpers.tpl`, rendered selector labels) was verified via `helm template` and passes cleanly with zero `app.kubernetes.io/name: field-guide-api` occurrences.
- **Files affected:** `charts/launchpad/values.yaml` (no modification — value already correct as authored in Task 1)
- **Verification:** `helm template launchpad charts/launchpad/ | grep 'app.kubernetes.io/name: field-guide-api'` returns nothing (see Self-Check below)

---

**Total deviations:** 1 (interpretation/documentation only, no code change)
**Impact on plan:** None on functionality. All gate intents (SC #1 collision guard, SC #4 RBAC shape, D-05/D-08/D-09) verified true against live rendered output and a live cluster deploy.

## Issues Encountered
None beyond the grep-gate interpretation documented above.

## Checkpoint Result (Task 3 — human-verify, D-09)

**Status:** APPROVED by operator (2026-07-12)

Verbatim outcome:
- `helm install launchpad charts/launchpad/` → `STATUS: deployed`
- `kubectl get pods -l app.kubernetes.io/name=launchpad -w` → `launchpad-555d88fcf8-n89ng   0/1   Running   0   6s`
- Pod phase `Running` with `READY 0/1` — expected and accepted per D-08 (launchpad's own MongoDB arrives in Phase 9 / DEP-03; `/health` returns 503 by design until then). The readinessProbe was NOT weakened to force a false-Ready state.
- ROADMAP SC #2 satisfied per D-09 (manual loop verification; `make build-launchpad`/`load-launchpad`/`deploy-launchpad` wrapper targets remain deferred to Phase 10 / DEP-04, intentionally not added in this plan).

## User Setup Required

None - no external service configuration required. The chart's `mongoUri` value is a local-dev placeholder only (`mongodb://localhost:27017/launchpad?serverSelectionTimeoutMS=2000`), not a real credential; real in-cluster MongoDB wiring arrives in Phase 9 (DEP-03).

## Next Phase Readiness
- DEP-01 and DEP-02 both satisfied: `charts/launchpad/` is a complete, lint-clean chart; the ServiceAccount/Role/RoleBinding are the live RBAC identity Plan 02's `cluster_state.py` (already committed) reads through in-cluster.
- Phase 08 is now fully complete (both 08-01 and 08-02 executed and summarized). ROADMAP SC #1–#4 for Phase 8 are satisfied; SC #5 (`_request_timeout=5` on all K8s API calls) was verified in 08-02.
- Phase 9 (Service Catalog + Events / MongoDB CRUD, DEP-03) will add `charts/launchpad/templates/mongodb/` — the `mongoUri` placeholder Secret value here will be superseded by real in-cluster Mongo wiring at that point.
- No blockers for Phase 9 or Phase 10.

---
*Phase: 08-helm-chart-k8s-diagnostics*
*Completed: 2026-07-12*

## Self-Check: PASSED

All 10 chart files under `charts/launchpad/` verified present on disk; both task commit hashes (98263d9, 039ad73) verified present in git log. `helm lint charts/launchpad/` re-run clean (0 errors, 0 warnings). `helm template launchpad charts/launchpad/` re-verified: no `app.kubernetes.io/name: field-guide-api`, `serviceAccountName: launchpad` present, `kind: Role`/`kind: RoleBinding`/`kind: ServiceAccount` present with no `kind: ClusterRole`, `POD_NAMESPACE` fieldRef present, readinessProbe `path: /health port: 8000` unweakened, `MONGO_URI` sourced only via `secretKeyRef`.
