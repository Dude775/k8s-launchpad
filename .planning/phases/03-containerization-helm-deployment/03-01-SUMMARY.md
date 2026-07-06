---
phase: 03-containerization-helm-deployment
plan: "01"
subsystem: containerization
tags: [docker, dockerfile, multi-stage, gunicorn, non-root, security]
dependency_graph:
  requires: []
  provides: [localhost:5001/field-guide-api:dev image, apps/field-guide-api/Dockerfile, apps/field-guide-api/.dockerignore]
  affects: [03-02-PLAN.md (Helm chart image ref), 03-03-PLAN.md (build + push loop), 03-04-PLAN.md (deploy loop)]
tech_stack:
  added: []
  patterns: [multi-stage Dockerfile (builder/runtime split), numeric non-root UID (10001), exec-form CMD for PID 1 gunicorn, .dockerignore allowlist for Windows host build contexts]
key_files:
  created:
    - apps/field-guide-api/Dockerfile
    - apps/field-guide-api/.dockerignore
  modified: []
decisions:
  - "exec-form CMD (JSON array) chosen over shell form so gunicorn is PID 1 and receives SIGTERM directly — shell form would swallow SIGTERM, causing 30s force-kill on every K8s rollout"
  - "workers=1 + threads=4: single worker keeps prometheus-flask-exporter per-process registry correct; threads handle concurrent /health + request overlap"
  - "numeric USER 10001: named USER app is not verifiable by Kubernetes runAsNonRoot: true at the kubelet level; numeric UID is kubelet-verifiable"
  - ".dockerignore defense-in-depth: both .dockerignore (context exclusion) and explicit COPY allowlist (app/ + wsgi.py only) defend against Windows .venv leaking into the image"
metrics:
  duration: "~8 minutes"
  completed: "2026-07-06T11:01:18Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 0
---

# Phase 03 Plan 01: Dockerfile + .dockerignore Summary

**One-liner:** Multi-stage `python:3.11-slim` image with numeric non-root UID 10001, exec-form gunicorn CMD targeting `wsgi:app`, and a `.dockerignore` that excludes the 100MB+ Windows `.venv` from the build context.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Author .dockerignore (build-context allowlist) | 98b1d22 | apps/field-guide-api/.dockerignore |
| 2 | Author multi-stage Dockerfile (non-root, gunicorn) | 4508efd | apps/field-guide-api/Dockerfile |

## Verification Results

All acceptance criteria passed:

- `docker build -t localhost:5001/field-guide-api:dev apps/field-guide-api` exited 0
- `docker run --rm localhost:5001/field-guide-api:dev id -u` printed `10001`
- Dockerfile contains two `FROM python:3.11-slim` lines (confirmed multi-stage)
- `grep gunicorn Dockerfile` succeeds; no `flask run` reference present
- CMD is exec-form JSON array: `["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "4", ...]`
- Build context transfer was ~9.85 kB (`.venv/` excluded correctly by `.dockerignore`)
- `.dockerignore` contains exact lines: `.venv/`, `.pytest_cache/`, `__pycache__/`, `**/__pycache__/`, `*.pyc`, `.coverage`, `.env`, `tests/`

## Deviations from Plan

None — plan executed exactly as written. Dockerfile follows Pattern 1 from 03-RESEARCH.md verbatim. `.dockerignore` follows Pattern 2 verbatim.

## Known Stubs

None. Both files are fully wired production artifacts — no placeholder content.

## Threat Flags

No new threat surface beyond what the plan's threat model already covers:

| Threat ID | Mitigation Applied |
|-----------|--------------------|
| T-03-01 (Elevation of Privilege) | `groupadd -r -g 10001 app && useradd -r -u 10001 -g app app` + `USER 10001` numeric directive in Dockerfile |
| T-03-02 (Tampering / build context) | `.dockerignore` excludes `.venv/`; Dockerfile COPYs only `app/` + `wsgi.py` |
| T-03-03 (Information Disclosure / FLASK_DEBUG) | No `FLASK_DEBUG` ENV in Dockerfile; no `flask run` reference anywhere |

## Self-Check: PASSED

- `apps/field-guide-api/.dockerignore` FOUND
- `apps/field-guide-api/Dockerfile` FOUND
- Commit 98b1d22 FOUND (`chore(03-01): add .dockerignore for field-guide-api`)
- Commit 4508efd FOUND (`feat(03-01): add multi-stage Dockerfile for field-guide-api`)
