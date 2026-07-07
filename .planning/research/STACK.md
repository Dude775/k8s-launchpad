# Stack Research

**Domain:** Local Kubernetes IDP Foundation — Flask API + Docker + kind + Helm + MongoDB
**Researched:** 2026-07-04 (v1.0) / updated 2026-07-08 (v1.1 additions)
**Confidence:** HIGH (all versions verified against PyPI, official GitHub releases, and official docs)

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

## Unchanged from v1.0

The following are unchanged and do **not** need re-research for v1.1:

- Python 3.11 runtime, Flask 3.1.3, Flask-PyMongo 3.0.1, PyMongo 4.13.2
- gunicorn 26.0.0 (1 worker per pod pattern)
- prometheus-flask-exporter 0.23.2 (launchpad app gets its own `/metrics`)
- python-dotenv 1.2.2
- pytest 9.1.1 + pytest-flask 1.3.0 + pytest-cov
- multi-stage `python:3.11-slim` Dockerfile, non-root UID 10001
- kind v0.32.0 + registry:3 local registry (no cluster changes)
- Helm 3 chart structure (new `charts/launchpad/` mirrors `charts/field-guide-api/`)
- Makefile POSIX patterns, `MSYS_NO_PATHCONV=1`, `.gitattributes` LF enforcement
- MongoDB in-cluster manifests (shared with field-guide-api or replicated in launchpad chart)

---

## Sources

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

*Stack research for: k8s-launchpad PRD-1 Foundation (v1.0) + PRD-3 Product Dashboard (v1.1)*
*Researched: 2026-07-04 (v1.0) / 2026-07-08 (v1.1 delta)*
