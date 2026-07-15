# Architecture Research

**Domain:** Self-hosted Kubernetes observability (kube-prometheus-stack) + Flask/htmx "control room" UI reskin, integrated into an existing multi-chart monorepo IDP
**Researched:** 2026-07-16
**Confidence:** HIGH (chart/CLI behavior verified against prometheus-community/grafana official docs + GitHub issues; MEDIUM on exact PromQL query shapes, which are a phase-level design detail, not a research blocker)

## Standard Architecture

### System Overview

```
┌───────────────────────────────────────────────────────────────────────────┐
│ EXISTING (frozen, additive-only)                                          │
│  ┌───────────────┐        ┌────────────────┐                             │
│  │ field-guide-api│ <---- │ launchpad        │  (both: default namespace) │
│  │ Svc:80->8000   │  http │  /api/status     │                             │
│  │ /metrics       │       │  /partials/*     │                             │
│  │ labels: name=  │       │  Svc:80->8000    │                             │
│  │  field-guide-api│      │  /metrics        │                             │
│  └───────┬────────┘       │  labels: name=   │                             │
│          │                │   launchpad      │                             │
│      mongo:7           mongo:7 (own)          │
└──────────┼────────────────────┼──────────────┼─────────────────────────────┘
           │ scraped by ServiceMonitor          │ scraped by ServiceMonitor
           │ (label-selector match, NO          │ (label-selector match, NO
           │  chart changes required)           │  chart changes required)
┌──────────▼────────────────────▼──────────────▼─────────────────────────────┐
│ NEW — infra/observability/ namespace "observability" (Helm: kube-prometheus-│
│ stack, trimmed)                                                             │
│  ┌────────────────┐   ┌───────────────────┐   ┌────────────────────────┐  │
│  │ Prometheus      │   │ Grafana            │   │ kube-state-metrics     │  │
│  │ Operator +      │──▶│ + sidecar watches  │   │ (cluster object state) │  │
│  │ Prometheus CR   │   │ ConfigMaps labeled │   └────────────────────────┘  │
│  │ svc:            │   │ grafana_dashboard=1│                              │
│  │ prometheus-     │   │ Svc: <rel>-grafana │   (Alertmanager: disabled)   │
│  │ operated:9090   │   │      :80           │   (node-exporter: disabled)  │
│  └───────▲─────────┘   └────────────────────┘                              │
│          │ PromQL HTTP API (/api/v1/query)                                 │
│  ┌───────┴─────────┐        ┌─────────────────────────┐                    │
│  │ ServiceMonitor:  │        │ Grafana dashboard        │                   │
│  │ field-guide-api  │        │ ConfigMaps (JSON,        │                   │
│  │ ServiceMonitor:  │        │ label grafana_dashboard) │                   │
│  │ launchpad        │        │ — dashboards-as-code     │                   │
│  │ (standalone      │        └─────────────────────────┘                    │
│  │  manifests, NOT  │                                                       │
│  │  in app charts)  │                                                       │
│  └──────────────────┘                                                       │
└──────────────────────────────────────────────────────────────────────────────┘
           ▲
           │ requests.get(PROMETHEUS_BASE_URL + /api/v1/query, timeout=2s)
┌──────────┴───────────────────────────────────────────────────────────────┐
│ launchpad app/ (NEW module, additive)                                     │
│  app/prometheus.py — thin PromQL client, never-raises, mirrors            │
│    app/status.py's exception-isolation + 2s timeout discipline            │
│  app/routes/observability.py (or extend partials_bp) — metric-card        │
│    fragment endpoint, "Open in Grafana" deep links, NO SIGNAL degradation │
│  app/templates/mission-control.css layered over pico.min.css + style.css  │
│    (base.html gains one new <link>, third cascade layer)                  │
└────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|-----------------|-------------------------|
| kube-prometheus-stack (trimmed) | Runs Prometheus Operator, a `Prometheus` CR, Grafana, kube-state-metrics; owns CRDs (`ServiceMonitor`, `PodMonitor`) | Helm chart `prometheus-community/kube-prometheus-stack`, installed into its own `observability` namespace, `alertmanager.enabled: false`, `nodeExporter.enabled: false` |
| ServiceMonitor (field-guide-api) | Tells the Prometheus Operator to scrape the *existing* field-guide-api Service's `/metrics` on its `http` port | Standalone YAML in `infra/observability/`, `spec.selector.matchLabels` = the Service's existing `app.kubernetes.io/name: field-guide-api` label — zero chart edits |
| ServiceMonitor (launchpad) | Same, for launchpad's `/metrics` | Standalone YAML in `infra/observability/`, matches `app.kubernetes.io/name: launchpad` |
| Grafana dashboard ConfigMaps | Provision uptime/latency/error-rate dashboards as code, re-created on every fresh cluster | ConfigMaps in `infra/observability/dashboards/`, each with label `grafana_dashboard: "1"`, one dashboard JSON per ConfigMap (Grafana sidecar recommendation — one dashboard per ConfigMap avoids known sidecar merge bugs) |
| `app/prometheus.py` (new) | Query the Prometheus HTTP API for the metric cards; never raise; degrade to "NO SIGNAL" on any failure | Thin wrapper around `requests.get(f"{PROMETHEUS_BASE_URL}/api/v1/query", params={"query": ...}, timeout=2)`, same shape as `app/status.py`'s `field_guide_reachable` check |
| New launchpad route/blueprint | Serve a metric-cards hypermedia fragment + "Open in Grafana" links | Extends the existing partial-fragment pattern (`app/routes/partials.py`, `app/templates/partials/status_cards.html`) rather than inventing a new polling mechanism |
| `mission-control.css` (new) | Visual reskin layer; hero card, metric-card styling, dimmed/disabled states | Third stylesheet loaded in `base.html` after `pico.min.css` and `style.css`, same override-cascade convention already established |
| Makefile: `observability-up/down`, `port-forward-grafana`, `seed-demo`, `up-mission-control` | Additive automation wrapping the above | New `.PHONY` targets appended to the existing Makefile; **zero edits to existing targets or their bodies** |

## Recommended Project Structure

```
infra/
├── observability/
│   ├── kube-prometheus-stack-values.yaml   # trimmed values (alertmanager/nodeExporter disabled)
│   ├── servicemonitor-field-guide-api.yaml # standalone CRD manifest, targets existing Service by label
│   ├── servicemonitor-launchpad.yaml       # standalone CRD manifest, targets existing Service by label
│   └── dashboards/
│       ├── uptime-dashboard-configmap.yaml     # label: grafana_dashboard: "1"
│       ├── latency-dashboard-configmap.yaml
│       └── error-rate-dashboard-configmap.yaml
scripts/
├── observability-up.sh     # helm repo add/update, helm upgrade --install --create-namespace -n observability, kubectl apply -f infra/observability/*.yaml, wait for rollout
├── observability-down.sh   # helm uninstall + kubectl delete namespace observability (idempotent, mirrors cluster-teardown.sh style)
└── seed-demo.sh            # idempotent curl/POST sequence against launchpad's EXISTING /catalog/new and any other write endpoints
apps/launchpad/app/
├── prometheus.py            # NEW — bare helper module, mirrors k8s.py/status.py shape
├── routes/
│   └── observability.py     # NEW blueprint (or extend partials.py) — metric-card fragment + Grafana deep-link builder
├── static/
│   └── mission-control.css  # NEW — third cascade layer
└── templates/
    ├── base.html            # ONE new <link> line added (additive asset reference only)
    ├── index.html           # hero "All Systems Online" + metric cards section added
    └── partials/
        └── metric_cards.html # NEW partial, follows status_cards.html's fragment/full-page pattern
