# Feature Research

**Domain:** Self-hosted observability dashboards (Prometheus/Grafana) + "mission control" status UI for an internal developer platform (IDP)
**Researched:** 2026-07-16
**Confidence:** MEDIUM-HIGH — golden-signals/PromQL/Grafana-provisioning claims verified against Google SRE book, Prometheus official docs, and prometheus-community/grafana Helm chart docs (HIGH); status-page UX conventions drawn from multiple industry sources in agreement (MEDIUM); graceful-degradation UI pattern for "NO SIGNAL" cards is a general reliability pattern, not observability-specific, applied by analogy to this project's existing DIAG-01/02 precedent (MEDIUM).

---

## Context

This document replaces the v1.1 Product Dashboard feature research (superseded, PRD-3 shipped). The
new milestone target is v2.0 — filling the reserved `infra/observability/` seam (PRD-4, metrics-only
slice) with Prometheus/Grafana, and reskinning `apps/launchpad/` into a dark "mission control" UI. Scope
is strictly additive: nothing from v1.1 (`/api/status`, service catalog, diagnostics, activity feed) is
changed or removed. This research focuses only on what's new: observability dashboard conventions and
mission-control status UI conventions.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features a reviewer evaluating an "observability platform" portfolio piece will assume exist. Missing these makes the mission-control claim feel hollow.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Per-service uptime % (rolling window) | The #1 metric on every status page (Statuspage.io, UptimeRobot, Better Stack all lead with it); PROJECT.md explicitly names it | LOW | `avg_over_time(up{job="..."}[24h]) * 100` against the Prometheus `up` series per scrape target — cheap, no app-code changes needed |
| Request latency percentiles (p95, at minimum) | One of Google's "Four Golden Signals" (latency, traffic, errors, saturation) — the SRE-book baseline every credible dashboard covers | MEDIUM | `histogram_quantile(0.95, sum(rate(flask_http_request_duration_seconds_bucket[5m])) by (le))` — bucket metric already emitted by `prometheus-flask-exporter` on both apps (zero app changes) |
| Error rate % per service | The other core golden signal; without it "health" is guesswork | MEDIUM | `sum(rate(flask_http_request_duration_seconds_count{status=~"5.."}[5m])) / sum(rate(flask_http_request_duration_seconds_count[5m]))` — same metric family as latency, just filtered by status label |
| Color-coded status legend, consistent everywhere | Every reviewed status page (GitHub, Statuspage, UptimeRobot examples) uses a green/yellow/red (or similar) legend applied uniformly; inconsistent color semantics between the existing `/api/status` cards and new metric cards would read as unfinished | LOW | Reuse the color/label vocabulary already established by v1.1's `/api/status` (operational/degraded/down) — do not invent a second taxonomy for the new cards |
| "Last updated" / data freshness indicator | Dashboards showing numbers with no timestamp read as untrustworthy — reviewers specifically probe "is this live or static" | LOW | Cheap to add: timestamp of last successful Prometheus query on each card |
| Drill-down / "view more" path from summary to detail | Status pages and APM tools never dead-end at a single number — GitHub's and Atlassian's status pages both link from summary to component history | LOW | "Open in Grafana" deep link satisfies this without building a second charting UI |
| Hero "all systems operational" banner | Nearly universal status-page convention (GitHub, Statuspage-based pages, UptimeRobot templates) — single glanceable verdict above the fold | LOW | Aggregate from existing `/api/status` plus new metric thresholds; this is the literal ask in PROJECT.md ("All Systems Online") |
| Graceful "no data yet" / degraded state (not a crash or blank page) | Google's SRE/reliability guidance and this project's own established pattern (DIAG-01/02 already do this for K8s API unavailability) — a dashboard that 500s or silently blanks when Prometheus isn't installed reads as fragile | LOW–MEDIUM | Direct precedent already in codebase: the lazy K8s client `(None, None)` disabled-signal pattern from `apps/launchpad`; apply the same idiom to a lazy Prometheus client |

### Differentiators (Competitive Advantage)

Not required by "has observability," but what makes this read as platform-engineering-grade rather than "ran `helm install kube-prometheus-stack`."

