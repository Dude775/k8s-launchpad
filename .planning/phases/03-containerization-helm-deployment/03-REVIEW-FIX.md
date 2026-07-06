---
phase: 03-containerization-helm-deployment
fixed_at: 2026-07-07T00:00:00Z
review_path: .planning/phases/03-containerization-helm-deployment/03-REVIEW.md
iteration: 1
findings_in_scope: 8
fixed: 8
skipped: 0
status: all_fixed
---

# Phase 03: Code Review Fix Report

**Fixed at:** 2026-07-07T00:00:00Z
**Source review:** .planning/phases/03-containerization-helm-deployment/03-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 8 (1 Critical, 7 Warning; fix_scope=critical_warning, 6 Info findings out of scope)
- Fixed: 8
- Skipped: 0

**Verification performed:**
- `helm lint charts/field-guide-api` — 0 failures after every fix and at the end
- `helm template test charts/field-guide-api` — full render OK; app Service selector (`name=field-guide-api`) confirmed to no longer subset-match the mongodb pod labels (`name=field-guide-api-mongodb`)
- `helm template --set mongodb.enabled=false` fails fast without `externalMongoUri`, renders the external URI when supplied
- `make test PYTHON="py -3.12"` — 32 passed, 100% coverage (95% threshold met)

## Fixed Issues

### CR-01: API Service selector also matches the MongoDB pod

**Files modified:** `charts/field-guide-api/templates/_helpers.tpl`, `charts/field-guide-api/templates/mongodb/deployment.yaml`, `charts/field-guide-api/templates/mongodb/service.yaml`, `charts/field-guide-api/templates/deployment.yaml`
**Commit:** 4223b4f
**Applied fix:** Added a dedicated `field-guide-api.mongodb.selectorLabels` helper with a distinct identity (`app.kubernetes.io/name: field-guide-api-mongodb` + instance) and used it in the mongodb Deployment `matchLabels`, pod template labels, and mongodb Service selector (also resolves IN-03's triplicated inline labels). `app.kubernetes.io/component: mongodb` kept as a non-selector pod label; added `app.kubernetes.io/component: api` as a non-selector label on the app pod template. Rendered output verified: app Service Endpoints can now only match API pods. Selector immutability was not a concern (release uninstalled, chart pre-release).

### WR-01: `mongodb.enabled: false` rendered a broken MONGO_URI

**Files modified:** `charts/field-guide-api/templates/secret.yaml`, `charts/field-guide-api/values.yaml`
**Commit:** e9482a3
**Applied fix:** Added top-level `externalMongoUri: ""` value (commented as the PRD-3 external-DB seam) and branched `secret.yaml`: when `mongodb.enabled=false`, `MONGO_URI` comes from `required "..." .Values.externalMongoUri` — render fails fast with a clear message if the flag is set without a URI. Verified all three modes render/fail as intended.

### WR-02: MongoDB credentials interpolated into URI without URL-encoding

**Files modified:** `charts/field-guide-api/templates/secret.yaml`
**Commit:** b3f35ae
**Applied fix:** Piped `mongodb.auth.username` and `mongodb.auth.password` through `urlquery` in the in-chart MONGO_URI. Verified: `p@ss:w/rd?%25` renders as `p%40ss%3Aw%2Frd%3F%2525`; default dev password renders unchanged.

### WR-03: No checksum annotations — config/secret changes did not restart app pods

**Files modified:** `charts/field-guide-api/templates/deployment.yaml`
**Commit:** ee0dfbc
**Applied fix:** Restructured the pod-template `annotations:` block so it always exists: `checksum/config` and `checksum/secret` (sha256 of the rendered templates) are unconditional; the prometheus.io annotations remain inside the `metrics.enabled` guard. Verified the checksum changes when `config.flaskDebug` changes and that the block renders correctly with metrics disabled.

### WR-04: MongoDB Deployment defaulted to RollingUpdate — upgrade deadlock on RWO PVC

**Files modified:** `charts/field-guide-api/templates/mongodb/deployment.yaml`
**Commit:** 43b4c84
**Applied fix:** Added `strategy: {type: Recreate}` with a comment explaining the mongod.lock / RWO surge deadlock and data-integrity hazard.

### WR-05: `make deploy` silently ignored IMAGE/TAG

**Files modified:** `Makefile`
**Commit:** a1562b4
**Applied fix:** `deploy` now passes `--set image.repository=$(IMAGE) --set image.tag=$(TAG)` to `helm upgrade --install`, coordinating build/load/deploy on the same coordinates. Verified via `make -n deploy TAG=v1.0`.

### WR-06: /health hung 30s on Mongo outage — readiness 503 path was dead code

**Files modified:** `charts/field-guide-api/templates/secret.yaml`, `charts/field-guide-api/templates/deployment.yaml`
**Commit:** 7b52383
**Applied fix:** Appended `&serverSelectionTimeoutMS=2000` to the in-chart MONGO_URI and set `timeoutSeconds: 3` on the readiness probe (probe timeout > ping timeout, so /health returns its designed 503). Applicability confirmed against app source first: the app binds Flask-PyMongo from `MONGO_URI` (app/config.py, app/extensions.py) and `serverSelectionTimeoutMS` is a native PyMongo URI option — chart-only change, no app modification, no dead config. The external `externalMongoUri` path is left untouched (user-supplied URI owns its own options).

### WR-07: Committed dev password had no guard rail

**Files modified:** `charts/field-guide-api/templates/NOTES.txt`
**Commit:** f82f42e
**Applied fix:** Added a conditional WARNING block to NOTES.txt that prints on every install/upgrade when `mongodb.enabled` and the password equals the committed dev default, with the exact `--set mongodb.auth.password=<real-password>` remediation. **Design note:** the reviewer's "preferred" hard-fail opt-in (`fail` unless `allowDevPassword=true`) was deliberately NOT chosen — it would break the phase Core Value (`make deploy` working out of the box with committed defaults) and make plain `helm lint`/`helm template` fail. The NOTES.txt warning is one of the reviewer's explicitly listed acceptable options. If a hard guard is wanted for PRD-3, revisit when the chart is templatized. Verified the warning renders with the default password and disappears with an overridden one.

## Skipped Issues

None.

## Out of Scope (fix_scope=critical_warning)

IN-01 through IN-06 were not addressed in this pass. Note: IN-03 (duplicated mongodb selector labels) was resolved as a side effect of the CR-01 fix, per the reviewer's own note.

---

_Fixed: 2026-07-07T00:00:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