```

### Structure Rationale

- **`infra/observability/` as flat standalone manifests, not a chart:** The milestone's hard constraint is zero modification to `charts/field-guide-api` and `charts/launchpad`. Putting ServiceMonitors inside either app chart would work functionally but violates the additive-only boundary; keeping them as plain YAML applied via `kubectl apply -f` (or a tiny umbrella chart if templating helps later) keeps the seam self-contained and reviewable independent of the app charts.
- **Dashboards as one ConfigMap per JSON file:** the Grafana sidecar has documented issues merging multiple dashboards bundled in a single ConfigMap; one file per ConfigMap is the safe, recommended pattern.
- **`app/prometheus.py` as a bare module (no Blueprint):** mirrors the two precedents already in this codebase — `app/k8s.py` (lazy, returns `None` sentinel on failure, no caching) and the `field_guide_reachable` block inside `app/status.py` (mandatory timeout, exception-isolated, discards exception detail). A new PromQL client should not invent a third style.
- **Reuse the hypermedia fragment pattern for metric cards, not a new mechanism:** `app/routes/partials.py` + `app/templates/partials/status_cards.html` already establish "poll a fragment endpoint with htmx, render full-page too when not `HX-Request`." The metric cards should be a sibling partial, not a parallel polling scheme.

## Architectural Patterns

### Pattern 1: Out-of-chart ServiceMonitor targeting existing Services by label

**What:** A `ServiceMonitor` CRD is a separate Kubernetes object from the `Service` it targets. The Prometheus Operator reconciles `spec.selector.matchLabels` against `Service.metadata.labels` (not the app chart) to find scrape targets. Both existing charts already stamp `app.kubernetes.io/name` / `app.kubernetes.io/instance` onto their Services via the shared `*.labels` Helm helper — this is already sufficient; **no chart edits are needed** to make either Service scrapable.

**When to use:** Whenever you must add Prometheus scraping to a workload whose chart you are contractually forbidden to touch (this project's exact situation).

**Trade-offs:** You lose the ability to co-version the ServiceMonitor with the app chart (upgrade/rollback together); acceptable here since these are truly independent lifecycle concerns (observability stack vs. app chart) and the constraint is explicit.

**Example (`infra/observability/servicemonitor-launchpad.yaml`):**
```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: launchpad
  namespace: observability
  labels:
    release: kube-prometheus-stack   # required unless serviceMonitorSelectorNilUsesHelmValues=false
