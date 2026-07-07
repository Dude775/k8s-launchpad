---
phase: 03-containerization-helm-deployment
plan: 02
subsystem: helm-chart
tags: [helm, kubernetes, mongodb, secrets, chart]
requires:
  - phase: 02-cluster-infrastructure
    provides: kind cluster + localhost:5001 registry (image pull path for image.repository default)
provides:
  - Complete Helm chart at charts/field-guide-api/ (apiVersion v2, helm lint clean)
  - Generic values.yaml — the PRD-3 app-templating seam (HELM-04)
  - App Deployment/Service/ConfigMap/Secret templates with live-verified MONGO_URI shape
  - Embedded MongoDB (plain mongo:7 Deployment/Service/PVC/Secret) gated on mongodb.enabled
affects:
  - 03-04 (deploys and smoke-tests this chart live)
  - PRD-3 (values.yaml schema is the templating seam for new apps)
  - PRD-4 (metrics.enabled Prometheus scrape annotations)
tech-stack:
  added: []
  patterns:
    - Single-source-of-truth hostname helper (field-guide-api.mongodb.fullname used by BOTH mongodb Service name and app Secret URI host)
    - stringData Secrets (no manual base64)
    - readiness=/health httpGet, liveness=tcpSocket (never couple liveness to Mongo)
key-files:
  created:
    - charts/field-guide-api/Chart.yaml
    - charts/field-guide-api/values.yaml
    - charts/field-guide-api/.helmignore
    - charts/field-guide-api/templates/_helpers.tpl
    - charts/field-guide-api/templates/NOTES.txt
    - charts/field-guide-api/templates/deployment.yaml
    - charts/field-guide-api/templates/service.yaml
    - charts/field-guide-api/templates/configmap.yaml
    - charts/field-guide-api/templates/secret.yaml
    - charts/field-guide-api/templates/mongodb/deployment.yaml
    - charts/field-guide-api/templates/mongodb/service.yaml
    - charts/field-guide-api/templates/mongodb/pvc.yaml
    - charts/field-guide-api/templates/mongodb/secret.yaml
  modified: []
  deleted:
    - charts/field-guide-api/.gitkeep (intentional — replaced by real chart files)
decisions:
  - "mongodb templates quote image value (image: \"mongo:7\") — semantically identical, YAML-safe"
  - "mongodb resources carry app.kubernetes.io/component: mongodb label so selectors never overlap the app pods"
  - "Prometheus scrape annotations (not ServiceMonitor) as the PRD-4 seam — no CRDs in PRD-1"
metrics:
  tasks-completed: 3
  duration: ~35 min (including session reconnect)
  completed: 2026-07-06
---

# Phase 3 Plan 02: Helm Chart (app + embedded MongoDB) Summary

Hand-written Helm-3-compatible chart deploying the field-guide API with Secret-only MONGO_URI (`?authSource=admin`, DB-in-path) and an embedded plain mongo:7 Deployment sharing one hostname helper — helm lint clean, 8 resources rendered.

## What Was Built

- **Chart scaffold** — `Chart.yaml` (apiVersion v2, version 0.1.0), generic `values.yaml` (image.*, service.*, resources, metrics.enabled, config.*, mongodb.* with enabled toggle, `pullPolicy: IfNotPresent` locked per HELM-04), `.helmignore`, `NOTES.txt` (port-forward + curl usage, zero credentials printed).
- **_helpers.tpl** — standard name/fullname/labels/selectorLabels plus `field-guide-api.mongodb.fullname`: the single source of truth used by BOTH the mongodb Service `metadata.name` and the app Secret's URI hostname (RESEARCH.md Pitfall 9 — these can never drift).
- **App templates** — Deployment (env via secretKeyRef + configMapKeyRef, readinessProbe httpGet `/health:8000`, livenessProbe tcpSocket 8000, securityContext `runAsNonRoot`/`runAsUser: 10001`/`allowPrivilegeEscalation: false`, Prometheus annotations gated on `metrics.enabled`), ClusterIP Service 80→8000, ConfigMap (MONGO_DBNAME + FLASK_DEBUG only), Secret (`stringData` MONGO_URI).
- **MongoDB templates** — plain `mongo:7` Deployment (NOT StatefulSet — chart-owned PVC dies with `helm uninstall`), ClusterIP Service :27017, PVC (ReadWriteOnce 1Gi, `storageClassName` omitted when `storageClass: ""`), Secret (MONGO_INITDB_ROOT_* via stringData). All four gated on `{{- if .Values.mongodb.enabled }}`.

Rendered app Secret URI (live-verified shape from research): `mongodb://root:fieldguide-dev-password@field-guide-api-mongodb:27017/fieldguide?authSource=admin`

## Verification Results

- `helm lint charts/field-guide-api` — exit 0 (only INFO: icon recommended)
- `helm template` renders all 8 resources: 2 Deployments, 2 Services, 2 Secrets, 1 ConfigMap, 1 PVC
- No `kind: StatefulSet`, no Bitnami references, no `MONGO_URI` in the rendered ConfigMap
- mongodb Service name (`field-guide-api-mongodb`) equals the Secret URI host — same helper
- `--set mongodb.enabled=false` renders exactly 1 Deployment / 1 Service / 1 Secret / 1 ConfigMap / 0 PVC (all mongodb resources omitted)
- `--set mongodb.persistence.storageClass=fast` renders `storageClassName: "fast"`; empty default omits the field
- mongodb readinessProbe: `mongosh --quiet --eval "db.adminCommand('ping')"` (auth-free per live research)

## Deviations from Plan

None - plan executed exactly as written.

Note: task 3's suggested verification grep `image: mongo:7` did not match the rendered `image: "mongo:7"` (the template quotes the value). Verified with the substring pattern instead — the acceptance criterion (`contains: mongo:7`) is satisfied; no template change needed.

## Known Stubs

None — all templates are fully wired; live deployment happens in 03-04 as planned.

## Threat Flags

None — all security surface (values.yaml dev-default password, Secret-only MONGO_URI, ClusterIP-only exposure, non-root securityContext) matches the plan's threat model dispositions T-03-04 through T-03-07.

## Commits

| Task | Commit | Description |
| ---- | ------ | ----------- |
| 1 | 152fae5 | helm chart scaffold — Chart.yaml, values.yaml, helpers, NOTES |
| 2 | b508097 | app templates — deployment, service, configmap, secret |
| 3 | 05b5a81 | mongodb templates — deployment, service, pvc, secret |

## Self-Check: PASSED

- All 13 chart files exist on disk (verified via helm template rendering all sources)
- Commits 152fae5, b508097, 05b5a81 present on worktree branch
- helm lint exit 0; all must_haves truths verified against rendered output