| Feature | Value Proposition | Complexity | Notes |
|---------|--------------------|------------|-------|
| Native in-app metric cards (no iframe) with explicit "NO SIGNAL" dimmed state | Most tutorials just iframe a Grafana panel; native cards that degrade gracefully when the stack is absent show intentional UX design, and iframes break without a live port-forward/ingress (already identified as a risk in Key Decisions) | MEDIUM | Fetch via Prometheus HTTP API instant queries (`/api/v1/query`) server-side in Flask, render as themed cards; keep queries simple (instant, not `query_range`) to avoid a client-side charting library |
| Grafana dashboards-as-code via sidecar ConfigMaps | Most local demos click through Grafana's UI to build dashboards by hand (not reproducible, not reviewable in a PR); provisioning via labeled ConfigMaps (`grafana_dashboard: "1"`) makes dashboards git-versioned and reproducible on a fresh `make cluster-up` | MEDIUM | Standard kube-prometheus-stack idiom — confirmed via prometheus-community/grafana-helm-charts docs; requires `grafana.sidecar.dashboards.enabled: true` |
| "Open in Grafana" deep links with preserved context | Bridges the native/Grafana divide cleanly — reviewer sees a quick native number, then can click through to the full time-series panel rather than hitting a dead end | LOW–MEDIUM | Requires knowing the target dashboard UID + panel ID ahead of time since dashboards are provisioned as code — link construction is deterministic once UIDs are fixed |
| Dark "control room" visual theme (Pico dark + custom layer) | Distinctive portfolio signal — plain default Bootstrap/Pico light dashboards are the norm; a deliberate NOC/mission-control aesthetic (dark background, glanceable hero card, sparklines) is the kind of detail that reads as "shipped a product," not "ran a tutorial" | LOW–MEDIUM | No build step required (CSS layer only) — matches existing project convention of vendored assets, zero JS tooling |
| Idempotent demo data seeding (`make seed-demo`) | A first-run empty dashboard (0 services, empty activity feed, no metrics history) undersells the product to a reviewer; seeding through the *existing* APIs (not direct DB writes) also exercises the real code paths as a side effect | LOW–MEDIUM | Driving it through existing REST endpoints (service catalog register, etc.) means zero new app code — pure script/Makefile work |
| Self-check for the observability stack itself | Extending the existing self-diagnostics philosophy ("does the platform's own tooling work?") to cover "is Prometheus actually scraping both targets" turns observability into another dogfooded diagnostic, reinforcing the platform's stated identity | MEDIUM | Natural extension of DIAG-01/02 pattern; check `up{job=...}` == 1 for each ServiceMonitor target as a diagnostic row |

### Anti-Features (Commonly Requested, Often Problematic)

Features that look good on a checklist but would be wasted effort or actively risky in this milestone's scope/budget.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|----------------|------------------|-------------|
| Iframe-embedded Grafana panels in the dashboard | "Just embed the real Grafana graph, it's already built" | Breaks without an active port-forward/ingress path, requires disabling Grafana's `X-Frame-Options`/auth in ways that fight the security posture, and visually clashes with the custom dark skin (already flagged as a risk in Key Decisions) | Native Prometheus-fed cards + "Open in Grafana" deep link for the full graph |
| Alertmanager + paging/notification rules | "A real observability stack has alerting" | Resource-heavy for a local kind cluster (already explicitly disabled for the trimmed stack); no on-call/pager exists to receive it — adds an entire second config surface (routing, receivers, silences) with no consumer | Defer to a later PRD; if urgency-signaling is wanted now, encode it as a threshold color on the existing status cards instead |
| node-exporter / host-level system metrics | "Complete observability includes CPU/disk/memory" | Explicitly flaky on Docker Desktop kind nodes per project's own Key Decisions; adds noise unrelated to the two Flask apps being demoed; expands scope beyond "observe our two services" | kube-state-metrics (already in scope) covers pod/deployment state, which is the more relevant signal for this platform |
| Custom charting library (Chart.js/D3) for native cards | "Sparklines/graphs look richer than plain numbers" | Introduces a JS build dependency the project has deliberately avoided everywhere else (vendored htmx, no build step); duplicates what Grafana already does well | Keep native cards to numbers + simple CSS-only sparkline (a handful of divs/inline SVG from a small array of points) or omit trend graphics entirely and rely on the Grafana deep link for the real chart |
| WebSocket/SSE live-push metric updates | "Mission control should feel real-time" | Adds a persistent-connection architecture (reconnect handling, backpressure) for a dashboard whose underlying Prometheus scrape interval is itself ~15-30s — the perceived gain is cosmetic | Periodic polling via htmx (existing pattern already used for status cards) at an interval matched to the Prometheus scrape interval |
| Long-term metrics retention / remote-write to a TSDB (Thanos, Mimir, Cortex) | "Real production observability keeps months of history" | Massive infra addition for a local single-node kind cluster with a stated resource budget; nothing in this milestone needs > default in-cluster Prometheus retention (hours/days) | Rely on default Prometheus local retention; revisit only if a future PRD needs historical trend analysis beyond a few days |
| SLO burn-rate / error-budget panels | "This is the SRE-mature version of error-rate monitoring" | Requires defining and maintaining actual SLO targets, multi-window burn-rate alerting rules, and adds conceptual overhead disproportionate to a 2-service demo platform | Simple threshold-colored uptime %/latency/error-rate cards communicate the same "is it healthy" signal at a fraction of the complexity; note as a v2.x+ differentiator if ever revisited |

