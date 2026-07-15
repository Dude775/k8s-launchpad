# Pitfalls Research

**Domain:** Adding kube-prometheus-stack observability + a UI reskin to an existing additive-only, resource-constrained kind/Docker-Desktop local IDP (k8s-launchpad v2.0)
**Researched:** 2026-07-16
**Confidence:** MEDIUM-HIGH (critical items cross-verified against prometheus-community/helm-charts and prometheus-operator issue trackers plus official docs; some Windows/Docker-Desktop specifics are MEDIUM — verify live on the actual dev machine)

## Critical Pitfalls

### Pitfall 1: kube-prometheus-stack's default kubelet/etcd/scheduler/controller-manager scrape jobs are permanently "down" on kind

**What goes wrong:**
Out of the box, kube-prometheus-stack ships scrape jobs for `kube-etcd`, `kube-scheduler`, `kube-controller-manager`, and `kube-proxy` that assume a kubeadm cluster where these are static pods reachable over the node's real network interface with metrics bound to a non-loopback address. On kind (and Docker Desktop's Kubernetes), these control-plane components bind metrics to `127.0.0.1` inside the node container, so Prometheus's scrape targets page shows a permanent wall of red/down targets — noise that undermines a portfolio-quality "All Systems Online" demo.

**Why it happens:**
The chart's defaults target production kubeadm topology, not kind's containerized-node topology. This is a widely reported, structural mismatch, not a misconfiguration.

**How to avoid:**
Explicitly set in the observability values file: `kubeEtcd.enabled: false`, `kubeControllerManager.enabled: false`, `kubeScheduler.enabled: false`, `kubeProxy.enabled: false` (in addition to the already-planned `nodeExporter.enabled: false` and `alertmanager.enabled: false`). Keep `kubeApiServer` and `kubeStateMetrics` enabled — those work fine on kind. Document this trimming explicitly in `infra/observability/` values comments so a reviewer understands it's intentional, not broken monitoring.

**Warning signs:**
Prometheus `/targets` page shows jobs stuck in `down` state immediately after install with connection-refused errors to internal addresses like `10.96.x.x:https`.

**Phase to address:**
Observability stack install phase (the phase that writes `infra/observability/` values.yaml) — bake the disabled list in from the first `helm install`, not as a later fix.

---

### Pitfall 2: ServiceMonitor `release:` label mismatch — Prometheus discovers zero targets for field-guide-api/launchpad

**What goes wrong:**
By default, kube-prometheus-stack configures `serviceMonitorSelectorNilUsesHelmValues=true`, which makes the Prometheus Operator only pick up ServiceMonitors carrying the label `release: <helm-release-name>`. A ServiceMonitor created in `infra/observability/` scraping field-guide-api's or launchpad's `/metrics` without that exact label is silently ignored — no error, just zero entries in Service Discovery.

**Why it happens:**
The "release label" requirement is a chart/operator convention, not something obvious from the ServiceMonitor CRD spec itself. It is one of the most frequently filed issues against the chart.

**How to avoid:**
Either (a) add `release: <exact-helm-release-name>` to every ServiceMonitor's `metadata.labels`, pinning the release name as a Makefile variable to avoid drift, or (b) set `prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues: false` and `serviceMonitorSelector: {}` so Prometheus watches all ServiceMonitors cluster-wide regardless of label — simpler for a single-tenant local cluster and needs no coordination with existing charts (keeps the additive-only constraint cleaner). Also verify the ServiceMonitor's `spec.selector.matchLabels` matches the **Service** object's labels (not the Pod's) for field-guide-api/launchpad — a second, independent selector layer that's easy to get wrong.

**Warning signs:**
`kubectl get servicemonitors -A` shows the objects exist, but Prometheus UI → Status → Target discovery shows nothing for them; the Prometheus config reload logs show no error — this fails silently, not loudly.

**Phase to address:**
ServiceMonitor/scraping phase — verify with an actual query against `up{job="field-guide-api"}` returning `1` before moving to dashboards.

