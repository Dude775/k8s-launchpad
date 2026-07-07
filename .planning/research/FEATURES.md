# Feature Research

**Domain:** Local IDP Browser Dashboard — v1.1 Product Dashboard (PRD-3)
**Researched:** 2026-07-08
**Confidence:** HIGH for feature scope; MEDIUM for K8s Python client patterns (verified via official kubernetes-client/python examples)

---

## Context

This document replaces the PRD-1 feature research for the v1.1 milestone. PRD-1 is complete. The new
target is `apps/launchpad/` — a separate Flask app serving a browser dashboard that makes k8s-launchpad
visible as a product. The dashboard is **presentation-layer first**: it displays real platform state
(MongoDB, health, K8s) and stores service registrations, but does NOT wire to a real build/deploy
pipeline (that is PRD-2/4 scope).

Constraint: Jinja2 + vendored htmx only. No React, no Vite, no CDN, no build step.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features a reviewer expects to see in any IDP dashboard. Missing one = product feels like a blank web
page, not a platform.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| UI shell: persistent sidebar or topbar, consistent layout across pages | Navigation baseline; without it every page feels disconnected | LOW | Jinja2 `base.html` with `{% block content %}`; sidebar with links to Dashboard, Catalog, Diagnostics |
| Landing page at `/` with platform status cards | Every IDP (Heroku, Port, Backstage) opens on a summary page; this is the "are we operational?" view | LOW | Cards: API health, MongoDB connectivity, launchpad version, service count; each is a colored badge (green/yellow/red) |
| Real data behind status cards (not hardcoded) | A static status card is a lie; it must reflect actual component health | LOW | New `/api/status` endpoint aggregates: `/health/ready` result, MongoDB ping latency, `APP_VERSION` env var, count of registered services |
| Service catalog page at `/catalog` listing registered services | The canonical IDP feature; Backstage, Cortex, Port all lead with this | LOW | Table or card grid of service registrations from MongoDB; name, description, owner, registered date, status badge |
| Onboard/register service form at `/catalog/new` (or modal) | A catalog without intake is read-only and grows only from seeding; the form is the "self-service" moment | LOW-MEDIUM | POST saves to `services` collection in MongoDB; fields: name (required), description, owner/team, git_repo_url, language/framework; fires an activity event on success |
| Form validation with error feedback | Users expect inline validation; silent failure breaks trust | LOW | Flask validates required fields server-side; re-render form with error messages on bad POST; no JS validation needed (htmx re-render is enough) |
| Diagnostics page at `/diagnostics` showing component health | Any platform tool must be self-aware; missing this = can't tell if anything is broken | MEDIUM | In-app checks: MongoDB ping + latency, self `/health` response, config/version; K8s section: pod list + deployment status (see K8s row below) |
| Activity/events feed at `/activity` (or sidebar widget) | Heroku's Events table and every IDP dashboard show "what happened recently"; without it, the platform feels static | MEDIUM | MongoDB `events` collection; display last 20 events newest-first: timestamp, event_type, target service name, message |

### Differentiators (Competitive Advantage)

