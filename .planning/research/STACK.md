# Stack Research

**Domain:** Local Kubernetes IDP — Flask API + Docker + kind + Helm + MongoDB, now adding Prometheus/Grafana observability + control-room UI reskin
**Researched:** 2026-07-04 (v1.0) / updated 2026-07-08 (v1.1 additions) / updated 2026-07-16 (v2.0 additions)
**Confidence:** HIGH (all versions verified against PyPI, official GitHub releases/README/values.yaml, and official docs)

---

## v2.0 Delta: New Additions Only

> The v1.0 stack (Flask 3.1.3, Flask-PyMongo 3.0.1, PyMongo 4.13.2, gunicorn 26.0.0,
> prometheus-flask-exporter 0.23.2, python-dotenv 1.2.2, pytest 9.1.1 + pytest-flask 1.3.0 +
> pytest-cov, kind v0.32.0, registry:3, Helm 3.21.2, multi-stage python:3.11-slim Dockerfile)
> and the v1.1 stack (kubernetes==33.1.0, Flask-WTF 1.3.0, htmx 2.0.10, Pico.css 2.1.1) are
> fully validated and carry over **unchanged**.
>
> This section documents **only what is new** for v2.0: the trimmed kube-prometheus-stack
> observability install, the ServiceMonitor/Grafana-dashboard integration points, the
> Prometheus-HTTP-API client approach for launchpad's native metric cards, and the dark
> "Mission Control" CSS layer over Pico. Nothing here changes existing charts, endpoints,
> or Makefile targets (additive-only, per PROJECT.md hard constraint).

### Core Additions

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `kube-prometheus-stack` (Helm chart) | **87.16.1** (chart), appVersion **v0.92.1** (Prometheus Operator) | Umbrella chart: Prometheus Operator + Prometheus server + Grafana + kube-state-metrics + CRDs, wired together | De-facto standard way to get the Prometheus Operator's `ServiceMonitor`/`PodMonitor` CRD workflow plus Grafana in one install — hand-rolling the operator + Grafana separately means re-solving CRD RBAC and dashboard-provisioning wiring the chart already does. Actively maintained by `prometheus-community` (confirmed via Context7: 816+ code snippets, high source reputation) |
| Prometheus Operator CRDs (bundled `crds` subchart, chart v0.0.0) | ships with 87.16.1 | Installs `ServiceMonitor`, `PodMonitor`, `PrometheusRule`, `Probe`, `Prometheus`, `Alertmanager`, `ThanosRuler` CRDs cluster-wide | `ServiceMonitor` is the exact integration point PRD-4 needs to scrape the existing `/metrics` endpoints on field-guide-api and launchpad — no app-code or chart changes required, satisfying the additive-only constraint |
| Grafana (bundled subchart) | **12.7.2** | Dashboard rendering + HTTP API for provisioning | Bundled version tracks the kube-prometheus-stack release; do NOT install a separate standalone `grafana/grafana` chart alongside it — that produces two Grafana instances and datasource-wiring drift |
| kube-state-metrics (bundled subchart) | **7.8.1** | Exposes cluster object state (pod/deployment/service counts) as Prometheus metrics | Kept **enabled** (unlike Alertmanager/node-exporter) because the "All Systems Online" hero card benefits from pod-readiness/replica-count series that `prometheus-flask-exporter` alone doesn't provide |

**Explicitly disabled (per PROJECT.md Key Decisions, resource budget on kind):**
- `alertmanager.enabled: false` — no alerting UI/routing consumer this milestone; cuts a StatefulSet + Secret + Service
- `nodeExporter.enabled: false` (upstream `prometheus-node-exporter` subchart is v4.56.1) — flaky as a DaemonSet on Docker Desktop kind nodes (hostPath/proc mount quirks); node-level metrics aren't part of v2.0's scope (per-service uptime/latency/error rate)

### New Supporting Library Usage (no new pip package)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `requests` | **2.34.2** (already pinned in `apps/launchpad/requirements.txt` — no version change) | HTTP client for querying the Prometheus HTTP API (`/api/v1/query`, `/api/v1/query_range`) from launchpad's Flask routes for the native metric cards | Use directly — no new dependency needed. A handful of `requests.get(f"{PROMETHEUS_BASE_URL}/api/v1/query", params={"query": promql}, timeout=2)` calls fully covers instant-query needs for uptime %/latency/error-rate cards; response is plain JSON |
| `prometheus-flask-exporter` | 0.23.2 (already installed on both apps — no change) | Source of the PromQL series to query: `flask_http_request_duration_seconds_bucket/_sum/_count` (histogram, labels `method`/`path`/`status`), `flask_http_request_total` (counter), `flask_http_request_exceptions_total` (counter) | Reference these exact metric names in both the Grafana dashboards-as-code JSON and the native Flask-side queries — keeps the two presentations (Grafana panel vs. native card) mathematically identical |

