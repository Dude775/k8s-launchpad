# k8s-launchpad

## What This Is

k8s-launchpad is a self-hosted Internal Developer Platform (IDP) — a "mini-Heroku" running on a local Kubernetes cluster. A developer registers a Git repo through a web dashboard; the platform automatically builds it (Docker), deploys it (Helm), syncs it via GitOps (ArgoCD), monitors it (Prometheus/Grafana/Loki), and scans it for vulnerabilities (Trivy), with a self-diagnostics engine that health-checks the platform's own components. Built as a portfolio piece to demonstrate platform-engineering-level thinking.

**PRD-1 (foundation) shipped as v1.0 on 2026-07-07:** monorepo, a sample "field-guide" Flask API (the platform's dogfood app), containerization, a local kind cluster with local registry, and Helm deployment — everything local and free. Now building PRD-3 (Product Dashboard / Local IDP UI) as v1.1 — deliberately ahead of PRD-2 (GitOps), presentation layer first.

## Core Value

`make cluster-up && make build && make load && make deploy` produces a running, reachable app on a local kind cluster — the full local build-to-deploy loop works end to end.

## Current Milestone: v1.1 Product Dashboard

**Goal:** Make k8s-launchpad visible as a product — a Flask-served browser dashboard that presents the platform as a local Internal Developer Platform, demoable to a human reviewer.

**Target features:**

- New platform app `apps/launchpad/` — separate Flask app with its own Dockerfile + Helm chart (platform/workload separation; reuses v1.0 chart patterns and the values.yaml templating seam)
- UI shell: landing/dashboard at `/`, sidebar/topbar, status cards — Jinja2 + vendored htmx (no CDN, no build step, no React/Vite)
- Real platform status API: API health, Mongo status, app/version info, service/demo state, metrics preview
- Service catalog page + launch/onboard form storing service registrations in MongoDB (no real deployment pipeline behind it)
- Diagnostics section: in-app checks (Mongo ping, self-health, config/version) plus read-only Kubernetes API queries via ServiceAccount RBAC, degrading gracefully outside the cluster — seed of the self-diagnostics engine
- Activity/events feed backed by simple persisted events in MongoDB
- README/demo updates: browser demo flow, screenshots plan
- Docker/Helm compatibility intact — dashboard deploys through the same `make` loop

**Out of scope for v1.1:** ArgoCD/GitOps (PRD-2), Prometheus/Grafana/Loki (PRD-4), EKS/Terraform/cloud, real deployment pipeline behind the onboard form.

## Requirements

### Validated

- [x] Working Flask field-guide API: REST CRUD for markdown-based DevOps knowledge entries (GET list, GET by id, POST create), MongoDB-backed — Validated in Phase 1: Scaffold + App + Tests
- [x] `/health` endpoint returns 200; `/metrics` exposes basic Prometheus-format metrics — Validated in Phase 1
- [x] Unit tests for API endpoints (pytest), passing via `make test` — Validated in Phase 1 (32 tests, 100% coverage, venv-based test target)
- [x] .gitignore covering .env, __pycache__, .venv, *.pyc, kubeconfig — in place BEFORE first meaningful commit — Validated in Phase 1 (first commit)
- [x] kind cluster config + script/Makefile target to spin it up with a local registry — Validated in Phase 2: live-verified end-to-end (clean-machine cluster-up, in-pod registry pull, idempotent re-run, double-safe teardown)
- [x] Dockerfile producing a small, working image — Validated in Phase 3: multi-stage python:3.11-slim, non-root UID 10001, gunicorn PID 1, live-verified in-cluster
- [x] Helm chart deploying the app (Deployment, Service, ConfigMap, Secret template, values.yaml); app reachable locally — Validated in Phase 3: helm lint clean, port-forward + curl 200 on /health, /entries, /metrics; code review Critical (service selector overlap) found and fixed
- [x] MongoDB running in-cluster (Helm dependency or simple manifest) — Validated in Phase 3: plain mongo:7 manifests embedded in chart, clean uninstall incl. PVC

- [x] Makefile developer CLI: cluster-up, cluster-down, build, load, deploy, test, clean + up/smoke/check-tools/port-forward, self-documenting `make help` — Validated in Phase 4 (v1.0): full loop + smoke live-verified in Git Bash, human-approved (WSL2 N/A on this machine)
- [x] README documenting end-to-end local setup (clone → make up → curl) — Validated in Phase 4 (v1.0): portfolio-grade README with Mermaid architecture, real captured output, plus docs/ troubleshooting, windows-setup, and known-limitations pages

### Active

v1.1 (Product Dashboard) requirements — being defined via /gsd-new-milestone; canonical list in .planning/REQUIREMENTS.md.

### Out of Scope

- ArgoCD / GitOps — deferred to PRD-2 (now scheduled after v1.1)
- Prometheus/Grafana/Loki/Trivy deployment — deferred to PRD-4 (app exposes /metrics now as a seam)
- Any AWS/EKS/Terraform — deferred to final PRD; everything stays local and free
- Real deployment pipeline behind the onboard form — v1.1 stores registrations only; wiring them to actual builds/deploys is a later PRD

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
| Flask + Python 3.11 for sample app | Locked in PRD; matches developer's primary stack | ✓ Good — 32 tests, 100% coverage, clean app factory |
| MongoDB in-cluster | Locked in PRD; exercises Helm dependency/stateful workload | ✓ Good — plain mongo:7 manifests, clean uninstall incl. PVC |
| kind for local cluster | Locked in PRD; free, disposable, CI-friendly | ✓ Good — survived Docker Desktop restart; idempotent re-runs |
| Helm 3 packaging | Locked in PRD; values.yaml becomes template seam for PRD-3 | ✓ Good — lint clean; generic values.yaml seam in place |
| Sample app = field-guide content API | Dogfood app that doubles as DevOps knowledge base content | ✓ Good |
| Horizontal Layers project mode | Infrastructure-heavy foundation PRD; layers (app → image → cluster → chart) map naturally to phases | ✓ Good — 4 phases, zero rework across layers |
| Plain mongo:7 manifests over Bitnami chart | Bitnami paywalled since Sep 2025; operator overkill for single instance | ✓ Good — avoided ImagePullBackOff on fresh clusters |
| registry:3 + per-node containerd hosts.toml | Canonical kind local-registry pattern; self-verifying push/pull at cluster-up | ✓ Good — wiring re-verified on every cluster-up |
| gunicorn-only serving (never Flask dev server) | SIGTERM handling for graceful pod termination | ✓ Good — non-root UID 10001, PID 1 exec-form |
| awk-powered self-documenting Makefile help | 15 targets discoverable via `make help` default goal | ✓ Good — README demo matches real output |
| PRD-3 (dashboard) before PRD-2 (GitOps) | v1.0 proved the backend loop; missing layer is presentation — make the platform demoable in a browser first | — Pending (v1.1) |
| Dashboard = separate platform app `apps/launchpad/` | Platform/workload separation — field-guide API stays the dogfood workload; exercises v1.0 values.yaml templating seam | — Pending (v1.1) |
| Jinja2 + vendored htmx for dashboard UI | Flask-first, no React/Vite, no CDN/build step; hypermedia fragments for live status cards and forms | — Pending (v1.1) |
| Diagnostics via in-app checks + read-only K8s API (ServiceAccount RBAC) | Seed of the self-diagnostics engine; degrades gracefully outside the cluster | — Pending (v1.1) |

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

**v1.0 Foundation shipped 2026-07-07.** The full local build-to-deploy loop works end to end: `make up` (cluster-up → build → load → deploy) produces a running Flask field-guide API on kind, backed by in-cluster MongoDB, confirmed by `make smoke` (200 on /health, /entries, /metrics) and human sign-off. Codebase: ~1,360 LOC of app/chart/script source, 32 tests at 100% coverage, 114 commits over 4 days. All PRD-2/3/4 seams in place: `/metrics` endpoint, generic values.yaml, `infra/argocd/` and `infra/observability/` directories.

**v1.1 COMPLETE (all phases 5–10 done, 2026-07-14).** Phase 10 delivered the Makefile integration + demo docs that close the milestone's core value: `make up-all` brings up the kind cluster and both apps in one command (verified live, exit 0 with reviewer-guiding epilogue), `make smoke-all` proves both apps (all endpoints 200, verified live), `make verify-ttl` confirms the events TTL index in-cluster, and the README now headlines the browser demo with five real captured screenshots (docs/screenshots/) plus launchpad-specific troubleshooting and known-limitations docs. DEP-04, DEP-05, DOCS-01 validated (verification 16/16 must-haves). Phase 10 code review logged 1 critical + 5 warnings for follow-up (10-REVIEW.md): notably `TTL_DEEP=1` deep mode can never pass against the 7-day TTL (CR-01) and known-limitations.md overstates it as closing the FEED-03 live-verify flag.

**v1.1 progress:** Phases 5–9 complete. Phase 8 delivered the launchpad Helm chart with least-privilege RBAC and the K8s diagnostics panel. Phase 9 (Service Catalog + Events / MongoDB CRUD) delivered the full catalog UX — register/view/deregister services via CSRF-protected forms, service detail pages, and a TTL-bounded events feed polling via htmx — backed by launchpad's own in-cluster MongoDB (DEP-03 manifests mirrored from field-guide-api). CAT-01..05, FEED-01..03, DEP-03 validated (verification passed 7/7 after CR-01 gap closure: naive-datetime normalization + tz_aware=True so relative times render real values against real MongoDB). Launchpad suite at 128 tests / 100% coverage.

Known tech debt: README /health example shows compact JSON while Flask emits spaced JSON (cosmetic); MongoDB runs with a committed local-dev password (acceptable for local kind only, warned in NOTES.txt); the launchpad chart's `mongoUri` default (`charts/launchpad/values.yaml:72`) embeds a local-dev hostname and credentials as committed defaults (WR-01, Phase 9 review/verification) — accepted for local kind only, override with `--set mongoUri=...` for anything real. (The status-card `--ok/--degraded/--unknown` CSS modifiers previously listed here as an open WR-01 gap were FIXED in Phase 7, commit `c977206` — `apps/launchpad/app/static/style.css:101-109`.)

## Next Milestone Goals

After v1.1 (PRD-3 Product Dashboard): PRD-2 GitOps — ArgoCD syncs deployments from Git (GITOPS-01). Later: PRD-4 observability/security, final PRD AWS/EKS.

---
*Last updated: 2026-07-14 — Phase 10 (Makefile Integration + Smoke + Docs) complete; v1.1 milestone execution finished*