spec:
  namespaceSelector:
    matchNames: ["default"]           # where launchpad's Service actually lives
  selector:
    matchLabels:
      app.kubernetes.io/name: launchpad   # already emitted by charts/launchpad/templates/service.yaml
  endpoints:
    - port: http        # matches the Service's existing `name: http` port
      path: /metrics
      interval: 15s
```

### Pattern 2: Graceful-degradation outbound query (extends an existing convention)

**What:** Every cross-service HTTP call in launchpad already follows one discipline: bounded timeout (2s), narrow exception catch, discard exception detail, return a sentinel (`False` / `0` / empty dict) — never raise past the caller. `app/prometheus.py` must be the third instance of this same pattern (after `app/k8s.py` and the `field_guide_reachable` check in `app/status.py`), not a new design.

**When to use:** Any new call from launchpad to a component that may not be installed (Prometheus/Grafana here) or may be temporarily unreachable.

**Trade-offs:** Silently swallowing errors means operators must rely on Grafana/Prometheus's own health surfaces for real debugging; acceptable because launchpad's UI purpose is "is it there, yes/no/dimmed," not a diagnostics console for Prometheus itself.

**Example:**
```python
PROMETHEUS_TIMEOUT_SECONDS = 2

def query_instant(promql: str) -> dict | None:
    base_url = current_app.config["PROMETHEUS_BASE_URL"]
    try:
        resp = requests.get(
            f"{base_url}/api/v1/query",
            params={"query": promql},
            timeout=PROMETHEUS_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException:
        return None  # caller renders a dimmed "NO SIGNAL" card
```

### Pattern 3: Stylesheet cascade layering (already established, extend don't replace)

**What:** `style.css` already documents itself as "loaded AFTER pico.min.css so these overrides win the cascade." `mission-control.css` is a third layer with the same contract: loaded after both, only adds new selectors/hero/metric-card rules, never edits `style.css` or `pico.min.css`.

**When to use:** Any future visual layer in this codebase — this is now a two-layer-turned-three-layer convention, not a one-off.

**Trade-offs:** Cascade ordering bugs are possible if specificity isn't managed, but the project has already accepted this trade-off for `style.css`; consistency matters more than avoiding a hypothetical CSS specificity fight.

## Data Flow

### Scrape flow (new)

```
Prometheus Operator (observability ns)
    ↓ watches ServiceMonitor objects (all namespaces, empty namespaceSelector by default)
ServiceMonitor(field-guide-api) / ServiceMonitor(launchpad)   [infra/observability/, standalone]
    ↓ selector.matchLabels resolves to existing Services in "default" ns
Service(field-guide-api):80 / Service(launchpad):80  [UNCHANGED — no chart edits]
    ↓ Endpoints -> Pod IP:8000/metrics
Prometheus scrapes /metrics on each app's existing prometheus-flask-exporter endpoint
    ↓ stored as time series
Prometheus TSDB (short retention, no PVC needed — kind clusters are disposable)
```

### Metric-card query flow (new)

```
Browser (htmx poll, e.g. every 10-15s)
    ↓ GET /partials/metric-cards  (new launchpad route)
app/routes/observability.py
    ↓ calls app/prometheus.py.query_instant(promql)
    ↓ requests.get(PROMETHEUS_BASE_URL + /api/v1/query, timeout=2s)
prometheus-operated.observability.svc.cluster.local:9090   [stable, hardcoded operator-governed Service name]
    ↓ success: render metric values + "Open in Grafana" deep link (GRAFANA_BASE_URL)
    ↓ failure/timeout: render dimmed "NO SIGNAL" card — same shape as field_guide_reachable=False today
```

### Demo-seeding flow (new, independent of observability)

```
make seed-demo
    ↓ idempotent curl/POST sequence against launchpad's EXISTING /catalog/new (v1.1, unchanged)
    ↓ (optionally) idempotent GETs against field-guide-api's existing /entries to generate traffic
    ↓ registrations land in launchpad's own Mongo (services collection) — same code path as a human filling the form
    ↓ activity feed populates via the EXISTING events.record_event() call inside catalog_new() — zero app-code changes
```

### Key Data Flows

1. **Scrape flow requires zero chart changes** — the only new Kubernetes objects are the `ServiceMonitor`s and the kube-prometheus-stack release itself; existing Service labels are already sufficient selectors.
2. **Query flow reuses the exact resiliency discipline already proven in `app/status.py`** — same timeout constant pattern, same never-raise contract, same "sentinel value on failure" shape.
3. **Demo seeding is fully decoupled from the observability stack** — it only exercises pre-existing, already-tested v1.1 write endpoints, so it can be built and validated independently and early.

## Scaling Considerations

This is a single-developer local `kind` cluster, not a multi-tenant production system — "scaling" here means "fits in Docker Desktop's resource budget," not "handles more users."

| Scale | Architecture Adjustments |
|-------|---------------------------|
| Local kind, current milestone | Trim kube-prometheus-stack aggressively: disable Alertmanager + node-exporter (already decided), keep Prometheus retention short (e.g. `--storage.tsdb.retention.time=6h` or similar via `prometheus.prometheusSpec.retention`), use `emptyDir` (no PVC) for Prometheus data — disposable by design, matches `reset-local`'s "everything is destroyable" philosophy |
| If dashboards/metrics need to survive `reset-local` | Not recommended for this milestone — dashboards are already reproducible-as-code (ConfigMaps re-apply on every `observability-up`), so there is no state worth persisting; keep it stateless |
| If a future milestone adds Loki (v2.1, deferred) | Loki will need its own PVC and its own ServiceMonitor/scrape-config equivalent (or a Promtail/Alloy DaemonSet) — out of scope now, but the `infra/observability/` flat-manifest pattern established here should extend cleanly |

### Scaling Priorities

1. **First bottleneck: Docker Desktop memory/CPU for kind.** Prometheus Operator + Prometheus + Grafana + kube-state-metrics, even trimmed, is the heaviest thing this cluster has run so far (heavier than two Flask apps + two MongoDBs combined). Set explicit low `resources.requests/limits` on every kube-prometheus-stack sub-component in the trimmed values file, mirroring the existing apps' `50m/128Mi` request pattern.
2. **Second bottleneck: cluster spin-up time.** `observability-up` adds a `helm repo add/update` + a multi-pod rollout (CRDs first, then operator, then Prometheus/Grafana pods) on top of the existing `up-all` sequence — budget for `--wait --timeout` values noticeably longer than the existing 180s used by `deploy`/`deploy-launchpad`.

## Anti-Patterns

### Anti-Pattern 1: Putting ServiceMonitors inside `charts/field-guide-api` or `charts/launchpad`

**What people do:** Add a `templates/servicemonitor.yaml` to the app chart because "it's right next to the Service it targets."
**Why it's wrong:** Violates the explicit hard constraint (zero modification to existing charts) and couples the app chart's lifecycle to whether the observability stack CRDs (`monitoring.coreos.com/v1`) exist — `helm install` of either app chart would fail on a cluster without the Prometheus Operator CRDs installed first, breaking the v1.1 smoke-test invariant that both charts install cleanly standalone.
**Do this instead:** Standalone ServiceMonitor manifests in `infra/observability/`, applied only when the observability stack (and its CRDs) already exist.

### Anti-Pattern 2: Iframe-embedded Grafana panels in launchpad

**What people do:** Drop an `<iframe src="http://grafana/d/...">` into the dashboard for "instant" visuals.
**Why it's wrong:** Already identified and rejected in this project's own Key Decisions — iframes require Grafana to be port-forwarded/reachable from the browser (not just in-cluster), break the "vendored/no-CDN" and "graceful degradation" philosophy, and clash with the Mission Control skin's visual language.
**Do this instead:** Native Prometheus-fed metric cards (server-side query, rendered as Jinja/htmx fragments) + an "Open in Grafana" deep link for drill-down — already the locked decision.

### Anti-Pattern 3: Coupling `/health` (readiness) to Prometheus/Grafana reachability

**What people do:** Add a Prometheus ping to the readinessProbe target because "the platform isn't really healthy without observability."
**Why it's wrong:** `/health` is explicitly, deliberately scoped to launchpad's own MongoDB only (documented decision: "readinessProbe must never couple to downstream services"). Coupling it to an optional, independently-lifecycled component (observability may not even be installed) would make the launchpad pod NotReady whenever `observability-down` is run, which is a working, supported state, not a failure.
**Do this instead:** Treat Prometheus/Grafana reachability exactly like field-guide-api reachability today — a `/api/status`-style aggregated check, never a readiness gate.

### Anti-Pattern 4: One ConfigMap holding multiple Grafana dashboard JSONs

**What people do:** Bundle uptime + latency + error-rate dashboards into a single `dashboards-configmap.yaml` for tidiness.
**Why it's wrong:** Documented upstream sidecar bug/limitation — multi-dashboard ConfigMaps are not reliably reflected in Grafana; updates to one dashboard can silently fail to propagate.
**Do this instead:** One ConfigMap per dashboard JSON, each labeled `grafana_dashboard: "1"`.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|----------------------|-------|
| kube-prometheus-stack (Prometheus Operator + Prometheus + Grafana + kube-state-metrics) | Helm chart `prometheus-community/kube-prometheus-stack`, installed via `helm upgrade --install --create-namespace -n observability` from `scripts/observability-up.sh` | Trim via values: `alertmanager.enabled: false`, `nodeExporter.enabled: false`; leave `kubeStateMetrics.enabled: true`, `grafana.enabled: true` |
| Prometheus HTTP API | launchpad's new `app/prometheus.py` calls `GET {PROMETHEUS_BASE_URL}/api/v1/query` | In-cluster DNS default: `http://prometheus-operated.observability.svc.cluster.local:9090` — this Service name is **hardcoded by the Prometheus Operator itself** (not the Helm release name), so it does not change if the observability Helm release is renamed. Mirrors the existing `FIELD_GUIDE_BASE_URL` config pattern exactly. |
| Grafana | Deep links only (`GRAFANA_BASE_URL` + dashboard UID), plus `make port-forward-grafana` for human access | Service name: `<observability-release>-grafana`, port 80. Default admin credentials: username `admin`, password from Secret `<release>-grafana` key `admin-password` (default value `prom-operator` unless overridden) — treat exactly like the existing MongoDB dev-password convention: fine for local kind, documented as local-dev-only, never a real credential |
| ServiceMonitor discovery selector | `kube-prometheus-stack`'s `Prometheus` CR defaults to `serviceMonitorSelectorNilUsesHelmValues: true`, which **requires every ServiceMonitor to carry a `release: <helm-release-name>` label** to be discovered | Since the two new ServiceMonitors are standalone manifests (not chart-templated), this label must be added by hand in `infra/observability/servicemonitor-*.yaml`, OR set `serviceMonitorSelectorNilUsesHelmValues: false` in the trimmed values to discover ServiceMonitors cluster-wide regardless of label — recommended for this single-tenant local environment, since there is no risk of accidentally scraping an unrelated tenant's ServiceMonitors |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|----------------|-------|
| launchpad ↔ Prometheus | Outbound HTTP (PromQL `/api/v1/query`), 2s timeout, never-raise | New `app/prometheus.py`; consumed by a new partial-fragment route, following the existing `field_guide_reachable` precedent in `app/status.py` |
| launchpad ↔ Grafana | No runtime HTTP call — deep links only (URL construction, no request) | Avoids adding Grafana as a second reachability dependency; simpler and matches the "no iframe" decision |
| `infra/observability/` ↔ `charts/field-guide-api` / `charts/launchpad` | Label-selector match only, no object ownership, no Helm dependency relationship | ServiceMonitors reference Services by label; if either app chart is ever uninstalled and reinstalled, the ServiceMonitor keeps working unmodified as long as the labels (`app.kubernetes.io/name`) stay the same, which they do (locked by the `_helpers.tpl` naming convention) |
| Makefile: existing targets ↔ new targets | New targets are pure additions (`.PHONY` list append, new target bodies); `up-mission-control` should be a NEW umbrella that calls `up-all` + `observability-up` + `seed-demo` in sequence, exactly like `up-all` today composes `up` + the launchpad build/load/deploy trio | Do not rename or alter `up`, `up-all`, `smoke`, `smoke-all`, or their bodies; add `smoke-mission-control` alongside `smoke-all` the same way `smoke-all` was added alongside `smoke`/`smoke-launchpad` in Phase 10 |

## Suggested Build Order (dependency-aware)

1. **`infra/observability/kube-prometheus-stack-values.yaml` + `scripts/observability-up.sh`/`observability-down.sh`.** Stand up the trimmed stack manually first (`helm upgrade --install`), verify all pods Running in the `observability` namespace, before writing any launchpad code. This is the highest-uncertainty piece (resource footprint, Helm chart version pinning) and should be de-risked first, in isolation.
2. **ServiceMonitors for field-guide-api and launchpad** (standalone manifests). Apply them, open the Prometheus UI (port-forward), and confirm both targets show `UP` in the Targets page. This is the cheapest possible validation of the "existing Service labels are sufficient" assumption — do this before writing a single line of query code.
3. **Grafana dashboard ConfigMaps (dashboards-as-code)**, one per dashboard, verified via the Grafana UI (port-forward) — confirms the sidecar-discovery wiring independent of anything in launchpad.
4. **Additive Makefile targets: `observability-up`, `observability-down`, `port-forward-grafana`.** Codify steps 1-3 into repeatable commands now, so the rest of the work (and any human reviewer) can bring the stack up/down in one command instead of manual `helm`/`kubectl` calls.
5. **`app/prometheus.py` + `PROMETHEUS_BASE_URL`/`GRAFANA_BASE_URL` config additions** (`app/config.py`, `.env.example`, `charts/launchpad/values.yaml` new keys, `configmap.yaml`/`deployment.yaml` new env entries — additive keys only, same precedent as v1.1's `eventsTtlSeconds` addition to this same chart) — buildable and unit-testable with mocked `requests.get` **without a live cluster**, exactly like the existing `test_status.py` pattern (`mock_requests_get` / `mock_requests_get_unreachable` fixtures). Do this before any UI work so the hermetic test suite covers the new module early.
6. **New metric-cards partial route + template**, wired to `app/prometheus.py`, with the "NO SIGNAL" dimmed-state branch tested exactly like `field_guide_reachable=False` is tested today.
7. **`mission-control.css` + one new `<link>` in `base.html` + hero/metric-card markup in `index.html`.** Purely visual layer, safest to do last since the underlying data plumbing (steps 1-6) is already proven and stable by this point.
8. **`make seed-demo`.** Independent of everything above (only depends on already-shipped v1.1 `/catalog/new` etc.) — can technically be built any time after step 1, but sequencing it near the end means it can immediately be used to populate the newly-built metric cards/dashboards for the final demo screenshots.
9. **`up-mission-control` umbrella target + `smoke-mission-control`.** Last — composes everything above (`up-all` + `observability-up` + `seed-demo`), following the exact compositional style already used by `up-all`/`smoke-all`.

**Why this order:** Steps 1-3 de-risk the highest-uncertainty, most-external part (a third-party Helm chart's behavior in this specific local kind environment) before any code is written against it. Step 5 can proceed in parallel with steps 2-4 once the `PROMETHEUS_BASE_URL` convention is agreed, since its tests are hermetic and don't require the live stack. UI polish (step 7) is deliberately last because it's the lowest-risk, most-iterative part and benefits from having real data (steps 1-6) to render before styling it.

## A Note on "Additive Only" and This Chart's Own Files

`charts/field-guide-api` gets zero touch this milestone — it is scraped purely via label-matching ServiceMonitors and needs nothing new. `charts/launchpad`, however, IS the Mission Control app being enhanced, so it will gain new (not modified) keys: `PROMETHEUS_BASE_URL`/`GRAFANA_BASE_URL` in `values.yaml`/`configmap.yaml`/`deployment.yaml` env block, and a new blueprint/route. This mirrors the project's own v1.1 precedent (`eventsTtlSeconds` was added to this exact chart in v1.1 without being considered a violation of "additive only"). The hard constraint is best read as: no existing key's behavior changes, no existing route's contract changes, no existing Makefile target's body changes — new keys/routes/targets are exactly what "additive" means. Recommend confirming this reading explicitly during roadmap/phase planning so it isn't re-litigated mid-implementation.

## Sources

- [prometheus-community/helm-charts kube-prometheus-stack values.yaml](https://github.com/prometheus-community/helm-charts/blob/main/charts/kube-prometheus-stack/values.yaml) — component enable/disable flags (HIGH confidence)
- [prometheus-community/helm-charts issue #1513 — serviceMonitorSelector label requirement](https://github.com/prometheus-community/helm-charts/issues/1513) and [issue #2051](https://github.com/prometheus-community/helm-charts/issues/2051) — confirms `serviceMonitorSelectorNilUsesHelmValues` default behavior requiring a `release` label on out-of-chart ServiceMonitors (MEDIUM-HIGH confidence, multiple corroborating GitHub issues)
- [prometheus-operator/prometheus-operator issue #149 — `prometheus-operated` governing Service](https://github.com/prometheus-operator/prometheus-operator/issues/149) and related discussion confirming the name is hardcoded in the operator, not release-name-dependent (HIGH confidence)
- [grafana/helm-charts issue #527 — sidecar dashboard ConfigMap provisioning race](https://github.com/grafana/helm-charts/issues/527) and community guidance on one-dashboard-per-ConfigMap (MEDIUM confidence — community-sourced, but consistent across multiple independent write-ups)
- [Grafana sidecar `sidecar.dashboards.enabled` / `grafana_dashboard` label convention](https://medium.com/cloud-native-daily/provision-grafana-dashboards-and-alerts-using-helm-and-sidecars-733dcd223037) (MEDIUM confidence, cross-checked against grafana-operator official docs example)
- [kube-prometheus-stack Grafana default admin secret `<release>-grafana` / `admin-password` key](https://github.com/prometheus-community/helm-charts/issues/4558) and related issues (MEDIUM-HIGH confidence)
- In-repo: `charts/launchpad/templates/_helpers.tpl`, `charts/launchpad/templates/service.yaml`, `charts/field-guide-api/templates/service.yaml` — confirms existing Service labels are already sufficient for ServiceMonitor selectors, verified by direct read (HIGH confidence, primary source)
- In-repo: `apps/launchpad/app/status.py`, `apps/launchpad/app/k8s.py`, `apps/launchpad/tests/test_status.py` — confirms the established graceful-degradation / hermetic-test pattern this milestone's new code must extend (HIGH confidence, primary source)
- In-repo: `Makefile`, `.planning/PROJECT.md` — confirms frozen target list, additive-only precedent (e.g. `eventsTtlSeconds` added to `charts/launchpad/values.yaml` in v1.1) (HIGH confidence, primary source)

---
*Architecture research for: k8s-launchpad v2.0 Observability + Mission Control integration*
*Researched: 2026-07-16*
