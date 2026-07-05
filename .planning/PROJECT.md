# k8s-launchpad

## What This Is

k8s-launchpad is a self-hosted Internal Developer Platform (IDP) — a "mini-Heroku" running on a local Kubernetes cluster. A developer registers a Git repo through a web dashboard; the platform automatically builds it (Docker), deploys it (Helm), syncs it via GitOps (ArgoCD), monitors it (Prometheus/Grafana/Loki), and scans it for vulnerabilities (Trivy), with a self-diagnostics engine that health-checks the platform's own components. Built as a portfolio piece to demonstrate platform-engineering-level thinking.

**This milestone (PRD-1) covers ONLY the foundation:** monorepo, a sample "field-guide" Flask API (the platform's dogfood app), containerization, a local kind cluster with local registry, and Helm deployment. Everything runs locally and free.

## Core Value

`make cluster-up && make build && make load && make deploy` produces a running, reachable app on a local kind cluster — the full local build-to-deploy loop works end to end.

## Requirements

### Validated

- [x] Working Flask field-guide API: REST CRUD for markdown-based DevOps knowledge entries (GET list, GET by id, POST create), MongoDB-backed — Validated in Phase 1: Scaffold + App + Tests
- [x] `/health` endpoint returns 200; `/metrics` exposes basic Prometheus-format metrics — Validated in Phase 1
- [x] Unit tests for API endpoints (pytest), passing via `make test` — Validated in Phase 1 (32 tests, 100% coverage, venv-based test target)
- [x] .gitignore covering .env, __pycache__, .venv, *.pyc, kubeconfig — in place BEFORE first meaningful commit — Validated in Phase 1 (first commit)
- [x] kind cluster config + script/Makefile target to spin it up with a local registry — Validated in Phase 2: live-verified end-to-end (clean-machine cluster-up, in-pod registry pull, idempotent re-run, double-safe teardown)

### Active

- [ ] Dockerfile producing a small, working image
- [ ] Helm chart deploying the app (Deployment, Service, ConfigMap, Secret template, values.yaml); app reachable locally
- [ ] MongoDB running in-cluster (Helm dependency or simple manifest)
- [ ] Makefile targets: cluster-up, cluster-down, build, load, deploy, test, clean — working under WSL2 / Git Bash (test done in Phase 1; cluster-up/cluster-down done in Phase 2)
- [ ] README documenting end-to-end local setup (clone → make cluster-up → make deploy → curl)

### Out of Scope

- ArgoCD / GitOps — deferred to PRD-2
- Platform dashboard / repo onboarding — deferred to PRD-3
- Prometheus/Grafana/Loki/Trivy deployment — deferred to PRD-4 (app exposes /metrics now as a seam)
- Any AWS/EKS/Terraform — deferred to final PRD; this milestone is local and free only

## Context

- Portfolio project for an AI Solutions Specialist demonstrating platform-engineering thinking; quality and readability matter as much as function.
- Multi-PRD project: PRD-1 (foundation) → PRD-2 (GitOps/ArgoCD) → PRD-3 (platform layer/dashboard) → PRD-4 (observability/security) → final PRD (AWS/EKS). PRD-1 must build clean seams, not implement future PRDs.
- **Seams to build (hooks only):**
  - App exposes `/metrics` so PRD-4 Prometheus can scrape it later
  - Helm chart `values.yaml` structured so PRD-3 can template new apps from it
  - Directory layout leaves room for `infra/argocd/` (PRD-2) and `infra/observability/` (PRD-4)
- Developer is on Windows using WSL2 / Git Bash; all `make` targets must work there.
- Target repo structure (monorepo): `apps/field-guide-api/` (src, tests, Dockerfile, requirements.txt), `charts/field-guide-api/`, `infra/kind/`, `scripts/`, `docs/`, `Makefile`, `.gitignore`, `README.md`.

## Constraints

- **Tech stack (LOCKED)**: Python 3.11 + Flask backend; MongoDB (local, containerized); Docker; kind (Kubernetes in Docker); local registry (kind's or a local Docker registry container); Helm 3; monorepo — do not re-ask or substitute
- **Budget**: Everything local and free — no cloud, no AWS in this milestone
- **Security**: .env for local config, Kubernetes Secrets in-cluster; NEVER commit real secrets; .gitignore before first meaningful commit
- **Platform**: Windows host with WSL2 / Git Bash — make targets and scripts must work in that environment
- **Git**: Many small human-style commits (lowercase, short messages)
- **Autonomy**: Operate autonomously on routine implementation choices; pause only for (a) cloud cost, (b) real credentials/secrets, (c) contradicting a locked decision. Record decisions in CONTEXT.md.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Flask + Python 3.11 for sample app | Locked in PRD; matches developer's primary stack | — Pending |
| MongoDB in-cluster | Locked in PRD; exercises Helm dependency/stateful workload | — Pending |
| kind for local cluster | Locked in PRD; free, disposable, CI-friendly | — Pending |
| Helm 3 packaging | Locked in PRD; values.yaml becomes template seam for PRD-3 | — Pending |
| Sample app = field-guide content API | Dogfood app that doubles as DevOps knowledge base content | — Pending |
| Horizontal Layers project mode | Infrastructure-heavy foundation PRD; layers (app → image → cluster → chart) map naturally to phases | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

## Current State

Phase 2 complete (2026-07-05) — idempotent kind cluster + registry:3 lifecycle live-verified end-to-end: `make cluster-up` self-verifies a host-push → in-pod-pull through the containerd hosts.toml mirror, re-runs cleanly, and `make cluster-down` tears down safely twice. A false-timeout in the verify-pod wait was fixed mid-verification (19642df). Code review: 1 Critical (kubectl context pinning) + 3 Warnings open — fix via `/gsd-code-review 2 --fix` before Phase 3 makes re-runs routine. Next: Phase 3 — containerization + Helm deployment.

---
*Last updated: 2026-07-05 after Phase 2 completion*
