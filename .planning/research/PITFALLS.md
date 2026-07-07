# Pitfalls Research

**Domain:** Adding an IDP dashboard (Flask+htmx, K8s API diagnostics, shared MongoDB, status aggregation) to an existing single-app local Kubernetes platform (k8s-launchpad v1.0)
**Researched:** 2026-07-08
**Confidence:** HIGH — pitfalls derived from the actual v1.0 codebase (Makefile, chart templates, conftest.py) plus verified library documentation patterns

---

## Critical Pitfalls

### Pitfall 1: Makefile variable collision — second app overrides first app's build/deploy targets

**What goes wrong:**
The existing Makefile defines `IMAGE`, `RELEASE`, and `CHART` as top-level variables defaulting to `field-guide-api` values. Adding a `make build` and `make deploy` for `launchpad` by changing those defaults — or adding targets without namespacing — means `make deploy` now deploys the dashboard and leaves no obvious way to redeploy the field-guide API without manually passing every override. The existing smoke test and port-forward targets silently target the wrong release.

**Why it happens:**
The v1.0 Makefile was designed for a single app. The `IMAGE`, `RELEASE`, and `CHART` variables at the top are the only coordination point. Developers add a second set of targets, realize the defaults conflict, and either change the defaults (breaking the first app) or add ad-hoc targets that duplicate logic.

**How to avoid:**
Namespace every variable for both apps: `FGA_IMAGE`, `FGA_RELEASE`, `FGA_CHART` for field-guide-api; `LP_IMAGE`, `LP_RELEASE`, `LP_CHART` for launchpad. Keep the original top-level variable names removed or aliased to avoid ambiguity. Add explicit targets: `build-launchpad`, `deploy-launchpad`, `smoke-launchpad`, `port-forward-launchpad`. The shared `make up` composite target must sequence both apps: `cluster-up build-fga load-fga deploy-fga build-launchpad load-launchpad deploy-launchpad`.

**Warning signs:**
- `make deploy` changes the running Helm release from `field-guide-api` to `launchpad` silently
- `make smoke` tests the wrong service (port-forward targets `svc/field-guide-api` but dashboard is on `svc/launchpad`)
- `helm list` shows only one release instead of two after `make up`

**Phase to address:** Phase: Monorepo scaffold for second app (first task of v1.1 — before any code is written)

---

### Pitfall 2: Helm Service selector collision between two charts in the same namespace

**What goes wrong:**
The new `launchpad` chart is created with `helm create charts/launchpad`, and the developer forgets to change the `app.kubernetes.io/name` value in the generated helpers. Both charts end up with identical `selectorLabels` — `app.kubernetes.io/name: launchpad` and `app.kubernetes.io/instance: launchpad`, but if the release name or chart name collide with the existing chart's pattern, the Service `selector` may route to the wrong pods. The v1.0 chart `_helpers.tpl` uses `app.kubernetes.io/name: {{ include "field-guide-api.name" . }}` derived from Chart.Name — the new chart must derive from its own Chart.Name.

More specifically: the `mongodb.selectorLabels` helper in the v1.0 chart generates `app.kubernetes.io/name: field-guide-api-mongodb`. If the launchpad chart also bundles MongoDB with a MongoDB deployment that carries any overlapping selector labels (e.g., `app.kubernetes.io/instance: launchpad` but `app.kubernetes.io/name: launchpad-mongodb`), Kubernetes Services won't cross-select — but if both charts are installed in the same namespace and a developer copies a Service selector verbatim from one chart to another without renaming, pods get wrong traffic.

**Why it happens:**
`helm create` generates a chart with `{{ .Chart.Name }}` in helpers. If the developer edits the chart templates but not `Chart.yaml`'s `name` field, or copies templates from the v1.0 chart without renaming the Helm template function names (`field-guide-api.selectorLabels` → `launchpad.selectorLabels`), selector strings can collide.

**How to avoid:**
- The new chart's `Chart.yaml` name must be `launchpad`, not `field-guide-api`
- All `_helpers.tpl` function names must use the chart's own prefix: `launchpad.fullname`, `launchpad.selectorLabels`, `launchpad.mongodb.fullname`
- After `helm install`, run `kubectl get ep` on both Services — endpoints must list only the correct pod IPs
- The launchpad's MongoDB (or shared MongoDB connection) must use a unique service name — do not share the `field-guide-api-mongodb` Service hostname unless intentionally cross-chart (see Pitfall 8)

