# k8s-launchpad

A self-hosted Internal Developer Platform (IDP) — a mini-Heroku running on a local Kubernetes cluster — that automatically builds, deploys, monitors, and security-scans applications from a Git repo; this milestone (PRD-1) establishes the foundation: monorepo layout, a Flask field-guide API, containerization, and Helm deployment on a local kind cluster.

## Repository Layout

| Directory | Purpose |
|-----------|---------|
| `apps/` | Application source code (e.g. `apps/field-guide-api/`) |
| `charts/` | Helm charts for each application (e.g. `charts/field-guide-api/`) |
| `infra/kind/` | kind cluster configuration and local registry setup |
| `infra/argocd/` | PRD-2 GitOps seam — ArgoCD manifests (empty this milestone) |
| `infra/observability/` | PRD-4 observability seam — Prometheus/Grafana/Loki (empty this milestone) |
| `scripts/` | Automation scripts (cluster bootstrap, image loading, etc.) |
| `docs/` | Project documentation |