---

### Pitfall 3: Grafana sidecar never picks up dashboard ConfigMaps

**What goes wrong:**
Dashboards-as-code via sidecar ConfigMaps requires the ConfigMap to (a) live in a namespace the sidecar is watching, (b) carry the label the chart's sidecar is configured to watch for (default `grafana_dashboard: "1"`), and (c) be present before or shortly after Grafana's own dashboard-provider init — the sidecar (`kiwigrid/k8s-sidecar`) has a known race where Grafana's dashboard provider initializes before the sidecar finishes writing the file, so a fresh install can show "no dashboards" until a pod restart.

**Why it happens:**
The sidecar polls/watches the API server independently of Grafana's own startup; there's no built-in readiness gate between them.

**How to avoid:**
Set `grafana.sidecar.dashboards.enabled: true`, `grafana.sidecar.dashboards.label: grafana_dashboard`, and `grafana.sidecar.dashboards.searchNamespace: ALL` (or the specific observability namespace — do not leave the default, which only searches Grafana's own namespace). Label every dashboard ConfigMap with `grafana_dashboard: "1"`. If dashboards don't appear after `helm install`, don't chase it as a config bug — do one `kubectl rollout restart deployment/<release>-grafana` and re-check; this is a known cold-start race on first install only.

**Warning signs:**
`kubectl logs <grafana-pod> -c grafana-sc-dashboard` shows the ConfigMap being written to `/tmp/dashboards/`, but Grafana's dashboard list UI is empty.

**Phase to address:**
Grafana dashboards-as-code phase — smoke-test by asserting dashboard UIDs exist via Grafana's HTTP API (`/api/search?query=`) after `make observability-up`, not just eyeballing the UI once.

---

### Pitfall 4: PromQL `rate()`/`increase()` windows shorter than the scrape interval return no data (blank dashboards)

**What goes wrong:**
Uptime/error-rate/latency panels built with something like `rate(flask_http_request_duration_seconds_count[1m])` return empty results if the effective scrape interval is 30-60s — a likely choice on a resource-trimmed local Prometheus to reduce CPU/etcd write pressure. `rate()` needs at least two samples inside its window; best practice is a window at least 4x the scrape interval.

**Why it happens:**
Dashboards are frequently copy-pasted from public examples assuming a 15s scrape interval; the actual scrape interval configured to reduce local resource pressure is often longer, silently breaking every rate-based panel.

**How to avoid:**
Pick one deliberate scrape interval for the observability stack, document it (e.g. 30s), and size every `rate()`/`increase()` window to at least 4x it (2m for a 30s interval). In Grafana panels, prefer the `$__rate_interval` template variable over hardcoded windows — but only after confirming the Prometheus datasource's configured scrape interval in Grafana matches the actual value (a second, independent place this can silently drift, since Grafana's own datasource setting defaults to 15s regardless of the real cluster interval).

**Warning signs:**
Panels render axes/legends but no lines; querying the raw counter in Explore shows increasing values, but the `rate()`-wrapped version returns "No data."

**Phase to address:**
Grafana dashboards-as-code phase — write the scrape interval as a single source-of-truth value (Helm value + Grafana datasource config), verified with one canary panel before building all three (uptime/latency/error-rate) dashboards.

---

### Pitfall 5: prometheus-flask-exporter default metric names don't match "generic" dashboard examples

**What goes wrong:**
`prometheus-flask-exporter` (already vendored per STACK.md) exposes metrics under its own naming convention — by default `flask_http_request_duration_seconds` (histogram) and a request-count metric, with `method`, `status`, and `path`/`endpoint` labels — not the generic `http_requests_total`/`http_request_duration_seconds` names used in most public Grafana dashboard examples and blog posts. Copy-pasting a public dashboard JSON produces panels that silently show no data because the metric name simply doesn't exist in this Prometheus.

**Why it happens:**
Every Flask/instrumentation library picks its own metric prefix; there's no cross-ecosystem standard name.