---

## Feature Dependencies

```
kube-prometheus-stack trimmed install (Prometheus + Grafana + kube-state-metrics)
    └──requires──> existing /metrics endpoints on both apps (already shipped, v1.0/v1.1)

ServiceMonitors (infra/observability/)
    └──requires──> kube-prometheus-stack (Prometheus Operator CRDs must exist first)
    └──requires──> existing /metrics endpoints (label-matched scrape targets)

Grafana dashboards-as-code (sidecar ConfigMaps)
    └──requires──> kube-prometheus-stack with grafana.sidecar.dashboards.enabled
    └──requires──> ServiceMonitors actively scraping (dashboards query empty series otherwise)

Native metric cards (uptime %, latency, error rate)
    └──requires──> Prometheus HTTP API reachable from launchpad pod
    └──requires──> ServiceMonitors scraping (same underlying series as Grafana dashboards)

"NO SIGNAL" graceful degradation on native cards
    └──requires──> lazy Prometheus client pattern (mirrors existing lazy K8s client from DIAG-01/02)
    └──enhances──> Native metric cards (makes them safe to ship before/without the stack running)

"Open in Grafana" deep links
    └──requires──> Grafana dashboards-as-code (dashboard UIDs must be fixed/known)
    └──enhances──> Native metric cards (adds drill-down path)

Mission Control hero "All Systems Online" card
    └──requires──> existing /api/status aggregation (v1.1)
    └──enhances──> Native metric cards (single glanceable verdict above the per-service detail)

make seed-demo
    └──requires──> existing service catalog + activity feed APIs (v1.1, unchanged)
    └──enhances──> Mission Control hero + native cards (first load is never an empty state)

Iframe-embedded Grafana panels ──conflicts──> Native metric cards + dark skin
    (excluded this milestone — see Anti-Features)

Alertmanager / node-exporter ──conflicts──> Trimmed resource-budget stack
    (explicitly disabled — see Anti-Features and PROJECT.md Out of Scope)
```

### Dependency Notes

- **Native metric cards require the same scrape wiring as Grafana dashboards:** both consume the identical Prometheus series (`up`, `flask_http_request_duration_seconds_*`), so there is no risk of the native cards and Grafana dashboards drifting apart in what they measure — they should use the *same* PromQL expressions, just rendered two ways.
- **"NO SIGNAL" degradation must exist before native cards ship, not after:** this project has already established the precedent (lazy K8s client, DIAG-01/02 outside-cluster/403/unreachable branches) — the roadmap should sequence the lazy Prometheus client alongside or before the card UI, mirroring that proven order.
- **"Open in Grafana" deep links depend on dashboard UIDs being fixed at authoring time:** because dashboards are provisioned as code (not click-built), the UID is deterministic and known before the Flask template is written — this is a one-way dependency (dashboards-as-code → deep links), not the reverse.
- **Iframe embedding conflicts with two already-locked decisions:** it fights both the native-card+NO-SIGNAL design and the vendored/no-CDN, no-iframe-fragility philosophy — this is already resolved in PROJECT.md Key Decisions, restated here as a hard anti-feature for roadmap purposes.
- **Alertmanager/node-exporter conflict with the stated resource budget:** re-enabling either later is a discrete, well-scoped future addition (not a rip-and-replace), since the trimmed stack still uses the same Helm chart with different toggles.

---

## MVP Definition

### Launch With (v2.0)

Minimum to make the "observability platform" and "mission control" claims credible and match PROJECT.md's target feature list.