**Deliberately NOT adding:**
- `prometheus-api-client` (PyPI, latest 0.7.2 as of Apr 2026) — a higher-level wrapper around the same HTTP API with pandas/numpy/matplotlib as (optional since 0.7.0) dependencies and built-in aggregation helpers (`get_metric_aggregation`) aimed at ML/anomaly-detection use cases. For "run 3-4 fixed PromQL instant queries and render a number," it's a dependency with no payoff — `requests` (already present) makes the same HTTP call with zero new install surface, consistent with the additive-only/no-build-step philosophy already established for the UI layer

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| Grafana sidecar (`k8s-sidecar`, bundled and auto-configured by `grafana.sidecar.dashboards.*`) | Watches ConfigMaps labeled `grafana_dashboard: "1"` cluster-wide and hot-loads them into Grafana — this is "dashboards-as-code" | kube-prometheus-stack's Grafana values (unlike the standalone `grafana/grafana` chart's defaults) already set `sidecar.dashboards.enabled: true`, `label: grafana_dashboard`, `labelValue: "1"`, `searchNamespace: ALL`. Ship dashboard JSON as plain `ConfigMap` manifests under `infra/observability/dashboards/`, applied alongside (not inside) the Helm release — reproducible on fresh clusters without touching the chart itself |
| `helm repo add prometheus-community https://prometheus-community.github.io/helm-charts` (or OCI `oci://ghcr.io/prometheus-community/charts/kube-prometheus-stack`) | Chart source | Pin the exact chart version (`--version 87.16.1`) in the new `observability-up` Makefile target — this chart releases roughly weekly; an unpinned `helm install` will drift between machine rebuilds and silently change trimmed-values behavior |
| `kubectl get crds \| grep monitoring.coreos.com` | Verification | Useful smoke-test step for `make observability-up`/`smoke-observability`: confirm `servicemonitors.monitoring.coreos.com` exists before applying `ServiceMonitor` manifests, since CRDs install asynchronously relative to `helm install` returning |

### Installation

```bash
# Add/pin the chart repo (one-time, or in Makefile bootstrap)
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install trimmed stack into its own namespace (additive: separate namespace,
# separate helm release — zero interaction with field-guide-api/launchpad releases)
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --version 87.16.1 \
  --namespace observability --create-namespace \
  -f infra/observability/values-trimmed.yaml

# No new Python packages required — requests==2.34.2 already in
# apps/launchpad/requirements.txt covers the Prometheus HTTP API client.
```

### `infra/observability/values-trimmed.yaml` (starting point — tune after first live memory read on kind)

```yaml
# Disabled per v2.0 scope + resource budget (Key Decisions in PROJECT.md)
alertmanager:
  enabled: false
nodeExporter:
  enabled: false

# Kept enabled: cluster-object-state metrics for the hero card
kubeStateMetrics:
  enabled: true

grafana:
  enabled: true
  adminUser: admin
  # Local kind demo only — never a real credential; override via existingSecret
  # if this chart is ever pointed at anything beyond a disposable kind cluster.
  adminPassword: prom-operator
  sidecar:
    dashboards:
      enabled: true          # already true by default in this chart, kept explicit
      label: grafana_dashboard
      labelValue: "1"
  resources:
    requests: { cpu: 50m, memory: 128Mi }
    limits: { cpu: 200m, memory: 256Mi }
  # No Ingress — access via `make port-forward-grafana` only (matches existing
  # port-forward pattern for field-guide-api/launchpad)

prometheusOperator:
  resources:
    requests: { cpu: 50m, memory: 100Mi }
    limits: { cpu: 200m, memory: 256Mi }

prometheus:
  prometheusSpec:
    retention: 24h            # portfolio demo, not a production retention window
    resources:
      requests: { cpu: 100m, memory: 256Mi }
      limits: { cpu: 500m, memory: 512Mi }
    # Let ServiceMonitors from any namespace be picked up (simplifies the
    # infra/observability/ ServiceMonitor manifests targeting the namespace
    # where field-guide-api/launchpad are deployed)
    serviceMonitorSelectorNilUsesHelmValues: false
    podMonitorSelectorNilUsesHelmValues: false

# defaultRules (PrometheusRule alerting rules) aren't useful without
# Alertmanager wired up — trims further CRD objects and rule-eval CPU
defaultRules:
  create: false
```