**How to avoid:**
Before writing any dashboard JSON, run `curl localhost:<port>/metrics` against a live field-guide-api/launchpad pod (or via port-forward) and copy the actual metric and label names present. Build the three dashboards (uptime/latency/error-rate) against these verified names, not a template found online.

**Warning signs:**
Grafana panel query inspector shows the query executed but with zero series returned; Prometheus's own metric browser/autocomplete in Explore doesn't suggest the metric name typed in the panel.

**Phase to address:**
Grafana dashboards-as-code phase — first task should be "dump real /metrics output from both apps," used as the reference for every subsequent PromQL query.

---

### Pitfall 6: Flask querying the in-cluster Prometheus HTTP API blocks the request-handling worker and breaks the hermetic test suite

**What goes wrong:**
Native metric cards in launchpad calling Prometheus's HTTP API (`/api/v1/query`) synchronously, without a short explicit timeout, can hang a gunicorn worker if Prometheus is unreachable/slow — with "1 worker per pod" (per STACK.md), one stuck worker means the entire dashboard becomes unresponsive, not just the metrics card. Separately, if the new code path makes a real HTTP call unconditionally, the existing hermetic 128-test suite (no kubeconfig, no cluster, established in v1.1) will either hang trying to connect or start failing outright the moment tests run with no observability stack up — a direct regression of the "additive only, v1.1 tests unchanged" hard constraint if this pattern leaks into shared code paths.

**Why it happens:**
The existing lazy-init pattern (`(None, None)` disabled signal for the K8s client, established before any route existed) was designed specifically to keep the app/tests loadable with no cluster — but a new Prometheus HTTP client is a new external dependency that must independently repeat that same discipline; it's easy to bolt on a plain `requests.get(...)` call without timeout/mocking and not notice until the test suite or a real "Prometheus down" scenario breaks in production.

**How to avoid:**
1. Mirror the existing K8s-client pattern: lazy client construction, a clear "disabled"/`None` sentinel when the observability stack isn't reachable, feeding the planned "NO SIGNAL" dimmed-panel UI state.
2. Always pass an explicit short timeout (e.g. `timeout=2`) to every Prometheus HTTP call — never rely on library/socket defaults.
3. In tests, mock/monkeypatch the Prometheus client the same way `k8s` is monkeypatched in `conftest.py` — assert the code never performs a real network call during `pytest`.
4. Treat "Prometheus unreachable" as a normal, tested degraded state (like the existing outside-cluster/403/unreachable K8s branches), not an exception path that surfaces a 500.

**Warning signs:**
`make test` starts taking noticeably longer or intermittently hangs; the dashboard page becomes slow/unresponsive specifically when the observability stack is down or not yet installed; new tests make assertions against real HTTP responses instead of mocked fixtures.

**Phase to address:**
Native metric cards / graceful degradation phase — the lazy-client + timeout + mock pattern should be the first thing written, before any actual query logic, exactly mirroring how the K8s client discipline was sequenced in v1.1.

---

### Pitfall 7: kube-prometheus-stack resource footprint exceeds Docker Desktop's WSL2/kind capacity, causing Pending/Evicted pods alongside the two existing app stacks

**What goes wrong:**
Even "trimmed" (operator + Prometheus + Grafana + kube-state-metrics, no Alertmanager/node-exporter), kube-prometheus-stack's default resource requests can push a Docker Desktop VM already running field-guide-api + its mongo + launchpad + its mongo past its allocated memory/CPU, especially if Docker Desktop wasn't explicitly given extra RAM beyond older/lower defaults. Symptoms are pods stuck `Pending` (insufficient CPU/memory) or nodes reporting memory pressure and evicting pods intermittently — worse than a hard failure because it looks flaky rather than structurally under-resourced.

**Why it happens:**
kube-prometheus-stack's chart defaults are sized for real clusters, not a single-node kind container sharing a laptop's RAM with two other app stacks; disabling Alertmanager/node-exporter cuts pod count but doesn't automatically right-size the remaining components' `resources.requests/limits`.

