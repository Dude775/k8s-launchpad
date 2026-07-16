# k8s-launchpad

## What This Is

k8s-launchpad is a self-hosted Internal Developer Platform (IDP) — a "mini-Heroku" running on a local Kubernetes cluster. A developer registers a Git repo through a web dashboard; the platform automatically builds it (Docker), deploys it (Helm), syncs it via GitOps (ArgoCD), monitors it (Prometheus/Grafana/Loki), and scans it for vulnerabilities (Trivy), with a self-diagnostics engine that health-checks the platform's own components. Built as a portfolio piece to demonstrate platform-engineering-level thinking.

**PRD-1 (foundation) shipped as v1.0 on 2026-07-07:** monorepo, a sample "field-guide" Flask API (the platform's dogfood app), containerization, a local kind cluster with local registry, and Helm deployment. **PRD-3 (Product Dashboard) shipped as v1.1 on 2026-07-14:** the `apps/launchpad/` browser dashboard that makes the platform visible as a product — status cards, service catalog, K8s diagnostics, activity feed — deployed alongside the field-guide workload. Everything local and free. Next: v2.0 — PRD-4 observability (Prometheus/Grafana) + Mission Control UI, pulled ahead of PRD-2 (GitOps/ArgoCD).

## Core Value

`make up-all` brings up the kind cluster and both apps (field-guide-api + launchpad dashboard) in one command — the platform is demoable to a human reviewer in a browser at `localhost:8081`.

## Current Milestone: v2.0 Observability + Mission Control

**Goal:** Turn k8s-launchpad from a static live-state dashboard into a real observability platform with a control-room UI — fill the reserved `infra/observability/` seam (PRD-4) and reskin launchpad to "launch to air" portfolio quality, strictly additively.

**Target features:**
- Trimmed kube-prometheus-stack via Helm on kind (operator + Prometheus + Grafana + kube-state-metrics; Alertmanager and node-exporter disabled), wired into `infra/observability/`
- ServiceMonitors in `infra/observability/` scraping the existing `/metrics` endpoints of field-guide-api and launchpad — zero changes to existing charts
- Grafana dashboards-as-code (uptime %, request latency, error rate per service) provisioned via sidecar ConfigMaps
- Mission Control skin: Pico dark scheme + custom `mission-control.css` layer (Flask/Jinja/htmx, vendored assets, no build step); hero "All Systems Online" card, service health cards
- Native metric cards fed by launchpad querying the Prometheus HTTP API, with "Open in Grafana" deep links; dimmed "NO SIGNAL" panels when observability isn't installed
- `make seed-demo`: idempotent API-driven demo seeding so first load is never an empty state
- Additive Makefile targets: `observability-up` / `observability-down` / `port-forward-grafana` / `seed-demo` + umbrella `up-mission-control` with a matching smoke target

**Hard constraint (ADDITIVE ONLY, non-negotiable):** nothing from v1.1 is deleted, rewritten, or behavior-changed — all existing Makefile targets, charts, routes, and API contracts keep working exactly as they do now, and v1.1 smoke tests pass unchanged.

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

- ✓ `apps/launchpad/` Flask platform app with app factory, env config, lazy no-kubeconfig K8s client (APP-01, APP-02) — v1.1, 128 tests / 100% coverage
- ✓ Browser dashboard UI shell with sidebar nav, live status cards, vendored htmx/Pico assets — fully offline (UI-01..05) — v1.1
- ✓ Platform status contract: `/api/status` aggregation, field-guide reachability degradation, own-Mongo `/health` readiness, `/metrics` parity (STAT-01..04) — v1.1
- ✓ Service catalog: register / view / detail / deregister with CSRF-protected server-side validation (CAT-01..05) — v1.1
- ✓ Diagnostics page: in-app checks + read-only K8s state via least-privilege RBAC, graceful outside-cluster degradation (DIAG-01..02) — v1.1
- ✓ TTL-bounded activity/events feed written by platform actions (FEED-01..03) — v1.1
- ✓ `charts/launchpad/` Helm chart with RBAC + own in-cluster mongo:7; namespaced `make` targets; `make up-all` + `smoke-launchpad` end-to-end (DEP-01..05) — v1.1
- ✓ README headlines the browser demo with five real screenshots (DOCS-01) — v1.1

### Active

v2.0 Observability + Mission Control requirements — being defined in .planning/REQUIREMENTS.md. Categories: observability stack (Prometheus/Grafana on kind), metrics scraping of existing /metrics seams, Grafana dashboards-as-code, Mission Control UI reskin, native metric cards with graceful degradation, demo seeding, additive Makefile targets.

### Out of Scope

- Loki / log aggregation — deferred to v2.1 (resource budget; v2.0 is metrics-only)
- Alertmanager and node-exporter — disabled in the trimmed kube-prometheus-stack (resource-heavy env; node-exporter flaky on Docker Desktop kind nodes)
- Iframe-embedded Grafana panels in launchpad — native Prometheus-fed cards + deep links chosen instead (iframes break without port-forward and clash with the skin)
- Trivy vulnerability scanning — remains deferred (later PRD-4 scope)
- PRD-2 GitOps/ArgoCD — explicitly reordered AFTER v2.0 (GITOPS-01 still deferred)
- Any AWS/EKS/Terraform — deferred to final PRD; everything stays local and free
- Real deployment pipeline behind the onboard form — v1.1 stores registrations only; wiring them to actual builds/deploys is a later PRD (PLAT-01)
- Authentication / multi-user — local single-user platform
- Edit an existing service registration — v1.1 shipped register/view/deregister only; revisit if PRD-2+ needs it

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
| PRD-3 (dashboard) before PRD-2 (GitOps) | v1.0 proved the backend loop; missing layer is presentation — make the platform demoable in a browser first | ✓ Good — v1.1 shipped a human-demoable product in 7 days; GitOps now has a UI to surface into |
| Dashboard = separate platform app `apps/launchpad/` | Platform/workload separation — field-guide API stays the dogfood workload; exercises v1.0 values.yaml templating seam | ✓ Good — zero changes to field-guide-api chart; both charts install into one namespace without collision |
| Jinja2 + vendored htmx for dashboard UI | Flask-first, no React/Vite, no CDN/build step; hypermedia fragments for live status cards and forms | ✓ Good — fully offline render, HX-Request fragment/full-page branch, zero JS build tooling |
| Diagnostics via in-app checks + read-only K8s API (ServiceAccount RBAC) | Seed of the self-diagnostics engine; degrades gracefully outside the cluster | ✓ Good — all three failure branches (outside-cluster/403/unreachable) tested; never 500s |
| `/health` checks only launchpad's own MongoDB | readinessProbe must never couple to downstream services; `/api/status` owns downstream checks | ✓ Good — readiness contract established in Phase 7 before the Phase 8 probe was written |
| Lazy K8s client init, `(None, None)` disabled signal | App and tests must load with no kubeconfig; established in Phase 5 before any route existed | ✓ Good — hermetic 128-test suite runs with no cluster |
| Separate in-cluster mongo:7 per chart (no shared instance) | Each chart stays independently installable/uninstallable | ✓ Good — TTL index created before first event write; launchpad pod Ready 1/1 |
| Module-attribute import discipline (`from app import k8s`) | Keeps conftest monkeypatch fixtures reaching helpers | ✓ Good — reused across Phases 8-9 without test friction |
| v2.0 = PRD-4 observability before PRD-2 GitOps | Operator's call: portfolio flagship needs production-grade telemetry + control-room UI; GitOps gains a richer surface to sync into | Pending (v2.0) |
| Trimmed kube-prometheus-stack (no Alertmanager/node-exporter) | Resource-heavy local env; keeps operator + ServiceMonitor CRD workflow while cutting ~40% footprint | Pending (v2.0) |
| ServiceMonitors live in infra/observability/, not in app charts | Strictest reading of additive-only — zero changes to v1.1 charts | Pending (v2.0) |
| Native Prometheus-fed metric cards over Grafana iframes | Degrades gracefully without port-forward; keeps vendored/no-CDN philosophy; "Open in Grafana" deep links for drill-down | Pending (v2.0) |
| Mission Control skin = Pico dark + mission-control.css layer | Lowest regression risk to existing pages/forms; no build step | Pending (v2.0) |
| Grafana dashboards-as-code via sidecar ConfigMaps | Reproducible on fresh clusters; strongest portfolio signal | Pending (v2.0) |
| Demo seeding via idempotent `make seed-demo` through existing APIs | Zero app-code changes; platform actions populate the activity feed naturally | Pending (v2.0) |

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

**v2.0 Phase 11 (Observability Stack Install) complete 2026-07-16** — verified 14/14 must-haves (OBS-01, OBS-02). Trimmed kube-prometheus-stack (chart 87.16.1: Prometheus Operator + Prometheus + Grafana + kube-state-metrics; Alertmanager/node-exporter/kubeadm jobs disabled) installs into the `observability` namespace via `scripts/observability-up.sh` with every kept-enabled component resource-bounded (~516 MiB total requests; D-09 kube-state-metrics gap closed live: 32Mi/10m, Burstable QoS), and tears down via `scripts/observability-down.sh` (namespace deleted, 10 monitoring CRDs retained per D-01). Both v1.1 apps survived three full install→teardown lifecycles with zero restarts. Certified end state: torn down. Next: Phase 12 ServiceMonitor scraping.

**v1.1 Product Dashboard shipped 2026-07-14** (milestone audit passed 27/27 requirements, 4/4 E2E flows). `make up-all` brings up the kind cluster and deploys both apps in one command; the launchpad dashboard at `localhost:8081` shows live status cards, a service catalog with full register/view/deregister CRUD, a K8s diagnostics panel, and a TTL-bounded activity feed — verified live with five real screenshots and human sign-off. Two Flask workloads (field-guide-api: 32 tests, launchpad: 128 tests, both 100% coverage), two independent Helm charts each with its own in-cluster mongo:7, 142 commits over 7 days (v1.0..v1.1: +21,464/−1,477 across 149 files).

**v1.0 Foundation shipped 2026-07-07.** Full local build-to-deploy loop: `make up` produces a running Flask field-guide API on kind with local registry, backed by in-cluster MongoDB, confirmed by `make smoke`. All PRD-2/4 seams in place: `/metrics` endpoints on both apps, generic values.yaml, `infra/argocd/` and `infra/observability/` directories.

Known tech debt (all tracked, non-blocking): 6 INFO/WARNING items in milestones/v1.1-MILESTONE-AUDIT.md (verify-ttl grep/pod-selection precision, README mermaid diagram omits launchpad, fixed sleep in smoke targets, .env.example missing EVENTS_TTL_SECONDS, duplicated blueprint import surfaces). Accepted risks in docs/known-limitations.md: committed local-dev MongoDB passwords/mongoUri defaults (local kind only — override for anything real); TTL expiry timing verified live-only (`make verify-ttl`, deep mode via `TTL_DEEP=1`).

## Next Milestone Goals

After v2.0: v2.1 Loki/log aggregation (deferred from v2.0), then PRD-2 GitOps — ArgoCD syncs deployments from Git (GITOPS-01) with the Mission Control UI surfacing sync state — then Trivy/security (rest of PRD-4), then final PRD AWS/EKS.

---
*Last updated: 2026-07-16 — Phase 11 (Observability Stack Install) complete, verified 14/14*