**Warning signs:**
- `kubectl get endpoints` shows a Service with zero endpoints despite pods Running
- Field-guide-api returns HTML fragments instead of JSON (routing to launchpad pods)
- `helm lint` passes but `kubectl describe svc` shows no endpoints for one of the two Services

**Phase to address:** Phase: Launchpad Helm chart scaffold

---

### Pitfall 3: Kubernetes Python client blocking the single gunicorn worker

**What goes wrong:**
The dashboard's status/diagnostics endpoints call `kubernetes.client.CoreV1Api().list_namespaced_pod(...)` synchronously from a Flask route handler. The kubernetes Python client's HTTP calls use `urllib3` and default to no client-side timeout (`_request_timeout=None`). When the kind API server is slow (cluster under load, resuming from laptop sleep) or unreachable, the urllib3 call hangs indefinitely. With `--workers 1` (the correct setting for this project), the single gunicorn worker is blocked. Every subsequent HTTP request to the dashboard — including htmx polls from open browser tabs, the Kubernetes readinessProbe, and health checks — queues behind the hung worker. gunicorn's worker timeout (default 30s) kills and restarts the worker, logging `[CRITICAL] WORKER TIMEOUT`. The pod enters a restart loop.

**Why it happens:**
The kubernetes Python client does not set a default timeout. The gunicorn `--timeout` setting (worker request timeout) measures time since the last I/O acknowledgement, not total wall-clock time — a hanging urllib3 socket does not generate I/O, so gunicorn does not detect the hang until 30s. Meanwhile every htmx `hx-trigger="every 5s"` poll lands on the stuck worker.

**How to avoid:**
Always set `_request_timeout` on every kubernetes client call:
```python
v1.list_namespaced_pod(namespace="default", _request_timeout=5)
```
Wrap all K8s client calls in `try/except ApiException` plus a broad `except Exception` fallback that returns a degraded status dict instead of propagating exceptions to Flask's error handler. Apply an application-level timeout guard (e.g., `concurrent.futures.ThreadPoolExecutor` with `.result(timeout=5)`) if the route is ever called under htmx polling.

**Warning signs:**
- `[CRITICAL] WORKER TIMEOUT` appears in gunicorn logs during cluster restarts or laptop sleep/wake
- Dashboard becomes unresponsive when the kind cluster is paused (Docker Desktop container paused)
- `make smoke` hangs on the dashboard endpoints after `docker pause` of the cluster

**Phase to address:** Phase: K8s API diagnostics implementation

---

### Pitfall 4: `load_incluster_config()` called at import time — app fails to start outside cluster

**What goes wrong:**
The kubernetes client initialization is placed at module level (outside a function), like:
```python
# k8s_client.py — BAD
from kubernetes import client, config
config.load_incluster_config()   # called at import
v1 = client.CoreV1Api()
```
When `conftest.py` imports `create_app`, Python imports `k8s_client.py`, which calls `load_incluster_config()`. Outside a pod, this raises `kubernetes.config.config_exception.ConfigException: Service host/port is not set.` — the entire test suite fails with an import error before a single test runs.

**Why it happens:**
The pattern comes from the kubernetes Python client's example files, which show `config.load_incluster_config()` at module scope. Developers copy this pattern without accounting for the local dev / test environment where `/var/run/secrets/kubernetes.io/serviceaccount/token` doesn't exist.

**How to avoid:**
Always initialize the kubernetes client lazily inside a factory function and catch `ConfigException`:
```python
# k8s_client.py — CORRECT
from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException

_k8s_available = False
_v1 = None

def get_k8s_client():
    global _k8s_available, _v1
    if _v1 is not None:
        return _v1, _k8s_available
    try:
        config.load_incluster_config()
        _k8s_available = True
    except ConfigException:
        _k8s_available = False
        return None, False
    _v1 = client.CoreV1Api()
    return _v1, True
```
Routes check `_k8s_available` and return a degraded JSON response when False. Tests mock `get_k8s_client` to return `(None, False)` without touching the cluster.

**Warning signs:**
- `pytest` exits immediately with `ConfigException: Service host/port is not set` before any test runs
- `create_app()` in conftest fails with an import error from the k8s module
- The app works when `kubectl exec`-ed into but fails on the developer's machine with `make test`

**Phase to address:** Phase: K8s API diagnostics implementation (establish the lazy-init pattern before writing any route that uses the client)

