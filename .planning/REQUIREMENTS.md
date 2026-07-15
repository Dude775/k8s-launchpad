# Requirements: k8s-launchpad — Milestone v2.0 Observability + Mission Control

**Defined:** 2026-07-16
**Core Value:** `make up-mission-control` brings up the cluster, both apps, the observability stack, and seeded demo data — the platform demos as a production-grade control room with real telemetry.

**Hard constraint (applies to every requirement):** ADDITIVE ONLY — nothing from v1.1 is deleted, rewritten, or behavior-changed. All existing Makefile targets, charts, routes, and API contracts keep working exactly as they do now; v1.1 smoke tests pass unchanged.

## v2.0 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Observability Stack

- [ ] **OBS-01**: Operator can install a trimmed kube-prometheus-stack (pinned chart 87.16.1; Alertmanager, node-exporter, default rules, and kind-incompatible kubeadm scrape jobs disabled; conservative resource limits) into the kind cluster from `infra/observability/`
- [ ] **OBS-02**: Operator can tear down the observability stack cleanly with an explicit, documented CRD teardown policy — both v1.1 apps keep running untouched
- [ ] **OBS-03**: Prometheus discovers and scrapes the existing `/metrics` of field-guide-api and launchpad via standalone ServiceMonitors in `infra/observability/` (zero changes to existing charts); both targets report `up == 1`

### Grafana Dashboards

- [ ] **GRAF-01**: Grafana dashboards are provisioned as code — JSON in git, one ConfigMap per dashboard, fixed UIDs — and appear automatically on a fresh cluster install (sidecar discovery, no manual clicks)
- [ ] **GRAF-02**: Operator can view per-service uptime % (rolling window) in a Grafana dashboard
- [ ] **GRAF-03**: Operator can view per-service request latency (p95 minimum) in a Grafana dashboard
- [ ] **GRAF-04**: Operator can view per-service error rate % in a Grafana dashboard

### Mission Control UI

- [ ] **UI-06**: Launchpad renders in a dark "control room" skin (Pico dark scheme + vendored `mission-control.css` layer, no build step) — every pre-existing v1.1 page verified legible via manual visual re-walk
- [ ] **UI-07**: Dashboard shows a hero "All Systems Online" verdict card computed from the existing `/api/status` plus metric thresholds, using the established operational/degraded/down color vocabulary
- [ ] **UI-08**: Dashboard shows native per-service metric cards — uptime %, p95 latency, error rate, and request rate (RPS) — fed server-side from the Prometheus HTTP API and rendered via the existing htmx fragment pattern
- [ ] **UI-09**: Metric cards degrade to a dimmed "NO SIGNAL" state with an observability-up hint when Prometheus is absent or unreachable — the app boots, never 500s, and the test suite stays hermetic (lazy client + mocks, mirroring the v1.1 K8s client pattern)
- [ ] **UI-10**: Each metric card links to its Grafana panel via deterministic "Open in Grafana" deep links (fixed dashboard UIDs)
- [ ] **UI-11**: Metric cards show a data-freshness indicator (timestamp of last successful Prometheus query)

### Diagnostics

- [ ] **DIAG-03**: The `/diagnostics` page shows an observability self-check — Prometheus reachability and per-target scrape health (`up == 1` for both apps) — degrading gracefully like the existing diagnostic rows

### Developer CLI & Demo

- [ ] **MAKE-03**: Additive Makefile targets `observability-up`, `observability-down`, and `port-forward-grafana` (free local port) exist; every pre-existing target is byte-for-byte unchanged
- [ ] **MAKE-04**: Operator can run idempotent `make seed-demo` that populates demo data (service registrations + field-guide entries) through the existing REST APIs — activity feed populates naturally, re-runs don't duplicate
- [ ] **MAKE-05**: Operator can run `make up-mission-control` — sequential umbrella: up-all → observability-up → seed-demo — as the one-command flagship demo
- [ ] **MAKE-06**: A new smoke target verifies the v2.0 surface (observability up, targets scraped, metric cards responding), and `make smoke-all` still passes unchanged

### Documentation

- [ ] **DOCS-02**: README headlines the Mission Control demo (`make up-mission-control` → browser walkthrough) with real captured screenshots of the new UI and Grafana dashboards

## Future Requirements (v2.1+)

Deferred. Tracked but not in the current roadmap.

### Observability

- **LOKI-01**: Loki log aggregation with logs surfaced in Grafana (deferred from v2.0 for resource budget)
- **ALERT-01**: Alertmanager with notification rules (no on-call consumer exists yet)
- **SLO-01**: SLO burn-rate / error-budget panels (requires defined SLO targets first)

### Platform

- **GITOPS-01**: ArgoCD syncs deployments from Git (PRD-2, reordered after v2.0)
- **PLAT-01**: Real deployment pipeline behind the onboard form
- **CLOUD-01**: AWS/EKS/Terraform (final PRD)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Iframe-embedded Grafana panels | Break without live port-forward, fight Grafana auth/frame-options, clash with the dark skin — native cards + deep links instead |
| Alertmanager / node-exporter | Resource-heavy on local kind; node-exporter flaky on Docker Desktop nodes; no alerting consumer |
| JS charting library (Chart.js/D3) for native cards | Introduces a build/vendor dependency the project deliberately avoids; Grafana owns the real charts |
| WebSocket/SSE live push | Cosmetic gain over htmx polling when the scrape interval is ~15-30s anyway |
| Long-term retention (Thanos/Mimir) | No historical-analysis need on a disposable local cluster |
| Loki / logs | Deferred to v2.1 by explicit decision (v2.0 is metrics-only) |
| Any modification to v1.1 endpoints, charts, or Makefile targets | ADDITIVE ONLY hard constraint |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| OBS-01 | — | Pending |
| OBS-02 | — | Pending |
| OBS-03 | — | Pending |
| GRAF-01 | — | Pending |
| GRAF-02 | — | Pending |
| GRAF-03 | — | Pending |
| GRAF-04 | — | Pending |
| UI-06 | — | Pending |
| UI-07 | — | Pending |
| UI-08 | — | Pending |
| UI-09 | — | Pending |
| UI-10 | — | Pending |
| UI-11 | — | Pending |
| DIAG-03 | — | Pending |
| MAKE-03 | — | Pending |
| MAKE-04 | — | Pending |
| MAKE-05 | — | Pending |
| MAKE-06 | — | Pending |
| DOCS-02 | — | Pending |

**Coverage:**
- v2.0 requirements: 19 total
- Mapped to phases: 0 (roadmap pending)
- Unmapped: 19 ⚠️ (expected before roadmap)

---
*Requirements defined: 2026-07-16*
*Last updated: 2026-07-16 after initial definition*