**Total trimmed footprint (operator + prometheus + grafana + kube-state-metrics, no alertmanager/node-exporter):** roughly 4 pods instead of 6+, well inside a Docker-Desktop-backed kind node's default allocation — verify empirically against the actual host's Docker Desktop memory cap during `make observability-up`, this is the one number that needs a live check rather than a values.yaml guess.

### Alternatives Considered (v2.0)

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|--------------------------|
| `kube-prometheus-stack` umbrella chart | Standalone `prometheus-community/prometheus` + `grafana/grafana` charts installed separately | Only if independent lifecycle/versioning of Prometheus vs. Grafana is needed (e.g. different owning teams) — for a single-operator portfolio project this doubles Helm releases for no benefit |
| `requests` for Prometheus HTTP API | `prometheus-api-client-python` | If the roadmap later adds anomaly detection, forecasting, or multi-metric dataframe correlation (its pandas/numpy-backed strength) — not needed for fixed uptime/latency/error-rate cards |
| ConfigMap sidecar dashboard provisioning (`grafana.sidecar.dashboards`) | `grafana.dashboardProviders` + baked-in dashboard JSON via `--set-file` at install time | If dashboards must be immutable/baked into the release artifact (e.g. regulated environments); the sidecar approach is preferred here because `infra/observability/dashboards/*.yaml` can be edited and reapplied with plain `kubectl apply` without a full `helm upgrade` |
| Native Prometheus-fed metric cards + "Open in Grafana" deep link (already decided in PROJECT.md) | Grafana panel iframes embedded in launchpad | Iframes require Grafana's `allow_embedding`/CSP config plus a stable reachable URL (port-forward or Ingress) at all times — breaks the "graceful NO SIGNAL degradation" requirement when observability isn't installed. Not recommended here |

### What NOT to Add (v2.0)

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Bitnami `grafana`/`prometheus` charts | Bitnami catalog behind Broadcom subscription paywall since Sep 29 2025 (same reason the Bitnami MongoDB chart was avoided in v1.0) | `prometheus-community/kube-prometheus-stack` (fully open, community-maintained) |
| Unpinned `helm install ... prometheus-community/kube-prometheus-stack` (no `--version`) | Chart releases roughly weekly; an unpinned install silently changes CRD versions, default resource shapes, and Grafana version between machine rebuilds — undermines "reproducible on fresh clusters" | Pin `--version 87.16.1` in the Makefile target; bump deliberately |
| `prometheus-api-client-python` as the Flask-side query client | Pulls in a heavier dependency surface (optional pandas/numpy/matplotlib) for what's 3-4 fixed instant PromQL queries; adds an abstraction layer with no payoff | Plain `requests.get(...)` against `/api/v1/query` — already a project dependency |
| Alertmanager + node-exporter in this milestone | Alertmanager needs routing/receiver config with no consumer yet (no alerting UI planned); node-exporter DaemonSet is known-flaky on Docker Desktop kind nodes (hostPath/proc mount access) | Leave both `enabled: false`; revisit node-exporter only if a future milestone needs host-level metrics |
| Grafana iframe embedding in launchpad pages | Requires Grafana reachable at a stable URL at all times (breaks offline/NO-SIGNAL degradation) and needs CSP/`allow_embedding` changes that clash with the "no build step, no CDN, vendored-only" UI philosophy | Native Prometheus-fed cards in launchpad + "Open in Grafana" deep link (opens Grafana directly, no iframe sandbox needed) |
| Raw hex colors scattered through `mission-control.css` | Fights the existing Pico CSS-variable architecture; makes future theme tweaks a find-and-replace exercise | Override `--pico-*` custom properties under an explicit `[data-theme="dark"]` (or forced `<html data-theme="dark">`) selector block, loaded after `pico.min.css` — same pattern Pico's own docs use for building custom color schemes |

### Mission Control Dark CSS Layer

**Approach:** Force `<html data-theme="dark">` (or scope under `[data-theme="dark"]`) and add `apps/launchpad/static/css/mission-control.css`, loaded after the vendored `pico.min.css`, that overrides Pico's `--pico-*` custom properties (`--pico-background-color`, `--pico-color`, `--pico-primary`, `--pico-card-background-color`, etc.) for a control-room palette (near-black background, high-contrast accent for status, dimmed/desaturated treatment for the "NO SIGNAL" degraded state). This is Pico's own documented customization mechanism — all of Pico's styling is driven by CSS custom properties, so no Pico source file needs to be touched, and the override survives future Pico version bumps. No build step, no new vendored asset beyond the one new plain CSS file.

### Stack Patterns by Variant (v2.0)