Features that lift this from "Flask website with a nice template" to "mini-IDP portfolio piece."

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Live status card polling via htmx | Makes the dashboard feel alive; demonstrates htmx competency | LOW | `hx-get="/api/status/fragment" hx-trigger="load, every 30s" hx-swap="outerHTML"` on the status card container; server returns HTML fragment only |
| Kubernetes pod/deployment status in diagnostics via in-cluster ServiceAccount | Shows real K8s API integration; Backstage/Port both do this; no other local IDP demo shows it | MEDIUM | `kubernetes` Python client, `load_incluster_config()`, read pods+deployments in `default` namespace; needs ClusterRole + ClusterRoleBinding in Helm chart; gracefully degrades outside cluster (catches `ConfigException`) |
| Graceful degradation when running outside cluster | Platform works as a demo even without a live kind cluster (e.g., interviewer opens it locally); makes diagnostics honest rather than broken | LOW | Try `load_incluster_config()`, fallback to "running outside cluster — K8s data unavailable" section instead of 500 |
| Status badge color system (green/yellow/red) | Visual affordance; a reviewer understands health at a glance without reading | LOW | CSS utility classes: `.badge-ok`, `.badge-warn`, `.badge-fail`; applied server-side from health state |
| Activity feed fires events from platform actions | Makes the feed feel live; service registration triggers `service_registered` event automatically; not manual logging | LOW | On every `POST /catalog/new` success, insert `{event_type, target, message, ts}` into `events` collection |
| Separate platform app (`apps/launchpad/`) with its own Helm chart | Shows workload/platform separation; demonstrates that the v1.0 Helm chart pattern is reusable | MEDIUM | New Dockerfile, new `charts/launchpad/`, uses same `values.yaml` structure as `field-guide-api`; exercises the PRD-1 values.yaml seam |
| `make dashboard-build/load/deploy` targets | Extends Makefile pattern from v1.0; reviewer sees the same loop works for the new app | LOW | Same pattern: build → load → port-forward; no new tooling needed |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real deployment pipeline behind the onboard form | "The form should do something real" | Out of scope for v1.1 by PRD definition; implementing it means also wiring ArgoCD (PRD-2) or Docker-in-Docker (risky in kind); unfinished pipelines feel worse than honest stubs | Show a "Registration saved — deployment pipeline coming in v1.2" toast/banner; PRD-2 wires it |
| WebSocket / Server-Sent Events for live updates | "Real-time feels polished" | Requires async Flask or a separate SSE handler; significantly increases server complexity; 30s htmx polling is indistinguishable from real-time for a status dashboard | htmx `hx-trigger="every 30s"` achieves the same visual effect |
| Service dependency graph visualization | Backstage has a dependency graph; reviewers recognize it | Backstage dependency graph requires a full graph-rendering library (D3/Cytoscape); out of scope for a single-developer sprint; adds frontend JS complexity | Show dependencies as a plain text list or tag on the service catalog card; defer graph to v2 |
| User authentication (login/session) | "Looks production-ready" | This is a local single-developer tool; adding auth means also managing users, sessions, password resets; adds 2-3x scope | Document "local-use only, no auth by design"; add auth note in README if questioned |
| Full Prometheus metrics charts (Grafana-style) | "Observability" | PRD-4 owns Prometheus + Grafana; building a metrics renderer now would duplicate PRD-4 and create overlapping UI | Display a "metrics preview" row on status page — just the raw `request_count` number fetched from field-guide-api `/metrics` endpoint; label it "full charts in PRD-4" |
| npm / Tailwind / Vite build step | "Modern CSS tooling" | Violates the locked stack (Jinja2 + htmx, no build step); introduces Node.js dependency into what is a Python project | Use a vendored CSS framework (e.g., Pico.css or a minimal custom CSS file, <200 lines); vendor htmx.min.js in `static/vendor/` |
| Pagination on service catalog list | "Scales better" | Portfolio dashboard will have fewer than 20 services; pagination adds form/query complexity for no real benefit | Show all services; add "X registered" count header; defer pagination to when real scale is needed |
| Separate microservice for events/notifications | "Clean architecture" | Adds a second HTTP service, service discovery, container orchestration overhead; a MongoDB collection is sufficient at this scale | Single `events` MongoDB collection accessed directly from the Flask app; no message bus |

---

## Feature Dependencies

