# Milestones

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