- [ ] Trimmed kube-prometheus-stack (Operator + Prometheus + Grafana + kube-state-metrics; Alertmanager/node-exporter off) — the whole milestone depends on this foundation
- [ ] ServiceMonitors scraping both apps' existing `/metrics` — zero risk to v1.1 charts, pure addition
- [ ] Three Grafana dashboards-as-code: uptime %, request latency (p95 at minimum), error rate — matches the golden-signals table-stakes bar and the explicit PROJECT.md target
- [ ] Native metric cards for the same three signals, fed by the Prometheus HTTP API, with "Open in Grafana" links — the differentiator that makes this a "platform" not "just a Helm install"
- [ ] "NO SIGNAL" graceful degradation on native cards when the stack isn't installed — required so the additive-only constraint holds (launchpad must still boot and look intentional pre-observability-install)
- [ ] Mission Control hero "All Systems Online" card + dark skin — the UI reskin half of the milestone, built on existing `/api/status`
- [ ] `make seed-demo` — first-load-is-never-empty is a small addition with outsized reviewer-impact
- [ ] Additive Makefile targets (`observability-up`/`down`, `port-forward-grafana`, `seed-demo`, `up-mission-control`) + matching smoke target — keeps the "one command, verifiable" project convention intact

### Add After Validation (v2.x)

- [ ] Loki/log aggregation — already explicitly deferred to v2.1 in PROJECT.md; add once metrics-only v2.0 is stable and resource budget is re-assessed
- [ ] Self-check diagnostic for "is Prometheus actually scraping both targets" — natural v2.1 extension of the DIAG-01/02 pattern once the base stack has proven stable
- [ ] Traffic/request-rate (RPS) as a fourth native card — the remaining golden signal not explicitly requested this milestone; cheap to add once the other three are proven (same metric family, just a `rate()` count instead of a ratio/quantile)

### Future Consideration (v2.x+ / later PRDs)

- [ ] Alertmanager + notification rules — defer until there's an actual on-call/notification consumer; premature before then
- [ ] SLO burn-rate / error-budget panels — meaningful once actual SLO targets are defined for the platform, not before
- [ ] Long-term metrics retention (Thanos/Mimir remote-write) — only relevant if historical trend analysis beyond default retention becomes a stated need
- [ ] node-exporter host metrics — revisit if/when the platform runs on a more stable host than Docker Desktop kind nodes

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|----------------------|----------|
| Trimmed kube-prometheus-stack install | HIGH | MEDIUM | P1 |
| ServiceMonitors for existing /metrics | HIGH | LOW | P1 |
| Grafana dashboards-as-code (uptime/latency/error) | HIGH | MEDIUM | P1 |
| Native metric cards + NO SIGNAL degradation | HIGH | MEDIUM | P1 |
| Mission Control hero + dark skin | HIGH | LOW–MEDIUM | P1 |
| make seed-demo | MEDIUM | LOW | P1 |
| "Open in Grafana" deep links | MEDIUM | LOW | P1 |
| Additive Makefile targets + smoke test | HIGH | LOW | P1 |
| Traffic/RPS as a 4th signal | MEDIUM | LOW | P2 |
| Observability self-diagnostic (is scraping healthy) | MEDIUM | MEDIUM | P2 |
| Loki/log aggregation | MEDIUM | HIGH | P2 (v2.1) |
| Alertmanager/paging | LOW (no consumer yet) | MEDIUM | P3 |
| SLO burn-rate panels | LOW (premature) | HIGH | P3 |
| Long-term retention (Thanos/Mimir) | LOW (no need yet) | HIGH | P3 |

**Priority key:** P1 = must have for v2.0 launch; P2 = should have, natural next step once P1 is stable; P3 = nice to have, explicitly out of scope for now per PROJECT.md.

---

## Competitor / Reference Product Feature Analysis

Not commercial competitors (this is a portfolio IDP, not a SaaS), but the reference products a reviewer will mentally compare this UI against.