**How to avoid:**
Explicitly override `resources.requests`/`resources.limits` for `prometheus`, `grafana`, `kube-state-metrics`, and the operator itself in the observability values file to conservative local-dev sizes, well below the chart defaults. Document the minimum required Docker Desktop memory allocation (verify empirically on the actual dev machine and record the number, e.g. in `docs/known-limitations.md`) rather than assuming the existing setup has enough headroom.

**Warning signs:**
`kubectl get pods -n <observability-namespace>` shows `Pending` with `kubectl describe` reporting `Insufficient cpu`/`Insufficient memory`; existing field-guide-api or launchpad pods start getting evicted or OOMKilled after the observability stack goes up, even though their own charts didn't change — the smoking gun for a shared-node resource-exhaustion regression against the additive-only constraint.

**Phase to address:**
Observability stack install phase — resource-size the values file before wiring any ServiceMonitors, and re-run `make smoke` / `smoke-launchpad` immediately after `observability-up` to catch node-level resource regressions early, per-phase, not at final milestone audit.

---

### Pitfall 8: kube-prometheus-stack CRDs installed via `helm install` are never upgraded by `helm upgrade`, and can hit the 262144-byte annotation limit

**What goes wrong:**
Helm's documented behavior is that CRDs placed in a chart's `crds/` directory are installed once and are never updated or deleted by subsequent `helm upgrade`/`helm uninstall` — so re-running `make observability-up` after bumping the chart version, or an `observability-down` that doesn't explicitly clean CRDs, leaves stale CRD schemas around that can silently break new ServiceMonitor/PodMonitor fields, or produce `no matches for kind "ServiceMonitor"` errors on a fresh cluster if CRDs and the operator race during a single combined install. Separately, the Prometheus Operator's CRDs (particularly the `Prometheus` CRD) are large enough that plain `kubectl apply` (client-side apply) can hit Kubernetes's hard 262144-byte annotation limit on `last-applied-configuration`, causing an upgrade to fail outright.

**Why it happens:**
This is documented, intentional Helm behavior (to avoid Helm accidentally deleting user data tied to CRDs) that surprises almost everyone the first time; the annotation-size issue is a hard Kubernetes API limit that the chart's CRDs are large enough to bump into on any repeated apply-based upgrade path.

**How to avoid:**
Treat `infra/observability/` CRD lifecycle explicitly: on `observability-down`, decide deliberately whether to delete CRDs (full teardown, safe for a disposable local kind cluster) or leave them (faster subsequent `up`); document the choice, don't leave it implicit. If any Makefile target ever needs to directly `kubectl apply` a CRD (rather than relying purely on `helm install`'s automatic CRD install-once behavior), use `kubectl apply --server-side` to sidestep the annotation-size limit.

**Warning signs:**
`kubectl get crd | grep monitoring.coreos.com` shows CRDs from a previous, older chart version after upgrading the chart; `helm upgrade` reports success but new CRD fields used in values.yaml have no effect; any direct `kubectl apply -f` against a Prometheus Operator CRD manifest fails with `metadata.annotations: Too long`.

**Phase to address:**
Observability stack install phase — decide and document the CRD teardown policy in the same PR that adds `observability-down`, not discovered later during milestone testing.

---

### Pitfall 9: Pico dark reskin silently breaks the existing v1.1 forms (service catalog register/deregister, CSRF forms)

**What goes wrong:**
Pico CSS variables must be overridden per-theme-selector (`[data-theme="dark"]` and `:root:not([data-theme="dark"])`/`@media (prefers-color-scheme: dark)`), and Pico deliberately leaves many elements without explicit background/color so they inherit from parent context. A `mission-control.css` layer added on top, if it sets colors/background at too broad a selector (e.g. `body`, `input`, `.card`) without matching Pico's own cascade/specificity, can make existing v1.1 forms (onboarding/register, deregister confirmation, CSRF-protected inputs) render with invisible text (dark-on-dark) or unreadable focus/error states — a regression the v1.1 smoke/E2E flows won't catch because they check HTTP status codes and DOM presence, not visual contrast.

