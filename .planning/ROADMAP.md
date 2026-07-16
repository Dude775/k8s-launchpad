# Roadmap: k8s-launchpad

## Milestones

- ✅ **v1.0 Foundation** — Phases 1-4 (shipped 2026-07-07) — [archive](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 Product Dashboard** — Phases 5-10 (shipped 2026-07-14) — [archive](milestones/v1.1-ROADMAP.md)
- 📋 **v2.0 Observability + Mission Control** — Phases 11-17 (planned)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

<details>
<summary>✅ v1.0 Foundation (Phases 1-4) — SHIPPED 2026-07-07</summary>

- [x] Phase 1: Scaffold + App + Tests (3/3 plans) — completed 2026-07-04
- [x] Phase 2: Cluster Infrastructure (2/2 plans) — completed 2026-07-05
- [x] Phase 3: Containerization + Helm Deployment (4/4 plans) — completed 2026-07-06
- [x] Phase 4: Makefile + Documentation (3/3 plans) — completed 2026-07-07

Full phase details: [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)

</details>

<details>
<summary>✅ v1.1 Product Dashboard (Phases 5-10) — SHIPPED 2026-07-14</summary>

- [x] Phase 5: Monorepo Scaffold + App Factory (2/2 plans) — completed 2026-07-08
- [x] Phase 6: UI Layer — Templates + Static Assets (2/2 plans) — completed 2026-07-10
- [x] Phase 7: Status API + Field-Guide Integration (2/2 plans) — completed 2026-07-10
- [x] Phase 8: Helm Chart + K8s Diagnostics (2/2 plans) — completed 2026-07-11
- [x] Phase 9: Service Catalog + Events / MongoDB CRUD (4/4 plans) — completed 2026-07-12
- [x] Phase 10: Makefile Integration + Smoke + Docs (2/2 plans) — completed 2026-07-13

Full phase details: [milestones/v1.1-ROADMAP.md](milestones/v1.1-ROADMAP.md)

</details>

### 📋 v2.0 Observability + Mission Control (Planned)

**Milestone Goal:** Turn k8s-launchpad from a static live-state dashboard into a real observability platform with a control-room UI — fill the reserved `infra/observability/` seam (PRD-4) and reskin launchpad to "launch to air" portfolio quality, strictly additively. Nothing from v1.1 is deleted, rewritten, or behavior-changed.

- [x] **Phase 11: Observability Stack Install** - Trimmed kube-prometheus-stack running in the kind cluster, resource-safe, teardown-documented (completed 2026-07-16)
- [ ] **Phase 12: ServiceMonitor Scraping** - Prometheus scrapes both existing apps' `/metrics` with zero chart changes
- [ ] **Phase 13: Grafana Dashboards-as-Code** - Uptime/latency/error-rate dashboards provisioned automatically on a fresh cluster
- [ ] **Phase 14: Additive Observability Makefile Targets** - `observability-up`/`observability-down`/`port-forward-grafana`, existing targets untouched
- [ ] **Phase 15: Native Metric-Card Client + Graceful Degradation** - Launchpad surfaces live golden-signal metrics natively, degrading gracefully without Prometheus
- [ ] **Phase 16: Mission Control UI Reskin** - Dark control-room skin with a hero verdict card, zero regression on pre-existing pages
- [ ] **Phase 17: Demo Seeding + Final Wiring** - One-command flagship demo (`make up-mission-control`) with populated data and updated README

## Phase Details

### Phase 11: Observability Stack Install
**Goal**: A trimmed `kube-prometheus-stack` (Prometheus Operator + Prometheus + Grafana + kube-state-metrics) runs in its own `observability` namespace on the kind cluster, with a documented teardown policy, and without disturbing the already-running v1.1 apps.
**Depends on**: Nothing new (first phase of v2.0; assumes v1.1's `make up-all` apps are already deployable)
**Requirements**: OBS-01, OBS-02
**Success Criteria** (what must be TRUE):
  1. Operator can install the trimmed stack into `observability` namespace from `infra/observability/`, with Alertmanager, node-exporter, default rules, and kind-incompatible kubeadm scrape jobs explicitly disabled.
  2. All observability pods reach Running/Ready within conservative resource limits, and immediately re-running `make smoke`/`smoke-launchpad` afterward still passes — the existing field-guide-api and launchpad pods are never evicted or restarted.
  3. Operator can tear down the observability stack via a documented CRD teardown policy, leaving both v1.1 apps running untouched.
  4. Prometheus and Grafana UIs are reachable locally via port-forward.
**Plans**: 3 plans
- [x] 11-01-PLAN.md — Trimmed chart values (`values-trimmed.yaml`) + idempotent self-verifying install script (OBS-01)
- [x] 11-02-PLAN.md — Idempotent teardown script + accepted-risk documentation for CRD retention / Grafana creds (OBS-02)
- [x] 11-03-PLAN.md — Live install→verify→teardown lifecycle checkpoint (UIs reachable, apps untouched, CRDs retained)

### Phase 12: ServiceMonitor Scraping
**Goal**: Prometheus actively discovers and scrapes the existing `/metrics` endpoints of field-guide-api and launchpad, with zero changes to either app's Helm chart.
**Depends on**: Phase 11
**Requirements**: OBS-03
**Success Criteria** (what must be TRUE):
  1. Standalone `ServiceMonitor` manifests exist in `infra/observability/` for field-guide-api and launchpad; neither app chart is modified.
  2. Prometheus's Targets page shows `up == 1` for both the field-guide-api and launchpad scrape jobs.
  3. Operator can confirm scraping via a live PromQL query (`up{job=...}`) returning 1 for both jobs, not just object creation succeeding.
**Plans**: TBD

### Phase 13: Grafana Dashboards-as-Code
**Goal**: Golden-signal Grafana dashboards (uptime, latency, error rate) are version-controlled and appear automatically on any fresh cluster install with zero manual clicks.
**Depends on**: Phase 12
**Requirements**: GRAF-01, GRAF-02, GRAF-03, GRAF-04
**Success Criteria** (what must be TRUE):
  1. Three dashboard JSON files live in git under `infra/observability/dashboards/`, one ConfigMap per dashboard, each with a fixed UID and the sidecar-discovery label.
  2. On a fresh cluster install, all three dashboards appear in Grafana automatically, verified via Grafana's own dashboard-search API (not eyeballing the UI once).
  3. Operator can view per-service uptime % (rolling window) for both field-guide-api and launchpad.
  4. Operator can view per-service p95 request latency for both services.
  5. Operator can view per-service error rate % for both services.
**Plans**: TBD
**UI hint**: yes

### Phase 14: Additive Observability Makefile Targets
**Goal**: The full observability stack lifecycle (install, teardown, Grafana access) is one-command reproducible in Git Bash, matching the project's existing compositional Makefile convention.
**Depends on**: Phase 13
**Requirements**: MAKE-03
**Success Criteria** (what must be TRUE):
  1. `make observability-up` brings up the trimmed stack, ServiceMonitors, and dashboards from a clean cluster in one command.
  2. `make observability-down` tears the stack down per the Phase 11 CRD teardown policy.
  3. `make port-forward-grafana` opens Grafana on a free local port.
  4. Every pre-existing Makefile target remains byte-for-byte unchanged (diff-verified against the pre-v2.0 Makefile).
**Plans**: TBD

### Phase 15: Native Metric-Card Client + Graceful Degradation
**Goal**: Launchpad surfaces live golden-signal metrics natively via the existing htmx fragment pattern, degrading gracefully — never crashing, never blocking — when Prometheus is absent or unreachable.
**Depends on**: Phase 13 (needs fixed dashboard UIDs for deep links) and Phase 12 (needs a live scrape target to query)
**Requirements**: UI-08, UI-09, UI-10, UI-11, DIAG-03
**Success Criteria** (what must be TRUE):
  1. Dashboard shows native per-service metric cards (uptime %, p95 latency, error rate, request rate) fed server-side from the Prometheus HTTP API via the existing htmx fragment pattern.
  2. When Prometheus is absent or unreachable, metric cards degrade to a dimmed "NO SIGNAL" state with an install hint — the app never 500s, and the hermetic test suite still passes fully mocked with no live cluster.
  3. Each metric card links to its Grafana panel via a deterministic "Open in Grafana" deep link using the fixed dashboard UIDs from Phase 13.
  4. Each metric card shows a data-freshness timestamp of its last successful Prometheus query.
  5. The `/diagnostics` page shows an observability self-check (Prometheus reachability + per-target scrape health, `up == 1` for both apps), degrading gracefully like the existing diagnostic rows.
**Plans**: TBD
**UI hint**: yes

### Phase 16: Mission Control UI Reskin
**Goal**: Launchpad reads as a dark "control room" product with a hero system-verdict card, with zero legibility regression on any pre-existing v1.1 page.
**Depends on**: Phase 15
**Requirements**: UI-06, UI-07
**Success Criteria** (what must be TRUE):
  1. Launchpad renders in a dark control-room skin (Pico dark scheme + a `mission-control.css` cascade layer), introducing no build step and no new vendored dependency beyond the one CSS file.
  2. Every pre-existing v1.1 page (onboard/register form, service catalog + detail, diagnostics, activity feed) is manually re-walked and confirmed legible under the new theme — recorded as an explicit exit-criterion check, not assumed from automated tests.
  3. Dashboard shows a hero "All Systems Online" verdict card computed from the existing `/api/status` plus metric thresholds, reusing the established operational/degraded/down color vocabulary (not a second taxonomy).
**Plans**: TBD
**UI hint**: yes

### Phase 17: Demo Seeding + Final Wiring
**Goal**: The entire v2.0 surface is reachable with a single command, populated with realistic demo data, and documented with real screenshots — the flagship one-command demo.
**Depends on**: Phase 14 and Phase 16
**Requirements**: MAKE-04, MAKE-05, MAKE-06, DOCS-02
**Success Criteria** (what must be TRUE):
  1. Operator can run idempotent `make seed-demo`, which populates service registrations and field-guide entries through the existing REST APIs; re-running it does not duplicate data, and the activity feed populates naturally.
  2. Operator can run `make up-mission-control` as a single sequential umbrella (`up-all` → `observability-up` → `seed-demo`) to reach the fully-populated flagship demo state.
  3. A new smoke target verifies the v2.0 surface end to end (observability up, both targets scraped, metric cards responding), and `make smoke-all` still passes unchanged.
  4. README headlines the Mission Control demo (`make up-mission-control` → browser walkthrough) with real captured screenshots of the new UI and Grafana dashboards.
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 11 → 12 → 13 → 14 → 15 → 16 → 17

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Scaffold + App + Tests | v1.0 | 3/3 | Complete | 2026-07-04 |
| 2. Cluster Infrastructure | v1.0 | 2/2 | Complete | 2026-07-05 |
| 3. Containerization + Helm Deployment | v1.0 | 4/4 | Complete | 2026-07-06 |
| 4. Makefile + Documentation | v1.0 | 3/3 | Complete | 2026-07-07 |
| 5. Monorepo Scaffold + App Factory | v1.1 | 2/2 | Complete | 2026-07-08 |
| 6. UI Layer — Templates + Static Assets | v1.1 | 2/2 | Complete | 2026-07-10 |
| 7. Status API + Field-Guide Integration | v1.1 | 2/2 | Complete | 2026-07-10 |
| 8. Helm Chart + K8s Diagnostics | v1.1 | 2/2 | Complete | 2026-07-11 |
| 9. Service Catalog + Events / MongoDB CRUD | v1.1 | 4/4 | Complete | 2026-07-12 |
| 10. Makefile Integration + Smoke + Docs | v1.1 | 2/2 | Complete | 2026-07-13 |
| 11. Observability Stack Install | v2.0 | 3/3 | Complete   | 2026-07-16 |
| 12. ServiceMonitor Scraping | v2.0 | 0/? | Not started | - |
| 13. Grafana Dashboards-as-Code | v2.0 | 0/? | Not started | - |
| 14. Additive Observability Makefile Targets | v2.0 | 0/? | Not started | - |
| 15. Native Metric-Card Client + Graceful Degradation | v2.0 | 0/? | Not started | - |
| 16. Mission Control UI Reskin | v2.0 | 0/? | Not started | - |
| 17. Demo Seeding + Final Wiring | v2.0 | 0/? | Not started | - |