**If Docker Desktop's kind node is memory-constrained (default WSL2 backend allocation, e.g. under 6GB free):**
- Start from `values-trimmed.yaml` above, then further drop `prometheus.prometheusSpec.retention` to `6h` and/or widen scrape interval if the operator's default `scrapeInterval: 30s` proves too chatty for 2 app targets + kube-state-metrics
- Retention and scrape frequency are the two knobs with the biggest disk/CPU impact on a single-node kind cluster, and neither affects the ServiceMonitor/dashboard wiring being demonstrated

**If dashboards need to survive `make observability-down` / `make observability-up` cycles without re-authoring:**
- Keep dashboard JSON as version-controlled `ConfigMap` YAML in `infra/observability/dashboards/`, not authored ad-hoc in the Grafana UI
- The sidecar re-syncs from labeled ConfigMaps on every pod start — this is what makes "reproducible on fresh clusters" true without a manual re-import step

**If launchpad needs to detect "observability not installed" for the NO-SIGNAL degradation requirement:**
- Have launchpad attempt a short-timeout (`requests.get(..., timeout=1-2)`) call to the Prometheus service DNS name (`http://<release>-kube-prometheus-stack-prometheus.observability.svc.cluster.local:9090`) and catch `ConnectionError`/`Timeout` to flip cards into the dimmed state — same lazy/degrade-gracefully pattern already used for the K8s client in `app/k8s.py` (`(None, None)` disabled signal)
- Mirrors an established, already-tested pattern in the codebase rather than inventing a new failure-handling convention

### Version Compatibility (v2.0 additions)

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `kube-prometheus-stack` 87.16.1 | Kubernetes 1.19+, Helm 3+ | kind v0.32.0's default node image ships Kubernetes 1.33.1 — well within range |
| `kube-prometheus-stack` 87.16.1 | Grafana 12.7.2, kube-state-metrics 7.8.1 (bundled subchart pins) | Don't override subchart versions independently via `--set` unless the umbrella chart's `Chart.yaml` dependency constraint has been confirmed to allow it — mismatched Grafana/dashboard-provisioning API versions can break the sidecar |
| Prometheus HTTP API (`/api/v1/query`) | any Prometheus server bundled by this chart version | Stable, versioned API (`v1`) unchanged across Prometheus 2.x/3.x — safe to hardcode `/api/v1/query` paths in launchpad's client code |
| `requests` 2.34.2 | Flask 3.1.3 / Python 3.11 (existing launchpad stack) | Already installed; no version bump needed |
| CRDs (ServiceMonitor etc., bundled `crds` subchart) | `helm uninstall` does NOT remove CRDs | Not a concern for `make observability-down` if it just does `helm uninstall` (CRDs persisting between down/up cycles is desirable — avoids re-creating CRDs on every `up`). Only relevant if the whole kind cluster is torn down and rebuilt, at which point CRDs are gone too and reinstall recreates them cleanly |

---

## v1.1 Delta: New Additions Only

> The v1.0 stack (Flask 3.1.3, Flask-PyMongo 3.0.1, PyMongo 4.13.2, gunicorn 26.0.0,
> prometheus-flask-exporter 0.23.2, python-dotenv 1.2.2, pytest 9.1.1 + pytest-flask 1.3.0 +
> pytest-cov, kind v0.32.0, registry:3, Helm 3.21.2, multi-stage python:3.11-slim Dockerfile)
> is fully validated and carries over **unchanged** into `apps/launchpad/`.
>
> This section documents **only what is new** for the v1.1 dashboard, K8s-diagnostics,
> and service-catalog features.

---

## New Core Libraries (pip)

### `kubernetes==33.1.0` — Kubernetes Python Client

**Purpose:** In-cluster API queries for the diagnostics section: list pods, check Deployment
status, query ConfigMaps. Provides read-only visibility into the cluster from inside the
launchpad pod.

**Why 33.1.0 specifically:** The kubernetes Python client versioning mirrors the Kubernetes minor
version — client 33.x targets Kubernetes 1.33 (full support, ✓). kind v0.32.0 ships Kubernetes
1.33.1 as its default node image. Using client 36.x (latest at PyPI) against Kubernetes 1.33
is "(+-)" partial compatibility — close enough, but 33.1.0 is the aligned pick and avoids
surprises on API objects that exist in 1.36 but not 1.33.

**Dependency footprint (no aiohttp):** certifi, six, python-dateutil, pyyaml, google-auth,
websocket-client, requests, requests-oauthlib, oauthlib, urllib3, durationpy. All sync,
no async dependencies. Correct for Flask + gunicorn sync workers.