**Why it happens:**
Pico's dark-mode variables and cascade behavior are non-obvious, and a "just add a CSS file" reskin approach doesn't automatically account for every existing page/component that was built and screenshot-verified under the light Pico theme in v1.1.

**How to avoid:**
Use Pico's official CSS-variable override pattern (`--pico-*` variables, not raw color properties) scoped to `[data-theme="dark"]`. After the reskin, manually re-walk every existing v1.1 page (dashboard, service catalog register/view/deregister, diagnostics, activity feed) in a browser — not just automated tests — checking text contrast and focus states, since this is exactly the kind of regression automated smoke tests structurally cannot detect. Reuse the same five-screenshot verification discipline from v1.1's README requirement, but for the dark skin.

**Warning signs:**
Existing forms visually "disappear" (dark text on dark background) even though `curl`/pytest-based tests still pass; error/validation message color no longer has sufficient contrast against the new dark background.

**Phase to address:**
Mission Control UI reskin phase — explicitly include a manual visual pass over every pre-existing v1.1 page as an exit criterion, not just the new Mission Control pages.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|-----------------|------------------|
| `helm install --set` chains of dozens of inline flags in the Makefile for kube-prometheus-stack trimming | Fast to write, no new file | Unreadable, fragile, hard to diff in code review, easy to typo a flag silently | Never for this project — use a checked-in `infra/observability/values.yaml`, matching the existing per-chart `values.yaml` convention |
| Skipping CRD teardown policy on `observability-down` ("just leave them, it's local") | Faster iteration during dev | Stale CRDs cause confusing "field has no effect" bugs on chart version bumps | Acceptable only if explicitly documented as a known limitation, same as v1.1's accepted-risk pattern in `docs/known-limitations.md` |
| Committing default Grafana `admin/admin` (or similarly weak) credentials in the observability values file | No secret-management plumbing needed | Same accepted-risk category as v1.1's committed local-dev Mongo password — fine for local kind, but must be documented, never assumed "obviously fine" | Acceptable only for local kind, explicitly logged in `docs/known-limitations.md` exactly like the existing MongoDB URI precedent |
| Hardcoding a 15s scrape interval assumption in dashboard PromQL without checking the actual configured interval | Dashboards "look done" quickly | Silent blank panels the moment scrape interval is tuned for resource savings | Never — always derive rate windows from the actual configured interval |
| Building native metric cards with a blocking `requests.get()` and no timeout "just to get it working" | Fastest path to a working demo | One slow/unreachable Prometheus call can hang a single-worker gunicorn pod, taking down the whole dashboard | Never — timeout + mock-in-tests must be there from the first commit, per the existing lazy-client precedent |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|-----------------|-------------------|
| Prometheus Operator ServiceMonitor selector | Assuming a ServiceMonitor is auto-discovered just by existing in the cluster | Match both the `release:` label convention (or disable `serviceMonitorSelectorNilUsesHelmValues`) AND ensure `spec.selector.matchLabels` matches the target Service's labels |
| Grafana sidecar dashboard provisioning | Assuming ConfigMaps are picked up instantly and namespace-agnostically by default | Set `sidecar.dashboards.searchNamespace` explicitly; expect a possible one-time restart on fresh install due to the known init race |
| kube-state-metrics + kube-prometheus-stack on kind | Leaving default `kubeEtcd`/`kubeScheduler`/`kubeControllerManager`/`kubeProxy` scrape jobs enabled | Disable all four explicitly alongside the already-planned Alertmanager/node-exporter disabling |
| Flask → in-cluster Prometheus HTTP API | Synchronous call with no timeout, no mock seam | Lazy client + explicit short timeout + "NO SIGNAL" degraded state, mirroring the existing K8s client pattern |
| Helm CRD lifecycle across `install`/`upgrade`/`uninstall` | Assuming `helm upgrade` also upgrades CRDs | CRDs are install-once by Helm design; decide and document an explicit teardown/upgrade policy |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|-----------------|
| Default (unsized) Prometheus/Grafana/kube-state-metrics resource requests on a shared kind node | Pods `Pending`/evicted, other app pods start getting OOMKilled | Explicitly right-size `resources.requests/limits` for all four remaining components in the trimmed stack | The moment the observability stack is installed alongside both existing app+mongo pairs on default Docker Desktop memory allocation |
| Short PromQL rate windows vs. actual scrape interval | Blank/"No data" panels despite metrics existing | Size rate windows to ≥4x scrape interval; keep Grafana datasource scrape-interval setting in sync with the real value | As soon as the scrape interval is tuned above 15s for resource savings |
| Unbounded/leftover port-forward processes from previous dev sessions | New `make port-forward-grafana`/`observability-up` runs fail with "address already in use" on 3000/9090/8080/8081 | Makefile target should kill any prior port-forward on the target port before starting a new one (mirroring whatever pattern the existing `port-forward` target for field-guide-api/launchpad already uses) | Any time a prior session wasn't cleanly torn down — common on Windows where Ctrl+C in Git Bash doesn't always kill background `kubectl port-forward` children |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Committing a real/production-looking Grafana admin password instead of an obviously-local-dev placeholder | Looks like a leaked credential to anyone scanning the repo, even though it's local-only | Follow the exact precedent already set for MongoDB in v1.1: an obviously-fake local value, documented as an accepted risk in `docs/known-limitations.md` |
| Exposing Prometheus/Grafana via a NodePort or LoadBalancer "for convenience" instead of port-forward | Unnecessarily widens local attack surface on a Windows host with other things listening on the network | Keep observability access to `kubectl port-forward` (via the planned `port-forward-grafana` target) — consistent with how field-guide-api/launchpad are already accessed |
| Prometheus HTTP API called from launchpad without validating/sanitizing any user-influenced query fragments (e.g. a future feature letting a user pick a service name to build a query) | PromQL injection into label matchers | Keep all v2.0 queries as fixed, code-defined PromQL strings with parameterized label values (never string-concatenate user input directly into a PromQL query) |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Native metric cards show a raw error/traceback when Prometheus isn't installed yet | Looks broken, undermines "portfolio quality" first impression | Dimmed "NO SIGNAL" panel state, exactly as already planned — make sure it's the first thing built, not a fallback bolted on after the happy path |
| Grafana deep links ("Open in Grafana") pointing to a URL that requires port-forward the reviewer hasn't set up | Dead link on first click, confusing | Document in the README that Grafana access requires `make port-forward-grafana` first; keep the deep link's port consistent with the Makefile target's convention |
| Dark reskin applied inconsistently — new Mission Control pages look polished, existing v1.1 pages (register/catalog/diagnostics) look untouched/mismatched | Jarring, unfinished-looking product for a portfolio piece | Explicitly re-skin/verify every existing v1.1 page under the new dark theme as an exit criterion, not just new pages |

