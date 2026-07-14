# Milestones

## v1.1 Product Dashboard (Shipped: 2026-07-14)

**Delivered:** The platform is now demoable as a product — `make up-all` brings up the kind cluster and both apps in one command, and a browser at `localhost:8081` shows the launchpad dashboard: live status cards, service catalog CRUD, Kubernetes diagnostics, and a TTL-bounded activity feed. Verified live with human-approved screenshots.

**Stats:** 6 phases, 14 plans, 36 tasks, 142 commits, 149 files changed (+21,464/−1,477) · Timeline: 2026-07-08 → 2026-07-14 (7 days)

**Key accomplishments:**

- New `apps/launchpad/` Flask platform app — app factory, env-driven config, lazy K8s client that loads with no kubeconfig — with a hermetic 128-test suite at 100% coverage
- Server-rendered dashboard shell: Jinja2 + vendored htmx 2.0.10 + Pico CSS 2.1.1 (fully offline, no CDN), sidebar navigation, and status cards polling via htmx with a tab-visibility guard
- Real platform status contract: `/health` checks only launchpad's own MongoDB (K8s readinessProbe-safe 200/503), `/api/status` aggregates platform state incl. field-guide-api reachability with graceful degradation, `/metrics` at Prometheus parity
- `charts/launchpad/` Helm chart with least-privilege RBAC (ServiceAccount + namespace-scoped Role, get/list/watch on pods/deployments only) and a `/diagnostics` page showing live cluster state, degrading to an "outside cluster" panel without 500s
- Service catalog CRUD (CSRF-protected onboard form, detail pages, confirmed deregister) + TTL-bounded MongoDB events feed, backed by launchpad's own in-cluster mongo:7 manifests
- `make up-all` / `make smoke-all` one-command bring-up and verification of both apps; README headlines the browser demo with five real captured screenshots plus launchpad troubleshooting and known-limitations docs

**Known deferred items at close:** 0 open artifacts (6 INFO/WARNING tech-debt items tracked in milestones/v1.1-MILESTONE-AUDIT.md; accepted risks documented in docs/known-limitations.md)

**Requirements:** 27/27 v1.1 requirements complete (see milestones/v1.1-REQUIREMENTS.md)

---

## v1.0 Foundation (Shipped: 2026-07-07)

**Delivered:** The full local build-to-deploy loop — `make cluster-up && make build && make load && make deploy` (alias `make up`) produces a running, reachable Flask API on a local kind cluster, verified live and human-approved.

**Stats:** 4 phases, 12 plans, 114 commits, 103 files, ~1,360 LOC of app/chart/script source · Timeline: 2026-07-04 → 2026-07-07 (4 days)

**Key accomplishments:**

- Flask field-guide API (app factory, env-driven config, MongoDB CRUD, /health readiness, Prometheus /metrics seam) with 32 tests at 100% coverage, runnable without a cluster
- Idempotent kind + registry:3 infrastructure: six-step cluster-up with per-node containerd hosts.toml wiring and a self-verifying host-push → in-pod-pull check; double-safe teardown
- Multi-stage python:3.11-slim image (non-root UID 10001, gunicorn PID 1) deployed via a lint-clean Helm chart with embedded mongo:7 manifests (no Bitnami) and a generic values.yaml as the PRD-3 templating seam
- MAKE-02 core value proven live twice: `make up` end-to-end + `make smoke` PASS on /health, /entries, /metrics, with human sign-off (Git Bash primary; WSL2 N/A)
- Self-documenting Makefile (awk-powered `make help`, 15 targets incl. up/smoke/check-tools/clean) + portfolio-grade README with Mermaid architecture and three docs/ deep-dive pages
- Resilience demonstrated incidentally: cluster and app survived a Docker Desktop restart; an orphaned Helm `pending-upgrade` lock was recovered with a standard rollback, no data loss

**Known deferred items at close:** 0 (single audit flag was a resolved Phase 01 UAT with zero pending scenarios)

**Requirements:** 21/21 v1 requirements complete (see milestones/v1.0-REQUIREMENTS.md)

---