**Python compatibility:** ≥3.10. Matches Python 3.11 runtime.

**Released:** June 9, 2025 (latest in the 33.x line).

**In-cluster config pattern (graceful degradation):**

```python
from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException

def build_k8s_client():
    """Return CoreV1Api if running in a cluster or a kubeconfig is available.
    Returns None when neither is present (e.g. local dev without a cluster).
    Callers must check for None before using the returned client."""
    try:
        config.load_incluster_config()          # uses /var/run/secrets/kubernetes.io/serviceaccount/
    except ConfigException:
        try:
            config.load_kube_config()           # falls back to ~/.kube/config for local dev
        except ConfigException:
            return None
    return client.CoreV1Api()
```

This is the **canonical two-step fallback**. The diagnostics endpoints return a degraded
"cluster unavailable" response when `build_k8s_client()` returns None rather than erroring.

**Why not lighter alternatives (lightkube, kr8s, raw HTTP):**
- lightkube and kr8s are maintained by smaller communities; official client is the K8s SIG-authored library
- Raw HTTP (requests + ServiceAccount token) avoids the package but requires manual token refresh, TLS cert handling, and URL construction — all solved by the official client
- For a portfolio project demonstrating platform-engineering, using the official client is the credible choice

---

### `Flask-WTF==1.3.0` — CSRF + Form Validation

**Purpose:** CSRF protection on the service-catalog registration form (POST `/services/register`).
Provides `FlaskForm` base class and `CSRFProtect` for the whole app.

**Why add it:** The service catalog form is the one user-facing mutating action in v1.1. CSRF
protection is table-stakes for any web form even in a local environment, and Flask-WTF is the
standard Flask ecosystem answer. It integrates with Flask's existing `SECRET_KEY` config — no
new config surface.

**Python ≥3.10, Flask 3.x compatible.** Released April 23, 2026. Requires WTForms (pulled
automatically as a transitive dep).

**How it integrates:** Drop `CSRFProtect(app)` in the app factory alongside `FlaskForm` subclasses.
Templates get `{{ form.hidden_tag() }}` for the CSRF token — works naturally in Jinja2 without
any build step.

**If skipped:** Plain `request.form` POST handling works fine for a local-only deployment, and
htmx AJAX POSTs need the CSRF token passed as a header (Flask-WTF makes this easy via
`hx-headers='{"X-CSRFToken": "{{ csrf_token() }}"}'`). Recommended to include.

---

## New Frontend Assets (vendored static files, no CDN, no build step)

### htmx 2.0.10 — Hypermedia-Driven UI

**Vendor path:** `apps/launchpad/static/vendor/htmx.min.js`

**Download URL (for `make vendor` or manual curl):**
```
https://cdn.jsdelivr.net/npm/htmx.org@2.0.10/dist/htmx.min.js
```

**Why vendor (not CDN link):** The milestone explicitly requires no CDN and offline-friendly
operation. A vendored file in `static/vendor/` is served by gunicorn/Flask and works with no
internet. One curl during dev setup, committed to the repo.

**Size:** ~14KB min+gzip. No dependencies, no build step, no npm.

**Features used in v1.1:**
- `hx-get` + `hx-trigger="every 30s"` — live status card polling without page refresh
- `hx-post` + `hx-target` — service catalog form submission returning htmx fragment
- `hx-swap="innerHTML"` / `hx-swap="outerHTML"` — partial page updates for status and notifications
- OOB swaps (`hx-swap-oob="true"`) — update activity feed independently on form success

**htmx v4 status:** v4.0.0 is in beta as of mid-2026, targeting Summer 2026. Do NOT use v4 beta —
it is incomplete and breaking. Stick with 2.0.10 stable.

**No htmx extensions needed** for v1.1's feature set. The core script covers all required patterns.

---

### Pico.css 2.1.1 — Minimal CSS Framework

**Vendor path:** `apps/launchpad/static/vendor/pico.min.css`

**Download URL:**
```
https://cdn.jsdelivr.net/npm/@picocss/pico@2.1.1/css/pico.min.css
```

**Released:** March 15, 2025.

**Why Pico.css over alternatives:**
- Single CSS file (~30KB), zero JS, zero build step — matches the no-CDN, no-build constraint perfectly
- Styles semantic HTML (headings, tables, forms, buttons, cards via `<article>`) without requiring class soup
- Ships light/dark mode that auto-detects `prefers-color-scheme` — professional look for free
- Cards via `<article>` are directly usable for status cards and service catalog entries
- Forms look correct without any custom CSS — service registration form is ready immediately