## "Looks Done But Isn't" Checklist

- [ ] **ServiceMonitors created:** Often missing the `release:` label match or a Service-label mismatch — verify with the Prometheus UI's Service Discovery/Targets page showing `up{job=...} == 1`, not just `kubectl get servicemonitor` succeeding.
- [ ] **Grafana dashboards provisioned:** Often show up in the ConfigMap/sidecar logs but not in the Grafana UI after a fresh install — verify via Grafana's own dashboard search API, and confirm at least one panel renders non-blank data (not just "the JSON imported").
- [ ] **"Trimmed" kube-prometheus-stack:** Often still leaves `kubeEtcd`/`kubeScheduler`/`kubeControllerManager`/`kubeProxy` scrape jobs enabled by default even after disabling Alertmanager/node-exporter — verify the Targets page has zero permanently-down jobs.
- [ ] **Native metric cards with graceful degradation:** Often only tested in the "everything up" happy path — verify the "NO SIGNAL" state actually renders (stop the observability stack and reload the dashboard) and that it doesn't hang the request.
- [ ] **`make seed-demo` idempotency:** Often only tested once from an empty database — verify running it twice in a row doesn't create duplicate catalog entries or duplicate activity-feed rows (check for a natural idempotency key or an existence check before each API call it drives).
- [ ] **Additive-only constraint:** Often "verified" by eyeballing that old files weren't touched — verify by literally re-running the full v1.1 smoke suite (`make smoke`, `smoke-launchpad`) after every v2.0 phase, not just at the final milestone audit.
- [ ] **Windows/Git Bash compatibility of new Makefile targets:** Often only tested by the person who wrote them in whatever shell they happen to be in — verify every new target (`observability-up`, `port-forward-grafana`, `seed-demo`, `up-mission-control`) explicitly in Git Bash on the actual Windows dev machine, watching for MSYS path-mangling on any argument that looks like an absolute path (e.g. `/api/v1/query`, label selectors starting with `/`).

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|-----------------|
| Stale/orphaned Prometheus Operator CRDs after a chart version bump | LOW (disposable local kind cluster) | `kind delete cluster` + recreate, or explicitly `kubectl delete crd -l app.kubernetes.io/part-of=kube-prometheus-stack` before reinstalling |
| ServiceMonitor silently not discovered | LOW | Fix label(s), `kubectl apply` again — Prometheus Operator reconciles on the next sync loop within seconds, no restart needed |
| Grafana dashboards not appearing after fresh install | LOW | One `kubectl rollout restart deployment/<release>-grafana`; if still missing, check sidecar container logs for the ConfigMap label mismatch |
| Node resource exhaustion causing existing app pods to be evicted | MEDIUM | `helm uninstall` the observability release, increase Docker Desktop memory allocation, re-apply trimmed `resources.requests/limits`, reinstall |
| Dark reskin breaks an existing v1.1 form's readability | MEDIUM | Isolate the offending Pico variable override, scope it more narrowly (component-level class instead of global selector), re-verify against all five original v1.1 screenshots |
| `make test` starts hanging due to an un-mocked live Prometheus HTTP call | LOW-MEDIUM | Add the missing `conftest.py` monkeypatch for the Prometheus client, add an explicit timeout to the underlying call as defense-in-depth |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Etcd/kubelet/scheduler/controller-manager scrape noise | Observability stack install phase | Prometheus Targets page shows zero permanently-down jobs after install |
| ServiceMonitor release-label / selector mismatch | ServiceMonitor/scraping phase | `up{job="field-guide-api"}` and `up{job="launchpad"}` both return `1` in Prometheus |
| Grafana sidecar dashboard discovery | Grafana dashboards-as-code phase | Grafana dashboard search API returns the provisioned dashboard UIDs post-install |
| PromQL rate() window vs scrape interval | Grafana dashboards-as-code phase | One canary rate-based panel renders non-blank data before building all three dashboards |
| prometheus-flask-exporter metric name mismatch | Grafana dashboards-as-code phase | PromQL queries built only from a real `/metrics` dump, not a public template |
| Flask→Prometheus blocking calls / hermetic test breakage | Native metric cards / graceful degradation phase | `make test` runtime unchanged and passes with zero live network calls; manual "stop observability, reload page" check doesn't hang |
| Resource exhaustion on shared kind node | Observability stack install phase | `make smoke` + `smoke-launchpad` pass immediately after `observability-up`, not just at milestone end |
| CRD install/upgrade/teardown ordering | Observability stack install phase | `observability-down` behavior (CRD kept vs. deleted) is documented and repeatable across two consecutive up/down cycles |
| Pico dark reskin breaking existing forms | Mission Control UI reskin phase | Manual visual re-walk of all pre-existing v1.1 pages under the new theme, screenshot-compared |
| Windows Git Bash / MSYS path mangling in new Makefile targets | Additive Makefile targets phase | Every new target explicitly exercised in Git Bash on the real Windows dev machine, not just WSL2 |
| `make seed-demo` non-idempotency | Demo seeding phase | Running `make seed-demo` twice produces no duplicate catalog/activity-feed entries |