```
UI shell (base.html)
    └──required by──> all page routes (Dashboard, Catalog, Diagnostics, Activity)

/api/status endpoint
    └──reads──> existing field-guide-api /health/ready (HTTP call or shared util)
    └──reads──> MongoDB ping (new check in launchpad app)
    └──reads──> APP_VERSION env var
    └──reads──> MongoDB services collection count
    └──consumed by──> landing page status cards (full page render)
    └──consumed by──> /api/status/fragment (htmx polling partial)

/api/status/fragment (htmx partial)
    └──requires──> /api/status data
    └──requires──> htmx.min.js vendored in static/vendor/

Service catalog page (/catalog)
    └──reads──> MongoDB services collection (list all)
    └──requires──> services collection exists (created lazily on first insert)

Onboard form (/catalog/new)
    └──writes──> MongoDB services collection
    └──fires──> events collection insert (service_registered event)
    └──requires──> MongoDB connection

Activity feed (/activity or sidebar widget)
    └──reads──> MongoDB events collection
    └──events populated by──> onboard form submit
    └──events populated by──> diagnostics run (optional: fires diagnostics_run event)

Diagnostics page (/diagnostics)
    └──in-app checks──> MongoDB ping (direct connection from launchpad)
    └──in-app checks──> launchpad /health endpoint (self-call)
    └──K8s section──> kubernetes Python client (load_incluster_config)
    └──K8s section──> requires ClusterRole (get/list pods, deployments) in Helm chart
    └──graceful fallback──> catches ConfigException → renders "outside cluster" message

Kubernetes RBAC (ClusterRole + ClusterRoleBinding + ServiceAccount)
    └──required by──> diagnostics K8s section
    └──lives in──> charts/launchpad/templates/

apps/launchpad/ Flask app
    └──separate from──> apps/field-guide-api/ (no shared code between them)
    └──requires──> its own Dockerfile + charts/launchpad/
    └──reuses pattern from──> charts/field-guide-api/ values.yaml structure
    └──deployed via──> make dashboard-build, make dashboard-load, make dashboard-deploy
```

### Dependency Notes

- **Status cards require a real `/api/status` endpoint, not proxying field-guide-api:** The launchpad
  app manages its own MongoDB connection and runs its own health checks. It may optionally call
  field-guide-api's `/health` endpoint via HTTP (loopback service call) to show that app's status.
  Do not import from field-guide-api — workload/platform separation.

- **htmx polling requires a dedicated partial route:** `/api/status/fragment` must return only the
  HTML fragment for the status card container (no `<html>`, no `<head>`). The full page render at `/`
  and the fragment are separate routes, sharing a Jinja2 macro.

- **Kubernetes client degrades gracefully:** `kubernetes.config.load_incluster_config()` raises
  `kubernetes.config.config_exception.ConfigException` outside a cluster. The diagnostics route must
  wrap this in a try/except and set a flag that the template uses to show the degraded state section.
  This is the correct pattern per the official kubernetes-client/python in-cluster example.

- **Events collection is write-ahead from other features:** The activity feed is downstream of all
  other writes. It requires no special setup — the collection is created lazily by the first insert.
  Seed it with a `platform_started` event on app startup.

---

## MVP Definition

### Launch With (v1.1 complete)

Minimum set for the milestone to be called "demoable as a platform":

- [ ] UI shell with navigation (sidebar or topbar) linking to all pages — layout works before content
- [ ] Landing `/` with status cards backed by real `/api/status` data (not hardcoded)
- [ ] Service catalog page `/catalog` showing registered services from MongoDB
- [ ] Onboard form `/catalog/new` — POST saves to MongoDB, redirects to catalog with success message
- [ ] Diagnostics page `/diagnostics` — MongoDB ping + self-health + version (K8s section as bonus)
- [ ] Activity feed — last 10 events visible, service_registered events fire automatically
- [ ] htmx polling on status cards (30s refresh, no page reload)
- [ ] apps/launchpad/ deploys through `make dashboard-build && make dashboard-load && make dashboard-deploy`
- [ ] Graceful degradation: diagnostics K8s section shows "outside cluster" state, not 500

### Add After Core Is Working (v1.1 polish)

- [ ] Kubernetes pod/deployment status in diagnostics (needs RBAC in Helm chart)
- [ ] Status badge color system applied consistently (green/yellow/red)
- [ ] Activity feed sidebar widget on landing page (not just dedicated `/activity` page)
- [ ] `make dashboard-port-forward` target for easy local access
- [ ] Screenshots in README showing dashboard, catalog, diagnostics pages

### Future Consideration (PRD-2+)