**What Pico.css does NOT provide:** Sidebar + topbar dashboard shell layout. Those require
~80–120 lines of hand-written CSS (Flexbox grid: `#layout { display: flex; }`, `#sidebar`,
`#main`, fixed topbar). This is expected and manageable; Pico handles everything else.

**Classless vs full version:** Use the full `pico.min.css` (not the classless variant). The
dashboard needs Pico's grid utilities and component classes (`<article>`, `<progress>`,
`<kbd>`) which are only in the full build.

**Alternatives considered:**
- Water.css: even simpler but no card/grid components — needs more custom CSS for dashboard feel
- Tailwind CSS: excellent but requires a build step (PostCSS/JIT) — violates the no-build constraint
- Pure hand-written CSS: viable but adds ~400+ lines of boilerplate to match Pico's baseline quality
- Bootstrap: too heavy (~30KB CSS + 40KB JS), designed for class-heavy HTML

---

## Jinja2 — No Changes Needed

Jinja2 is Flask's bundled template engine (auto-installed with Flask 3.1.3). No separate
installation. `render_template()`, template inheritance, `{% block %}`, and filters are all
available.

**Pattern for dashboard:** Single base template (`templates/base.html`) with sidebar + topbar
shell; child templates extend it with `{% extends "base.html" %}` and override `{% block content %}`.

**Flash messages:** `flask.flash()` + `get_flashed_messages(with_categories=True)` in
`base.html` — no extra package needed for user feedback after form submission.

---

## Helm Chart Additions — New `charts/launchpad/` Chart

The launchpad app gets its own Helm chart, copied from `charts/field-guide-api/` and modified.
No new pip packages — the RBAC setup is pure Kubernetes YAML inside the chart.

**New templates needed inside `charts/launchpad/templates/`:**

```
serviceaccount.yaml   # ServiceAccount for the launchpad pod
role.yaml             # Role: read-only access to K8s resources
rolebinding.yaml      # Binds the Role to the ServiceAccount
```

**Minimal `role.yaml` for diagnostics feature:**
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: {{ include "launchpad.fullname" . }}-reader
  namespace: {{ .Release.Namespace }}
rules:
  - apiGroups: [""]
    resources: ["pods", "services", "configmaps", "endpoints"]
    verbs: ["get", "list"]
  - apiGroups: ["apps"]
    resources: ["deployments", "replicasets"]
    verbs: ["get", "list"]
```

**Why `Role` + `RoleBinding` (not `ClusterRole`):** The diagnostics feature reads resources in
the launchpad's own namespace, not cluster-wide. Namespace-scoped RBAC follows least-privilege
and avoids granting cluster-wide read access for a dashboard that only cares about its own workloads.

**`deployment.yaml` addition:** Mount the ServiceAccount token by setting
`serviceAccountName: {{ include "launchpad.fullname" . }}` in the pod spec. Kubernetes
automatically mounts the token at `/var/run/secrets/kubernetes.io/serviceaccount/` — the
location `load_incluster_config()` reads from.

---

## Recommended Stack — v1.1 Additions

### New pip Requirements

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| kubernetes | 33.1.0 | K8s API queries from inside pod | Official SIG client; matches K8s 1.33; no aiohttp; handles token refresh, TLS, API discovery |
| Flask-WTF | 1.3.0 | CSRF + form validation | Standard Flask ecosystem; integrates with `SECRET_KEY`; enables safe htmx POSTs via CSRF header |

**`apps/launchpad/requirements.txt` (additions over v1.0 base):**
```text
Flask==3.1.3
Flask-PyMongo==3.0.1
pymongo==4.13.2
gunicorn==26.0.0
prometheus-flask-exporter==0.23.2
python-dotenv==1.2.2
kubernetes==33.1.0
Flask-WTF==1.3.0
WTForms==3.2.2
```

### New Vendored Static Assets

| Asset | Version | Vendor Path | Size |
|-------|---------|-------------|------|
| htmx | 2.0.10 | `apps/launchpad/static/vendor/htmx.min.js` | ~14KB min.gz |
| Pico.css | 2.1.1 | `apps/launchpad/static/vendor/pico.min.css` | ~30KB min |

Download script (add as `make vendor` Makefile target):
```bash
mkdir -p apps/launchpad/static/vendor
curl -sL https://cdn.jsdelivr.net/npm/htmx.org@2.0.10/dist/htmx.min.js \
  -o apps/launchpad/static/vendor/htmx.min.js
curl -sL https://cdn.jsdelivr.net/npm/@picocss/pico@2.1.1/css/pico.min.css \
  -o apps/launchpad/static/vendor/pico.min.css