## Sources

- [prometheus-community/helm-charts #2381 — ServiceMonitor wrong labels for kube-state-metrics](https://github.com/prometheus-community/helm-charts/issues/2381) — MEDIUM
- [prometheus-community/helm-charts #3131 — Grafana missing label release: prometheus](https://github.com/prometheus-community/helm-charts/issues/3131) — MEDIUM
- [prometheus-community/helm-charts #1513 — serviceMonitorSelector causes queries to fail](https://github.com/prometheus-community/helm-charts/issues/1513) — MEDIUM
- [Prometheus Operator troubleshooting docs](https://prometheus-operator.dev/docs/platform/troubleshooting/) — HIGH (official docs)
- [Grafana helm-charts #527 — sidecar init race with dashboard provider](https://github.com/grafana/helm-charts/issues/527) — MEDIUM
- [Fabian Lee — Prometheus: adding a Grafana dashboard via ConfigMap](https://fabianlee.org/2022/07/06/prometheus-adding-a-grafana-dashboard-using-a-configmap/) — MEDIUM
- [linkerd2 #7978 — charts not displaying data when duration < scrape interval](https://github.com/linkerd/linkerd2/issues/7978) — MEDIUM
- [Grafana Labs blog — $__rate_interval for Prometheus rate queries](https://grafana.com/blog/2020/09/28/new-in-grafana-7.2-__rate_interval-for-prometheus-rate-queries-that-just-work/) — HIGH (official)
- [prometheus/prometheus #3194 — rate()[1m] does not return data](https://github.com/prometheus/prometheus/issues/3194) — MEDIUM
- [kube-prometheus-stack CRD "no matches for kind" — helm-charts #1564, #2217, #2035](https://github.com/prometheus-community/helm-charts/issues/1564) — MEDIUM
- [helm/charts #9241 — CRD validation fails despite CRDs present](https://github.com/helm/charts/issues/9241) — MEDIUM
- [prometheus-community/helm-charts #1500 — CRD upgrade "Too long: must have at most 262144 bytes"](https://github.com/prometheus-community/helm-charts/issues/1500) — MEDIUM
- [Arthur Koziel — Fixing ArgoCD "Too long" CRD error (server-side apply)](https://www.arthurkoziel.com/fixing-argocd-crd-too-long-error/) — MEDIUM
- [prometheus-operator/kube-prometheus discussion #790 — node-exporter CrashLoopBackOff on Docker Desktop mount propagation](https://github.com/prometheus-operator/kube-prometheus/discussions/790) — MEDIUM (confirms why node-exporter is correctly disabled per project decision)
- [kind known issues docs](https://kind.sigs.k8s.io/docs/user/known-issues/) — HIGH (official)
- [benoitc/gunicorn #2020, #1801 — worker timeout on slow outbound HTTP calls](https://github.com/benoitc/gunicorn/issues/2020) — MEDIUM
- [Pico CSS official docs — CSS variables and color-scheme theming](https://picocss.com/docs/css-variables) — HIGH (official)
- [Pico CSS official docs — Color schemes](https://picocss.com/docs/color-schemes) — HIGH (official)
- [todzhang.com — Git Bash MSYS path-conversion pitfall for kubectl/minikube-style CLIs](https://www.todzhang.com/blogs/tech/en/minikube-windows-path-pitfall) — MEDIUM
- Project's own established precedents (lazy K8s client `(None, None)` pattern, hermetic 128-test suite, accepted-risk documentation convention) — HIGH (from `.planning/PROJECT.md`, first-party)

---
*Pitfalls research for: k8s-launchpad v2.0 Observability + Mission Control milestone*
*Researched: 2026-07-16*