| Feature | Statuspage.io / UptimeRobot-style status pages | Grafana Cloud / stock kube-prometheus-stack dashboards | Our Approach |
|---------|--------------------------------------------------|----------------------------------------------------------|--------------|
| Hero status verdict | "All Systems Operational" banner, color-coded, above the fold | None — Grafana has no single "verdict," just panels | Adopt the status-page hero convention (matches PROJECT.md's explicit "All Systems Online" ask), computed from existing `/api/status` + metric thresholds |
| Per-service uptime % | Central metric, usually 90-day rolling | Available via PromQL but requires building the panel yourself | Native card with a short rolling window (e.g., 24h, given local cluster lifespan) + full Grafana panel for the longer view |
| Latency/error-rate detail | Rarely shown (status pages are consumer-facing, not engineer-facing) | Deep, panel-per-metric, but requires knowing PromQL / clicking through Explore | Native cards surface the number directly; deep link hands off to Grafana for the graph — splits the difference between the two audiences |
| Visual theme | Light, brand-colored, consumer-friendly | Default Grafana dark theme, generic | Deliberate dark "control room" skin — closer to a NOC wallboard than either reference, reinforcing the "mission control" identity |
| Behavior when data is missing | Status pages assume the monitoring backend is always up (it's their whole product) | Grafana panels show "No data" natively but require you to already be in Grafana | Explicit "NO SIGNAL" state in the native launchpad UI itself, before a reviewer ever needs to open Grafana — degrade gracefully at the point of first contact |
| Demo-readiness / seeded state | N/A — real products always have real traffic | Stock dashboards are empty until the cluster has been running a while | `make seed-demo` guarantees a populated, convincing first load |

**Key takeaway:** The right abstraction for this portfolio scope is neither a pure consumer-facing status page nor a raw Grafana install — it's a hybrid: a status-page-style hero verdict and native golden-signal cards feeding straight from Prometheus (so the launchpad UI never depends on Grafana being reachable), with Grafana's dashboards-as-code kept as the deep-dive layer behind explicit links. This split is what turns "installed a monitoring stack" into "built an observability experience."

---

## Sources

- [Google SRE Book — Monitoring Distributed Systems (Four Golden Signals)](https://sre.google/sre-book/monitoring-distributed-systems/) — HIGH confidence, canonical source for latency/traffic/errors/saturation
- [Prometheus HTTP API official docs](https://prometheus.io/docs/prometheus/latest/querying/api/) — HIGH confidence, instant query / query_range semantics
- [prometheus-community/helm-charts — kube-prometheus-stack values.yaml](https://github.com/prometheus-community/helm-charts/blob/main/charts/kube-prometheus-stack/values.yaml) — HIGH confidence, component enable/disable toggles (`nodeExporter.enabled`, `kubeStateMetrics.enabled`, `grafana.sidecar.dashboards.enabled`)
- [prometheus-community/helm-charts issue #336 — dashboards/datasources via sidecar+ConfigMap](https://github.com/prometheus-community/helm-charts/issues/336) — MEDIUM confidence, community-confirmed pattern
- [rycus86/prometheus_flask_exporter GitHub](https://github.com/rycus86/prometheus_flask_exporter) — HIGH confidence, confirms histogram bucket metric name/labels already emitted by both apps
- [mkaz.me — SLO formulas implementation in PromQL](https://mkaz.me/blog/2024/slo-formulas-implementation-in-promql-step-by-step/) — MEDIUM confidence, uptime/availability PromQL patterns
- [SoByte — Calculating SLI and SLO with PromQL](https://www.sobyte.net/post/2022-08/promql-sli-slo/) — MEDIUM confidence, corroborates uptime/latency-ratio query patterns
- [Better Stack Community — Status page examples](https://betterstack.com/community/guides/incident-management/status-page-examples/) — MEDIUM confidence, status-page UX convention survey
- [UptimeRobot — Ultimate Guide to Building a Status Page](https://uptimerobot.com/knowledge-hub/monitoring/building-a-status-page-ultimate-guide/) — MEDIUM confidence, status legend / hero banner conventions
- [ivbeg/awesome-status-pages GitHub list](https://github.com/ivbeg/awesome-status-pages) — MEDIUM confidence, breadth of real-world status page examples
- [AWS Well-Architected — REL05-BP01 Graceful Degradation](https://docs.aws.amazon.com/wellarchitected/latest/framework/rel_mitigate_interaction_failure_graceful_degradation.html) — HIGH confidence (official AWS reliability guidance), general pattern applied by analogy to the "NO SIGNAL" card requirement
- Project's own `.planning/PROJECT.md` (v1.1 requirements STAT-01..04, DIAG-01..02) — HIGH confidence, direct precedent for status-color vocabulary and graceful-degradation idiom already proven in this codebase

---

*Feature research for: observability dashboards + mission-control status UI (k8s-launchpad v2.0)*
*Researched: 2026-07-16*