```

Commit the downloaded files to the repo so the project works offline after initial setup.

### New Helm Templates

| File | Resource | Purpose |
|------|----------|---------|
| `charts/launchpad/templates/serviceaccount.yaml` | ServiceAccount | Pod identity for K8s API auth |
| `charts/launchpad/templates/role.yaml` | Role | Read-only verbs on pods, deployments, services, configmaps |
| `charts/launchpad/templates/rolebinding.yaml` | RoleBinding | Binds reader Role to ServiceAccount |

---

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| React / Vue / Svelte | Requires npm build step, node_modules, Vite/webpack — violates locked no-build constraint | Jinja2 + vendored htmx (locked decision) |
| CDN links for htmx or Pico.css | Breaks offline operation; external dependency for a local platform | Vendor files in `static/vendor/`, commit to repo |
| htmx v4.0.0-beta | Pre-release, incomplete, breaking changes from 2.x — targeting Summer 2026 final | htmx 2.0.10 stable |
| kubernetes==36.x | Client 36 targets K8s 1.36; partial compat (+-) with 1.33 that kind v0.32.0 runs | kubernetes==33.1.0 (aligned with K8s 1.33) |
| lightkube / kr8s | Smaller community, less API coverage, no meaningful advantage over official client for this use case | kubernetes==33.1.0 (official) |
| Raw HTTP for K8s API | Manual token refresh, TLS management, URL construction — reinvents the wheel that the official client solves | kubernetes==33.1.0 |
| ClusterRole / ClusterRoleBinding | Grants cluster-wide read access; overkill for a dashboard reading its own namespace | Namespace-scoped Role + RoleBinding |
| celery / redis | No background jobs in v1.1 scope; activity feed is synchronous event writes | MongoDB events collection with `find().sort("created_at", -1)` |
| flask-login / flask-jwt | No authentication in v1.1 scope; local-only platform | None (no auth in v1.1) |
| Tailwind CSS | Requires PostCSS/JIT build step — violates no-build constraint | Pico.css 2.1.1 + minimal custom CSS |
| Bootstrap | ~70KB JS + CSS, class-heavy HTML, overkill for a local dashboard | Pico.css 2.1.1 |
| Jinja2 (separate install) | Already bundled with Flask 3.x; pinning separately creates version conflict risk | Use Flask's bundled Jinja2 |
| aiohttp / Quart / Starlette | Async Flask variants; gunicorn sync workers are the locked pattern; adds complexity without benefit | gunicorn + Flask sync (unchanged) |
| htmx extensions (json-enc, preload, response-targets) | Not needed for v1.1's feature set (polling, form POST, OOB swap) | Core htmx only |

---

## Version Compatibility Matrix (v1.1 additions)

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| kubernetes 33.1.0 | Kubernetes 1.33.x (✓ full), Python ≥3.10 | Matched to kind v0.32.0 default node image (K8s 1.33.1) |
| kubernetes 33.1.0 | requests, urllib3 ≥1.24.2, pyyaml ≥5.4.1 | No aiohttp dep in 33.x; safe for sync Flask |
| Flask-WTF 1.3.0 | Flask 3.x, WTForms 3.2.2, Python ≥3.10 | April 2026; officially supports Flask 3 |
| WTForms 3.2.2 | Flask-WTF 1.3.0 | Pulled as transitive dep; pin for reproducibility |
| htmx 2.0.10 | All modern browsers; no IE11 | 2.x dropped IE; targets Chrome/Firefox/Safari LTS |
| Pico.css 2.1.1 | All modern browsers, CSS Grid/Flexbox | March 2025; zero JS; no browser polyfills needed |

---

## Unchanged from v1.0 / v1.1

The following are unchanged and do **not** need re-research for v2.0:

- Python 3.11 runtime, Flask 3.1.3, Flask-PyMongo 3.0.1, PyMongo 4.13.2
- gunicorn 26.0.0 (1 worker per pod pattern)
- prometheus-flask-exporter 0.23.2 on both apps (the scrape target this milestone consumes)
- python-dotenv 1.2.2
- pytest 9.1.1 + pytest-flask 1.3.0 + pytest-cov
- multi-stage `python:3.11-slim` Dockerfile, non-root UID 10001
- kind v0.32.0 + registry:3 local registry (no cluster changes)
- Helm 3 chart structure for `charts/field-guide-api/` and `charts/launchpad/` (untouched — new observability wiring lives in `infra/observability/`, not inside these charts)
- Makefile POSIX patterns, `MSYS_NO_PATHCONV=1`, `.gitattributes` LF enforcement
- MongoDB in-cluster manifests
- kubernetes==33.1.0, Flask-WTF 1.3.0, htmx 2.0.10, Pico.css 2.1.1 (base layer that `mission-control.css` styles on top of)

---

## Sources

**v2.0 additions:**
- `/prometheus-community/helm-charts` (Context7) — chart identity, code-snippet count, source reputation confirmation
- [prometheus-community/helm-charts Chart.yaml](https://raw.githubusercontent.com/prometheus-community/helm-charts/main/charts/kube-prometheus-stack/Chart.yaml) — chart version 87.16.1, appVersion v0.92.1, subchart pins (grafana 12.7.2, kube-state-metrics 7.8.1, prometheus-node-exporter 4.56.1) (HIGH confidence)
- [prometheus-community/helm-charts values.yaml](https://raw.githubusercontent.com/prometheus-community/helm-charts/main/charts/kube-prometheus-stack/values.yaml) — `alertmanager.enabled`, `nodeExporter.enabled`, `grafana.sidecar.dashboards.*`, `defaultRules.create` default keys/values (HIGH confidence)
- [prometheus-community/helm-charts README.md](https://raw.githubusercontent.com/prometheus-community/helm-charts/main/charts/kube-prometheus-stack/README.md) — Kubernetes 1.19+/Helm 3+ requirement, CRD install/upgrade behavior, component-disable flags (HIGH confidence)
- [Artifact Hub — kube-prometheus-stack](https://artifacthub.io/packages/helm/prometheus-community/kube-prometheus-stack) — version cross-check, OCI install path `oci://ghcr.io/prometheus-community/charts/kube-prometheus-stack` (HIGH confidence)
- [prometheus-api-client PyPI](https://pypi.org/project/prometheus-api-client/) — latest 0.7.2 (Apr 2026), optional pandas/numpy/matplotlib since 0.7.0 (MEDIUM confidence)
- [prometheus_flask_exporter README](https://raw.githubusercontent.com/rycus86/prometheus_flask_exporter/master/README.md) — default metric names/labels (`flask_http_request_duration_seconds`, `flask_http_request_total`, `flask_http_request_exceptions_total`) (HIGH confidence — matches already-deployed library behavior)
- [Pico CSS — Color schemes docs](https://picocss.com/docs/color-schemes) and [CSS variables docs](https://picocss.com/docs/css-variables) — `data-theme="dark"` mechanism, `--pico-*` variable override pattern (HIGH confidence)
- Community/blog cross-checks (MEDIUM confidence, used only for default service-naming/credential conventions, not version numbers): general Prometheus/Grafana Helm deployment writeups found via WebSearch (e.g. OneUptime kube-prometheus-stack guides) — verify exact in-cluster Service DNS names with `kubectl get svc -n observability` once installed, since they depend on the Helm release name chosen at implementation time

**v1.0/v1.1 (carried over):**
- [kubernetes PyPI](https://pypi.org/project/kubernetes/) — version 36.0.2 latest overall; 33.1.0 is latest 33.x (Jun 2025) (HIGH confidence)
- [kubernetes-client/python README](https://github.com/kubernetes-client/python/blob/master/README.md) — compatibility matrix; client 33.x = K8s 1.33 (✓) (HIGH confidence)
- [kubernetes 33.1.0 on PyPI](https://pypi.org/pypi/kubernetes/33.1.0/json) — no aiohttp dep confirmed; all sync deps; Python ≥3.10 (HIGH confidence)
- [kubernetes in_cluster_config example](https://github.com/kubernetes-client/python/blob/master/examples/in_cluster_config.py) — `load_incluster_config()` pattern (HIGH confidence)
- [Flask-WTF PyPI](https://pypi.org/project/Flask-WTF/) — version 1.3.0, April 23, 2026, Python ≥3.10 (HIGH confidence)
- [htmx.org homepage](https://htmx.org/) — 2.0.10 confirmed as current stable; v4 in beta targeting Summer 2026 (HIGH confidence)
- [htmx GitHub releases](https://github.com/bigskysoftware/htmx/releases) — 2.0.x stable release line confirmed (HIGH confidence)
- [Pico.css GitHub releases](https://github.com/picocss/pico/releases) — v2.1.1 released March 15, 2025 (HIGH confidence)
- [Pico.css classless docs](https://picocss.com/docs/classless) — classless vs full version distinction (HIGH confidence)

---

*Stack research for: k8s-launchpad PRD-1 Foundation (v1.0) + PRD-3 Product Dashboard (v1.1) + PRD-4 Observability/Mission Control (v2.0)*
*Researched: 2026-07-04 (v1.0) / 2026-07-08 (v1.1 delta) / 2026-07-16 (v2.0 delta)*