---

### Pitfall 5: Dashboard `/health` depending on downstream services causes readinessProbe cascades

**What goes wrong:**
The launchpad `/health` endpoint is implemented to check: MongoDB ping + K8s API ping + field-guide-api's `/health` (HTTP call). The Helm chart's `readinessProbe` calls `/health` every 5 seconds. When the K8s API is slow (Pitfall 3) or the field-guide-api pod is restarting, `/health` blocks for up to the timeout. The readinessProbe times out (`timeoutSeconds: 3` but the upstream call takes 5s). Kubernetes marks the launchpad pod NotReady and stops routing traffic. The pod then can't be reached by anything else, including the developer trying to debug why the dashboard is down.

The recursive case: if field-guide-api's `/health` also checks MongoDB, and MongoDB is briefly slow, both apps mark themselves NotReady simultaneously. The cluster appears fully broken during a routine MongoDB restart.

**Why it happens:**
Developers naturally want the health endpoint to show "everything is green." The Kubernetes probe does not distinguish between "this pod is healthy" and "all services this pod depends on are healthy." Liveness and readiness probe design is often misunderstood as a system health check rather than a pod health check.

**How to avoid:**
Split health semantics strictly:
- `GET /health` (readiness): checks ONLY this pod's own dependencies — MongoDB ping with 2s timeout. Does NOT call field-guide-api. Does NOT call K8s API.
- `GET /api/status` (platform status): checks field-guide-api reachability, K8s API, and other platform components. Returns degraded JSON gracefully when anything is slow. This endpoint is called by the dashboard's htmx status cards, NOT by the readinessProbe.

The `_helpers.tpl` pattern from v1.0 already implements this correctly for field-guide-api — replicate it exactly for launchpad.

**Warning signs:**
- `kubectl get pod launchpad-xxx` shows `0/1 READY` during a MongoDB restart
- `kubectl describe pod launchpad-xxx` shows `Readiness probe failed: Get "http://...:8000/health": context deadline exceeded`
- Dashboard becomes inaccessible whenever any downstream service hiccups

**Phase to address:** Phase: Launchpad app scaffold and `/health` endpoint

---

### Pitfall 6: htmx polling + synchronous K8s API = worker starvation

**What goes wrong:**
The dashboard's status cards use `hx-trigger="every 5s"` to poll `/api/status`. This endpoint calls the kubernetes Python client synchronously (see Pitfall 3). With one browser tab open: 12 requests/minute. Each request that hits a slow K8s API holds the single gunicorn worker for up to the timeout. A second browser tab doubles the rate to 24/minute. The worker cannot complete one request before the next arrives. The browser shows spinners on the status cards; htmx queues requests; gunicorn logs worker timeouts; the dashboard falls over.

**Why it happens:**
htmx polling appears harmless in demos with fast mock responses. The danger emerges when the polled endpoint does real I/O. The `hx-trigger="every 5s"` attribute has no built-in backoff, no visibility check, and no request debouncing — it fires regardless of whether the previous request completed.

**How to avoid:**
- Keep the `/api/status` K8s client call under a strict 3-second timeout (see Pitfall 3)
- Use `hx-trigger="every 10s"` minimum — never below 5s for endpoints doing real I/O
- Add `hx-trigger="every 10s [document.visibilityState !== 'hidden']"` to suppress polling in background tabs
- Cache the K8s API response in-process (a module-level dict with a TTL of 8–10 seconds) so concurrent polls within the same interval don't each make a new API call
- Alternative: use htmx load polling (`hx-trigger="load delay:10s"`) which chains requests sequentially (next fires only after previous response), preventing concurrent accumulation

**Warning signs:**
- `/api/status` responds fast when called directly with `curl` but the browser shows permanent spinners under normal use
- gunicorn logs show `[CRITICAL] WORKER TIMEOUT` at the same cadence as the poll interval
- `kubectl get pod launchpad` shows `RESTARTS: 1` after a few minutes of browser use

**Phase to address:** Phase: htmx UI and status polling implementation

---

### Pitfall 7: Unbounded MongoDB activity/events feed collection

**What goes wrong:**
Every platform event (page load, service registration, status check, K8s API query) writes a document to a `platform_events` collection. There is no TTL index, no capped size, and no document limit. After a weekend of demos, the collection has 200k+ documents. `GET /api/events` does a full collection scan with no limit/sort index, taking seconds. The events page hangs. The collection's WiredTiger storage grows unbounded.

