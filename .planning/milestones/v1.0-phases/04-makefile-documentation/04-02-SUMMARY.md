---
phase: 04-makefile-documentation
plan: "02"
subsystem: documentation
tags: [readme, docs, portfolio, mermaid, troubleshooting, windows-setup, known-limitations]
dependency_graph:
  requires: [04-01]
  provides: [DOCS-01, readme-portfolio-entry-point, docs-three-deep-dive-pages]
  affects: [README.md, docs/troubleshooting.md, docs/windows-setup.md, docs/known-limitations.md]
tech_stack:
  added: []
  patterns:
    - Mermaid graph LR diagram in GitHub-rendered README
    - Symptom-cause-fix troubleshooting table pattern
    - PRD-seam documentation (argocd/observability directory stubs explained)
    - WR-07 dev-password guard consistent with NOTES.txt wording
key_files:
  modified:
    - README.md
  created:
    - docs/troubleshooting.md
    - docs/windows-setup.md
    - docs/known-limitations.md
decisions:
  - "README uses 'Helm' (not 'Helm 3') in Architecture section — installed version is Helm 4"
  - "Demo flow Prometheus output is representative (python_gc_*, flask_exporter_info) matching 03-VERIFICATION; not fabricated"
  - "docs/ pages use relative links back to each other and to README for navigability"
metrics:
  duration: "724s"
  completed: "2026-07-07"
  tasks_completed: 2
  files_modified: 4
---

# Phase 4 Plan 02: README + Documentation Summary

**One-liner:** Rewrote README.md as a portfolio-grade entry point with Mermaid architecture diagram, real terminal output, and security note; populated the empty docs/ directory with three linked deep-dive pages covering troubleshooting, Windows setup, and known limitations.

## What Was Built

### Task 1: README.md rewrite

The 16-line stub was replaced with a 170-line portfolio-grade document containing:

1. **Hook paragraph** — positions k8s-launchpad as a self-hosted IDP / mini-Heroku; states PRD-1 scope clearly.
2. **`## Architecture`** — Mermaid `graph LR` diagram: Developer → Makefile → `localhost:5001 registry` → kind cluster → Helm → app pod + MongoDB pod.
3. **`## What This Proves`** — 6-bullet portfolio signal list (local Kubernetes, build-to-deploy loop, GitOps/observability/template seams, self-documenting DX).
4. **`## Prerequisites`** — Table (Docker Desktop, kind, Helm, kubectl, make) with a `make check-tools` verification step and a link to `docs/windows-setup.md`.
5. **`## Quickstart`** — `git clone → make check-tools → make up → make smoke` with real captured `make smoke` PASS output from 04-01/03-VERIFICATION.
6. **`## Developer Loop`** — `make test → build → load → deploy → smoke`; points to `make help`.
7. **`## Demo Flow`** — copy-paste session: `kubectl port-forward svc/field-guide-api 8080:80` + three curl commands with real responses from 03-VERIFICATION (`{"status":"ok","mongo":"up"}`, `[]`, Prometheus text). Screenshots-planned checklist for future PRDs.
8. **`## Repository Layout`** — absorbed from the original README (all rows preserved including `infra/argocd/` and `infra/observability/` seams).
9. **`## Security Note`** — `fieldguide-dev-password` warning consistent with NOTES.txt; `--set mongodb.auth.password` override command.
10. **`## Known Limitations & Roadmap`** — one-line summary linking `docs/known-limitations.md`.
11. **`## Troubleshooting`** — one-line summary linking `docs/troubleshooting.md`.

### Task 2: Three docs/ deep-dive pages

**`docs/troubleshooting.md`** (23 lines)
- Symptom → Likely Cause → Fix table with 10 rows
- Covers: kind/Docker not on PATH, Docker daemon not running, `ImagePullBackOff` on registry-verify pod, `bad interpreter: No such file or directory` (CRLF), `/health` 503 (MongoDB not ready), stale port-forward / `make smoke` timing, image not pushed before deploy, registry not connected to kind network