- [ ] Real deployment pipeline triggered from onboard form (PRD-2: ArgoCD sync)
- [ ] Service status linked to live K8s deployment state (PRD-2: post-ArgoCD)
- [ ] Prometheus metrics charts in dashboard (PRD-4: Grafana or custom renderer)
- [ ] Trivy scan results per service (PRD-4: vulnerability scanner)
- [ ] User authentication and access control (final PRD or if open-sourcing)

---

## Feature Prioritization Matrix

| Feature | Portfolio Value | Implementation Cost | Priority |
|---------|----------------|---------------------|----------|
| UI shell (base layout, nav) | HIGH | LOW | P1 |
| `/api/status` endpoint | HIGH | LOW | P1 |
| Landing page with status cards | HIGH | LOW | P1 |
| Service catalog page | HIGH | LOW | P1 |
| Onboard form → saves to MongoDB | HIGH | LOW | P1 |
| Activity/events feed (basic) | HIGH | LOW | P1 |
| Diagnostics: in-app checks | HIGH | LOW | P1 |
| htmx polling on status cards | HIGH | LOW | P1 |
| apps/launchpad/ separate Dockerfile + Helm chart | HIGH | MEDIUM | P1 |
| Graceful K8s degradation outside cluster | HIGH | LOW | P1 |
| Status badge color system | MEDIUM | LOW | P2 |
| K8s pod/deployment list in diagnostics | MEDIUM | MEDIUM | P2 |
| RBAC (ServiceAccount, ClusterRole) in Helm chart | MEDIUM | MEDIUM | P2 |
| Activity feed sidebar widget | MEDIUM | LOW | P2 |
| `make dashboard-*` Makefile targets | MEDIUM | LOW | P2 |
| Metrics preview number on landing page | LOW | LOW | P3 |
| Pagination on catalog list | LOW | MEDIUM | P3 |
| Service dependency tags/links | LOW | LOW | P3 |

**Priority key:** P1 = must have for v1.1 launch; P2 = should have within v1.1; P3 = nice to have, defer.

---

## IDP Competitor Feature Analysis

How real IDPs handle the same features, and what the right-scaled equivalent is for a single-developer
Flask portfolio project.

| Feature | Backstage (full IDP) | Port.io | Heroku Dashboard | Our v1.1 Approach |
|---------|---------------------|---------|-----------------|-------------------|
| Service catalog entry fields | name, description, type, lifecycle, owner, annotations, labels, relations | Custom blueprints; team, environment, tech, custom metadata | App name, stack, region, dyno count | name (required), description, owner, git_repo_url, language — 5 fields, no custom schema |
| Status dashboard | Plugin-based; Datadog, PagerDuty, CI pipelines in sidebar | Customizable widgets; scorecards | App overview: dyno status, recent deploy, error rate | Platform status cards: API health, MongoDB, version, service count — fixed, not plugin-based |
| Health/diagnostics | Catalog freshness, CI build status | Scorecard checks, integration health | Production Check (scaling, logging, alerting enabled?) | MongoDB ping + self-health + version + K8s pod list |
| Activity feed | Catalog entity history, audit log (Auditor Service in backend) | Automation run history, action log | Events table: deploys, config changes, restarts — newest first, actor shown | MongoDB events collection: service_registered, platform_started — no actor (single user) |
| Onboarding form | Software Templates (Scaffolder) — triggers repo creation, CI pipeline | Self-service actions (no-code form → automation) | `heroku apps:create` CLI / dashboard create button | Simple form → MongoDB insert; no pipeline; honest "registered, not deployed" status |
| Live data refresh | Plugin-controlled; most data is cached/polled | Real-time via webhook ingestion | Metrics tab auto-refreshes; event table is static | htmx `hx-trigger="every 30s"` on status fragment — sufficient for local demo |
| Dependency graph | Full graph view with D3-based rendering | Entity relationship map | N/A (app-centric, no cross-service graph) | Not in v1.1 — too complex for scope; defer |