**Why it happens:**
Inserting an event document is a one-liner. Adding a TTL index is a separate step developers defer to "later" — but "later" never arrives in a local dev project. Capped collections require upfront planning because you cannot add a TTL index to a capped collection after the fact, and you cannot convert a regular collection to capped without dropping it.

**How to avoid:**
Decide the retention strategy before writing the first event document:

Option A (recommended): Regular collection with TTL index. At app startup (or Helm init job), create the index:
```python
db.platform_events.create_index("created_at", expireAfterSeconds=604800)  # 7 days
```
Always include `created_at: datetime.utcnow()` in every event document. Always query with `.sort("created_at", -1).limit(100)`.

Option B: Capped collection (max 10k documents, 50MB):
```python
db.create_collection("platform_events", capped=True, size=52428800, max=10000)
```
Note: capped collections and TTL indexes are mutually exclusive — pick one.

Both: Add a compound index on `(event_type, created_at)` to support filtered queries. Query always includes `.limit()` — never unbounded `find()`.

**Warning signs:**
- `db.platform_events.count_documents({})` returns > 10k after a day of use
- `GET /api/events` response time grows over multiple demo sessions
- `mongomock` tests pass but real MongoDB shows slow queries under load (mongomock doesn't enforce collection size)

**Phase to address:** Phase: Activity feed and MongoDB schema design

---

## Moderate Pitfalls

### Pitfall 8: Shared MongoDB — database name or collection name collision

**What goes wrong:**
The `launchpad` app uses `mongoDbName: fieldguide` in its Helm values (copied from the field-guide-api chart) and writes service registrations to a `services` collection. The field-guide-api also happens to use a `services` collection for some future feature, or the launchpad writes to `entries` by mistake. Both apps share the same MongoDB pod. Cross-collection contamination is silent: inserts succeed, but one app reads the other's documents.

**Why it happens:**
The values.yaml template pattern from v1.0 is designed to be copied. The `mongoDbName` field defaults to `fieldguide`. Developers set the launchpad chart's `mongoDbName` to `launchpad` but forget to update the runtime `MONGO_DBNAME` environment variable, or vice versa.

**How to avoid:**
- The launchpad chart must have `mongoDbName: launchpad` as its default — never `fieldguide`
- Collection names must be scoped: `platform_services`, `platform_events` in the `launchpad` database vs `entries` in the `fieldguide` database
- If the launchpad connects to the field-guide-api's MongoDB pod (shared instance, no separate MongoDB), the MONGO_URI in the launchpad's Secret must specify `/launchpad` as the database, not `/fieldguide`
- At startup, log `app.config["MONGO_DBNAME"]` so the developer can verify which database the app connected to

**Warning signs:**
- `db.fieldguide.entries` appears in the launchpad app's MongoDB queries (wrong database)
- `kubectl exec -it <mongodb-pod> -- mongosh` → `db.launchpad.getCollectionNames()` returns empty despite app running
- Field-guide-api entries disappear after launchpad writes to the same collection

**Phase to address:** Phase: Launchpad app factory and MongoDB integration

---

### Pitfall 9: htmx fragment vs full-page route confusion — browser reload breaks the page

**What goes wrong:**
A route returns an HTML fragment (a `<div>` with status cards, no `<head>` or `<body>`). htmx swaps it into the DOM correctly during normal navigation. But if the user bookmarks the fragment URL, refreshes the page, or htmx pushes the fragment URL to history via `hx-push-url`, the browser loads the raw fragment on next visit — a bare `<div>` with no CSS, no JS, no layout. The page appears broken.

**Why it happens:**
In a Jinja2 + htmx app without a JavaScript SPA router, every route must decide: does it serve a full page (extending `base.html`) or a fragment? When `hx-boost` is active, `GET` navigation returns fragments and htmx swaps them. If the same URL is hit directly (via browser address bar, curl, or htmx request error recovery), it must still return the full page. Developers write two separate routes instead of detecting the request type.

**How to avoid:**
- Distinguish routes at the template level using Flask's `request.headers.get("HX-Request")` header (htmx sets this on all AJAX requests):
```python
@bp.route("/status")
def status():
    if request.headers.get("HX-Request"):
        return render_template("_status_cards.html", ...)   # fragment only
    return render_template("status.html", ...)              # full page wrapping the fragment
```
- Use a naming convention: templates prefixed with `_` are fragments never served as standalone pages
- Do NOT use `hx-push-url` on fragment routes — only push URL when the target is a full page
- Test by navigating directly to fragment URLs in a fresh browser tab (no htmx context)

**Warning signs:**
- Page looks correct under normal navigation but broken after browser refresh
- Fragment HTML appears as raw text in the browser when the URL is bookmarked and revisited
- `curl http://localhost:8080/api/status` returns a bare `<div>` without `<html>` wrapper

**Phase to address:** Phase: Jinja2 template structure and htmx route design

---

### Pitfall 10: Port collision on `make port-forward` with two services

**What goes wrong:**
The existing `make port-forward` target forwards `svc/field-guide-api` to `localhost:8080`. The developer adds a `make port-forward` for the launchpad also on port 8080. The second `kubectl port-forward` fails with `bind: address already in use` — silently when launched in the background. The developer sees the field-guide-api on 8080 and assumes the launchpad is at 8080 too, getting confused about which service they're testing.

**Why it happens:**
The Makefile has a single `port-forward` target. The developer adds a second target with the same port. Background-launched `kubectl port-forward` processes fail silently (stdout redirected to `/dev/null`).

**How to avoid:**
Assign fixed, distinct ports and document them in `make help`:
- `port-forward-fga`: `localhost:8080` → `svc/field-guide-api:80`
- `port-forward-launchpad`: `localhost:8081` → `svc/launchpad:80`

The `make smoke` targets must use the correct port for each service. The README and `make help` documentation must clearly show which port each service uses. Add a `port-forward-all` target that starts both in the background with a verification step.

**Warning signs:**
- `make port-forward-launchpad` exits immediately with no error but no traffic reaches the service
- `lsof -i :8080` shows two `kubectl` processes competing for the same port
- Developer is testing the wrong service and doesn't realize it

**Phase to address:** Phase: Makefile extension for second app

---

### Pitfall 11: mongomock gap — TTL indexes and capped collections not fully supported

**What goes wrong:**
Tests use `mongomock.MongoClient()` (established pattern from v1.0). The launchpad app uses `create_index(..., expireAfterSeconds=604800)` at startup and capped collection creation. mongomock accepts these calls without error but does not enforce TTL expiration or collection size limits. Test coverage for the events feed appears to pass, but the actual behavior on real MongoDB differs: capped collections refuse inserts beyond `max` documents (unexpected for the developer who only tested with mongomock), and TTL expiration background jobs don't run during tests — the "event expires after 7 days" behavior is never tested.

**Why it happens:**
mongomock implements the MongoDB wire protocol surface but not background threads (TTL cleanup) or storage constraints (capped size). Developers assume green tests mean the production behavior is verified.

**How to avoid:**
- Write unit tests that assert the TTL index exists (check `collection.index_information()`) rather than testing expiry timing
- Write integration tests for the events feed using a real mongo:7 container (e.g., via `pytest-docker` or a Makefile `make test-integration` target)
- Document explicitly in `conftest.py` that mongomock does not enforce TTL or capped collection limits
- Add a startup check in the app that logs `"platform_events TTL index: OK"` when the index exists and `"WARNING: TTL index missing"` otherwise

**Warning signs:**
- `test_event_expires_after_ttl` passes but events never disappear in the running deployment
- A test creating a capped collection with `max=10` succeeds even when inserting 1000 documents
- The events API returns thousands of documents despite expected TTL cleanup

**Phase to address:** Phase: Activity feed implementation and test design

---

### Pitfall 12: Second Helm chart's MongoDB — cross-chart hostname wiring mistake

**What goes wrong:**
The launchpad app is configured to connect to the existing `field-guide-api`'s MongoDB pod (rather than deploying its own). The MONGO_URI in the launchpad's Helm Secret references the MongoDB service as `field-guide-api-mongodb:27017` — correct for the service name in the `default` namespace. But if the developer uses the launchpad chart's own MongoDB hostname helper (`launchpad-mongodb`), the DNS lookup fails with `No route to host`. Alternatively, if both charts deploy their own separate MongoDB instances, the `launchpad`'s MongoDB has `mongodb.enabled: true` and the developer forgets to set `mongoDbName: launchpad`, writing to the fieldguide database instead.

**Why it happens:**
Cross-chart service references are not validated by `helm lint` or `helm upgrade`. The error only appears at runtime as a MongoDB connection failure in the pod logs.

**How to avoid:**
Decision first, then implementation: Choose ONE MongoDB instance for v1.1 (the shared field-guide-api MongoDB, or a new launchpad-owned one). Document the decision in `CONTEXT.md`. If sharing: disable MongoDB in the launchpad chart (`mongodb.enabled: false`) and supply `externalMongoUri` via `--set` pointing to `field-guide-api-mongodb:27017` — the v1.0 chart already has this `externalMongoUri` seam in `values.yaml`. If separate: set `mongoDbName: launchpad` and verify with `kubectl exec <launchpad-pod> -- env | grep MONGO` that the correct database name is injected.

**Warning signs:**
- `kubectl logs <launchpad-pod>` shows `No servers found yet, connection refused` on startup
- `mongosh` inside the MongoDB pod shows the `launchpad` database is missing while the app claims to be writing events
- `helm lint charts/launchpad` passes but `make smoke-launchpad` times out

**Phase to address:** Phase: Launchpad Helm chart and MongoDB wiring

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Calling `load_incluster_config()` at module level | One-line K8s setup | Test suite crashes outside cluster; forces mock complexity | Never — always lazy-init inside a function |
| `hx-trigger="every 2s"` on status cards | Snappier feeling UI | Worker starvation with >1 browser tab; masks K8s timeout problems | Never below 10s on routes doing real I/O |
| Reusing `IMAGE`, `RELEASE`, `CHART` Makefile variables for both apps | Minimal Makefile changes | Deploying one app silently skips the other; smoke test targets wrong service | Never — namespace variables from the start |
| Unindexed `platform_events` collection without `.limit()` | Fast to write | Full collection scan; demo slows after 1 hour of use | Never — add TTL index and `.limit()` before first insert |
| Dashboard `/health` calling field-guide-api's `/health` | Looks like a real health check | readinessProbe cascade; dashboard goes NotReady when field-guide-api restarts | Never — liveness/readiness must be scoped to the pod's own dependencies |
| Copying `mongoDbName: fieldguide` into the launchpad chart unchanged | Faster scaffolding | Silent data collision between two apps in shared MongoDB | Never — set `mongoDbName: launchpad` from the start |
| Vendoring `htmx.min.js` without pinning the version in a comment | Simpler static folder | Next developer doesn't know which version is vendored; 1.x vs 2.x has breaking API changes | Acceptable if the version is documented in a comment at the top of the file |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| kubernetes Python client | No `_request_timeout` on API calls | Always pass `_request_timeout=5` to every client method call |
| kubernetes Python client | `load_incluster_config()` at import time | Lazy-init inside `get_k8s_client()` factory; catch `ConfigException` and return disabled mode |
| htmx polling → Flask route | Polling an endpoint that does synchronous K8s/MongoDB I/O | Keep the polled endpoint under 3s; cache K8s results for the poll interval |
| launchpad → field-guide-api MongoDB | Using wrong service hostname (launchpad chart's own helper instead of cross-chart name) | Hard-code the shared MongoDB service name as `field-guide-api-mongodb` in launchpad's `externalMongoUri` value |
| Jinja2 + htmx | Returning full HTML from a fragment-only route | Check `request.headers.get("HX-Request")` and return appropriate template type |
| ServiceAccount RBAC | Using ClusterRole instead of namespace-scoped Role | Create a `Role` in the `default` namespace with only `get/list` on `pods` and `services` — no ClusterRole needed for kind local dev |
| mongomock in tests | Assuming mongomock enforces TTL and capped collection limits | Write separate integration tests against real mongo:7 for storage-behavior tests |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Unbounded `platform_events` query | `/api/events` takes 1–2s to load after 1 day of use | TTL index + always `.limit(100).sort("created_at", -1)` | ~10k documents (minutes on a demo) |
| htmx poll interval below 10s on I/O-bound route | Browser spinner; gunicorn timeouts; worker CRITICAL messages | Minimum 10s poll + visibility check + in-process cache | First time a second browser tab is opened |
| K8s client without timeout on `/api/status` | Dashboard hangs when cluster paused; readinessProbe failures | `_request_timeout=5` on all calls; module-level result cache with 10s TTL | First laptop sleep/wake cycle during a demo |
| Flask `render_template` with large context objects | HTML generation slow for events feed | Paginate: never pass >100 events to a template; use `.limit()` in the query | ~500 events in the template context |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| ClusterRole instead of namespace-scoped Role for launchpad ServiceAccount | If launchpad pod is compromised, attacker gets read access to all namespaces, all clusters | Use `Role` (namespace-scoped), not `ClusterRole`; bind only to `default` namespace |
| ServiceAccount token auto-mounted on field-guide-api pod | Field-guide-api doesn't need K8s API access; token is an unnecessary attack surface | Set `automountServiceAccountToken: false` in the field-guide-api Helm chart Deployment spec |
| Committing `apps/launchpad/.env` with MongoDB URI before `.gitignore` covers new app dir | Credentials in git history | Verify `.gitignore` covers `apps/launchpad/.env` before first commit in that directory |
| Kubernetes RBAC verbs `*` on pods | Any pod operation (delete, exec) possible from inside launchpad pod | Restrict to `verbs: ["get", "list", "watch"]` only — no `create`, `delete`, `exec` |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| htmx status card shows spinner during every 5s poll | Dashboard flickers every 5 seconds; feels broken | Use `hx-indicator` on a small spinner icon, not the entire card; swap only the inner data, not the card shell |
| Degraded K8s status shown as a red error state | Reviewer thinks the platform is broken when the cluster is just local | Use a "degraded" yellow state with message "K8s API unavailable — running outside cluster" for graceful fallback |
| Events feed shows raw timestamps (UTC epoch) | Hard to read during a demo | Format as relative time ("2 minutes ago") in Jinja2 using a custom filter |
| Service registration form accepts empty names | Invalid data in MongoDB; confusing list state | Client-side required attribute + server-side validation before insert |

---

## "Looks Done But Isn't" Checklist

- [ ] **K8s client graceful degradation:** `make test` passes with zero kubernetes calls; `KUBERNETES_SERVICE_HOST` is unset and the dashboard still starts
- [ ] **MongoDB database isolation:** `kubectl exec <mongodb-pod> -- mongosh --eval "db.adminCommand({listDatabases:1})"` shows both `fieldguide` and `launchpad` as separate databases
- [ ] **htmx fragment safety:** Direct browser navigation to `/api/status` (no htmx context) returns a usable full page, not a bare div
- [ ] **Events TTL index:** `db.launchpad.platform_events.getIndexes()` shows a TTL index on `created_at`; queries always use `.limit()`
- [ ] **Port-forward isolation:** `make port-forward-launchpad` uses port 8081, not 8080; both port-forward targets can run simultaneously without conflict
- [ ] **Makefile target clarity:** `make build` alone fails with a helpful error or does not exist — must be `make build-fga` or `make build-launchpad`
- [ ] **RBAC scope:** `kubectl get role -n default` shows a namespace-scoped Role for launchpad; `kubectl get clusterrole | grep launchpad` returns nothing
- [ ] **Worker timeout resilience:** Kill the kind API server process (`docker pause kind-control-plane`) and confirm the dashboard responds with a degraded status within 6s, not a hung worker
- [ ] **Poll visibility:** Opening a second browser tab does not double the gunicorn request rate — verify with `kubectl logs -f <launchpad-pod>` while switching between two open tabs

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Makefile variable collision discovered mid-milestone | MEDIUM | Rename variables to namespaced form; update all targets; run `make up` end-to-end to verify |
| Selector label collision (wrong pods behind Service) | MEDIUM | `helm uninstall` both releases; fix `_helpers.tpl`; `helm install` in order; verify endpoints |
| K8s client hanging workers discovered in demo | LOW | Add `_request_timeout=5` to all client calls; restart pod; no data loss |
| `platform_events` collection unbounded (already has 100k docs) | MEDIUM | Create TTL index (`create_index` on existing collection is non-blocking on small datasets); add `.limit()` to all queries; consider a one-time cleanup script |
| MongoDB database collision (launchpad wrote to `fieldguide`) | HIGH | Drop contaminated collections in `fieldguide`; fix `mongoDbName` in chart values; redeploy; accept data loss (local kind only) |
| Fragment URL bookmarked without full-page fallback | LOW | Add `HX-Request` check to route; no data loss; retested in 10 minutes |
| `load_incluster_config()` at module level blocking tests | LOW | Move to lazy factory function; tests unblocked immediately |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Makefile variable collision | Phase: Monorepo scaffold — first task before any code | `make help` shows namespaced targets; `make deploy-fga` and `make deploy-launchpad` deploy distinct releases |
| Helm Service selector collision | Phase: Launchpad Helm chart scaffold | `kubectl get endpoints` shows correct pod IPs for each Service |
| K8s client blocking gunicorn worker | Phase: K8s API diagnostics | `_request_timeout=5` present on all client calls; confirmed via code review |
| `load_incluster_config` at import time | Phase: K8s API diagnostics — establish lazy-init factory first | `make test` passes without `KUBERNETES_SERVICE_HOST` set |
| Dashboard `/health` cascading failure | Phase: Launchpad app scaffold + `/health` endpoint | `/health` only pings MongoDB; `/api/status` is separate and not probed |
| htmx polling + K8s I/O starvation | Phase: htmx UI and status polling | Poll interval ≥ 10s; visibility guard present; confirmed by log inspection |
| Unbounded events collection | Phase: Activity feed and MongoDB schema | TTL index confirmed in mongosh; `.limit()` in all queries; tests assert index existence |
| Shared MongoDB DB name collision | Phase: Launchpad app factory | `app.config["MONGO_DBNAME"]` logs `launchpad` not `fieldguide` on startup |
| htmx fragment vs full-page confusion | Phase: Jinja2 template structure | Direct browser navigation to fragment URLs returns full page |
| Port-forward collision | Phase: Makefile extension | Both port-forward targets run simultaneously on distinct ports |
| mongomock gap for TTL/capped | Phase: Activity feed test design | `conftest.py` documents limitation; index existence test added |
| Cross-chart MongoDB hostname wiring | Phase: Launchpad Helm chart and MongoDB wiring | `kubectl exec <launchpad-pod> -- env | grep MONGO` shows correct URI |

---

## Sources

- v1.0 Makefile (`E:/Genspark/k8s-launchpad/Makefile`) — existing variable/target names that would collide
- v1.0 `_helpers.tpl` (`charts/field-guide-api/templates/_helpers.tpl`) — selectorLabels pattern that must be replicated, not shared
- v1.0 `conftest.py` — mongomock monkeypatching pattern; basis for K8s client mock strategy
- v1.0 `health.py` — readiness probe design pattern: scope to own MongoDB, not downstream services
- v1.0 `app/__init__.py` — app factory pattern; kubernetes client must follow same lazy-init discipline
- [kubernetes-client/python: in_cluster_config.py example](https://github.com/kubernetes-client/python/blob/master/examples/in_cluster_config.py) — shows absence of fallback handling; ConfigException documented in issue #992
- [kubernetes-client/python: timeout-settings.md](https://github.com/kubernetes-client/python/blob/master/examples/watch/timeout-settings.md) — `_request_timeout` is the correct parameter; no default means infinite wait
- [htmx hx-trigger attribute docs](https://htmx.org/attributes/hx-trigger/) — `every` polling syntax; HTTP 286 stop-polling mechanism; no built-in visibility guard
- [htmx template fragments essay](https://htmx.org/essays/template-fragments/) — fragment vs full-page route design
- [htmx hx-boost fragment issue #497](https://github.com/bigskysoftware/htmx/discussions/2543) — browser restore of fragment URLs as broken page
- [MongoDB TTL Indexes official docs v7.0](https://www.mongodb.com/docs/v7.0/core/index-ttl/) — TTL index behavior, 60s background cleanup cadence
- [MongoDB Capped Collections](https://www.mongodb.com/docs/manual/core/capped-collections/) — mutual exclusivity with TTL indexes
- [API health checks for graceful vs cascading failure](https://klotzandrew.com/blog/api-health-checks-for-graceful-or-cascading-failure/) — cascading failure pattern documented
- [Kubernetes RBAC Good Practices](https://kubernetes.io/docs/concepts/security/rbac-good-practices/) — Role vs ClusterRole; automountServiceAccountToken
- [mongomock unit test pattern — flask-mongomock-example](https://github.com/alkc/flask-mongomock-example) — confirmed mongomock does not enforce TTL or capped constraints
- [gunicorn worker timeout issues](https://github.com/benoitc/gunicorn/issues/1655) — blocking IO (no client timeout) not detected by gunicorn until `--timeout` fires

---
*Pitfalls research for: Flask+htmx dashboard + K8s API diagnostics + shared MongoDB (k8s-launchpad v1.1 Product Dashboard)*
*Researched: 2026-07-08*