**`docs/windows-setup.md`** (105 lines)
- Git Bash as primary path with `winget install` commands for all four tools
- `MSYS_NO_PATHCONV=1` explanation (Git Bash `//` path-conversion bug, already set in Makefile header)
- `.gitattributes` LF enforcement rationale and `core.autocrlf` fix procedure
- WSL2 as optional/secondary path with Linux install commands and Docker Desktop integration note

**`docs/known-limitations.md`** (64 lines)
- 9 limitation items derived from REQUIREMENTS.md Out-of-Scope table and 03-VERIFICATION
- Covers: no ArgoCD (PRD-2), no dashboard (PRD-3), no observability stack (PRD-4), port-forward only, ephemeral kind PVC, committed dev password (`fieldguide-dev-password`) with override command, cosmetic gunicorn `/home/app` warning (harmless, deferred), no RBAC, no cloud

## Verification Results

| Check | Result |
|-------|--------|
| README has `mermaid` fenced block with `graph LR` | PASS |
| README has all 10 required section headings | PASS |
| README contains `make check-tools`, `make up`, `make smoke` | PASS |
| README contains `{"status":"ok","mongo":"up"}` and port-forward command | PASS |
| README contains `fieldguide-dev-password` and `--set mongodb.auth.password` override | PASS |
| README links to `docs/troubleshooting.md` and `docs/known-limitations.md` | PASS |
| README preserves `infra/argocd/` and `infra/observability/` layout rows | PASS |
| No `Helm 3` string in architecture section | PASS |
| README line count (min 90) | PASS (170 lines) |
| `docs/troubleshooting.md` exists with `| Symptom |` table, `ImagePullBackOff`, `bad interpreter`, `503` | PASS |
| `docs/windows-setup.md` exists with `MSYS_NO_PATHCONV`, `Git Bash`, `WSL2` | PASS |
| `docs/known-limitations.md` exists with `fieldguide-dev-password`, `PRD-2`, `PRD-4`, `port-forward`, gunicorn `/home/app` | PASS |
| docs/ min line counts (15/20/15) | PASS (23/105/64) |
| No stubs or placeholder text in any file | PASS |

## Deviations from Plan

None — plan executed exactly as written.

The only minor note: the plan listed `## Known Limitations & Roadmap` as the heading;
the README uses this exact heading, satisfying the acceptance criteria for links to `docs/known-limitations.md`.

## Known Stubs

None. All content is substantive:
- Demo output is verbatim from `03-VERIFICATION.md` and `NOTES.txt`
- Prometheus snippet is representative (matches what prometheus-flask-exporter 0.23.2 produces)
- The "Screenshots (planned)" checklist in Demo Flow is explicitly deferred documentation, not a functional stub

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced.
Documentation-only changes. Threat mitigations applied per plan threat model:

| Threat | Mitigation Applied |
|--------|-------------------|
| T-04-05: dev password presented as acceptable production practice | Security Note + known-limitations both state `fieldguide-dev-password` is local-kind-only; `--set` override documented |
| T-04-06: docs instructing users to expose beyond localhost | README/demo document only `kubectl port-forward ... 8080:80`; known-limitations explicitly notes no Ingress/TLS |
| T-04-07: docs omitting destructive nature of reset-local | known-limitations + README describe `make reset-local` (and `make cluster-down`) as data-destroying; `make clean` documented as safe/cache-only |

## Self-Check: PASSED

| Item | Status |
|------|--------|
| README.md exists and is 170 lines | FOUND |
| docs/troubleshooting.md exists | FOUND |
| docs/windows-setup.md exists | FOUND |
| docs/known-limitations.md exists | FOUND |
| 04-02-SUMMARY.md exists | FOUND |
| 1e5c962 (task 1 commit) | FOUND |
| e5701a8 (task 2 commit) | FOUND |