**Key takeaway:** Real IDPs at scale are plugin-driven, webhook-fed, and heavily integrated with CI/CD
and alerting systems. At portfolio scope (single developer, local kind cluster, no pipeline), the right
abstraction is: fixed status cards + simple catalog table + honest "no pipeline yet" onboarding form
+ MongoDB-backed events. The K8s diagnostics section is the unique technical differentiator that
separates k8s-launchpad from a plain Flask CRUD demo.

---

## Service Catalog Entry Schema (MongoDB document)

What `services` collection documents should contain. Informed by Backstage Component entity, Heroku app
overview, and Cortex entity details.

```python
{
    "_id": ObjectId,
    "name": str,            # required; unique; slug-friendly
    "description": str,     # optional; what this service does
    "owner": str,           # optional; team or person name
    "git_repo_url": str,    # optional; not validated; no real pipeline in v1.1
    "language": str,        # optional; python / go / node / etc.
    "status": str,          # "registered" | "deployed" — "registered" is default in v1.1
    "registered_at": datetime,  # set on create
    "updated_at": datetime,     # set on update
}
```

**What NOT to collect in v1.1:** namespace, Docker image tag, ArgoCD app name, Helm release name,
environment (dev/staging/prod). These belong to the deployment pipeline (PRD-2), not the registration
form. Collecting them now with no pipeline to use them creates dead fields.

---

## Activity Event Schema (MongoDB document)

What `events` collection documents should contain. Informed by Heroku Events table (action type,
actor, timestamp) and Backstage Auditor Service (event_type, severity, entityRef).

```python
{
    "_id": ObjectId,
    "event_type": str,      # "service_registered" | "platform_started" | "diagnostics_run" | "health_check_fail"
    "target": str,          # service name or "platform" for platform-level events
    "message": str,         # human-readable string; e.g. "field-guide-api registered"
    "ts": datetime,         # UTC; used for sort order
    "severity": str,        # "info" | "warn" | "error" — drives icon/color in feed
}
```

**Display:** newest-first, last 20 events. No pagination needed at this scale.

---

## `/api/status` Endpoint Response

What the platform status endpoint aggregates and returns. This is what status cards and htmx polling
fragments consume.

```json
{
    "api": { "status": "ok" },
    "mongo": { "status": "ok", "latency_ms": 2 },
    "version": "1.1.0",
    "service_count": 3,
    "field_guide_api": { "status": "ok", "url": "http://field-guide-api/health" }
}
```

`field_guide_api` health is fetched with a short timeout (500ms); on timeout/error, status becomes
`"unreachable"`. This is the correct pattern for a platform watching its own workloads. Use
`requests` with `timeout=0.5` and catch `RequestException`.

---

## Sources

- [Backstage Descriptor Format — catalog entity fields](https://backstage.io/docs/features/software-catalog/descriptor-format/)
- [Backstage Auditor Service — event logging](https://backstage.io/docs/backend-system/core-services/auditor/)
- [Backstage Catalog Audit Events](https://backstage.io/docs/features/software-catalog/audit-events/)
- [Cortex Entity Details Page — what to pin](https://docs.cortex.io/ingesting-data-into-cortex/entities/details)
- [Port Software Catalog guide](https://www.port.io/guide/software-catalog)
- [Heroku Dashboard — app overview sections](https://devcenter.heroku.com/articles/heroku-dashboard)
- [Everything Starts with the Service Catalog — InfraCloud](https://www.infracloud.io/blogs/service-catalog-idp-modeling-guide/)
- [htmx hx-trigger polling patterns](https://htmx.org/attributes/hx-trigger/)
- [kubernetes-client/python in-cluster example](https://github.com/kubernetes-client/python/blob/master/examples/in_cluster_config.py)
- [Harness IDP service onboarding form fields](https://developer.harness.io/docs/internal-developer-portal/tutorials/service-onboarding-with-idp-stage/)

---

*Feature research for: k8s-launchpad v1.1 Product Dashboard (PRD-3)*
*Researched: 2026-07-08*
