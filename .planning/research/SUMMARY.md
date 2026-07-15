# Project Research Summary

**Project:** k8s-launchpad — v2.0 "Observability + Mission Control"
**Domain:** Self-hosted Kubernetes observability (kube-prometheus-stack) + "mission control" status UI reskin, layered onto an existing additive-only, resource-constrained local kind IDP
**Researched:** 2026-07-16
**Confidence:** HIGH

## Executive Summary

k8s-launchpad v2.0 adds a trimmed `kube-prometheus-stack` (Prometheus Operator + Prometheus + Grafana + kube-state-metrics, with Alertmanager/node-exporter and the kubeadm-only control-plane scrape jobs disabled) into a new `infra/observability/` seam, wires it to the two existing apps' already-shipped `/metrics` endpoints via standalone `ServiceMonitor` manifests, provisions three Grafana dashboards as code (uptime, p95 latency, error rate) via labeled sidecar ConfigMaps, and surfaces the same three golden signals as native Prometheus-fed metric cards inside a reskinned dark "Mission Control" launchpad UI. This is the industry-standard way experts build exactly this: the Prometheus Operator's ServiceMonitor/CRD model is the de-facto scraping pattern, Google's four-golden-signals framework (here: uptime, latency, errors) is the accepted baseline for "credible observability," and dashboards-as-code via labeled ConfigMaps is the standard reproducible-provisioning idiom for this exact Helm chart family. All four research files agree the work factors cleanly into "stand up the trimmed stack -> wire scraping -> provision dashboards -> build native cards with graceful degradation -> reskin," and that this order de-risks the highest-uncertainty, most-external piece (a third-party Helm chart's footprint on a Docker-Desktop-backed kind node) before any application code is written against it.

The single biggest risk theme across all four files is **silent failure, not loud failure**: ServiceMonitor label mismatches, sidecar ConfigMap races, PromQL rate windows shorter than the scrape interval, and kubeadm-only scrape jobs stuck permanently "down" all produce dashboards/cards that *look* fine structurally (objects exist, HTTP 200s return) while showing zero or blank data — exactly the kind of regression the existing hermetic pytest suite and HTTP-status-only smoke tests cannot catch. The second major risk is resource exhaustion: even trimmed, kube-prometheus-stack is the heaviest thing this kind cluster has run (heavier than both Flask apps + two MongoDBs combined), so unsized `resources.requests/limits` risk evicting the *existing*, already-shipped app pods — a direct violation of the additive-only constraint even though no app chart code was touched. Mitigation for both is well-established in the research: pin explicit conservative resource limits from the first `helm install`, verify actual metric names/labels via a live `/metrics` dump before writing any PromQL, and re-run the existing `make smoke`/`smoke-launchpad` suite after every new phase (not just at milestone end) to catch shared-node regressions immediately. The third theme, specific to the UI half, is that a naive CSS-only dark reskin can silently break existing v1.1 forms' text/background contrast — a regression automated tests structurally cannot detect, requiring an explicit manual visual re-walk of every pre-existing page as an exit criterion.

The recommended approach is staged bottom-up: de-risk the trimmed Helm install and its resource footprint first (in isolation, verified via `kubectl`/Prometheus UI, no app code), then scraping (verified via the Targets page showing `up == 1`), then dashboards-as-code (verified via Grafana's own search API, not eyeballing), then the native metric-card client and route (built and unit-tested with mocked HTTP calls, mirroring the existing lazy K8s-client pattern, before any live cluster involvement), and only last the purely visual Mission Control reskin (safest to do last since it benefits from real data already flowing). Additive Makefile targets and `make seed-demo` bookend the work — the former codifying each stage into repeatable commands as soon as it's proven, the latter usable at any point after step 1 but most valuable staged near the end to populate the finished UI for demo screenshots.

## Key Findings

### Recommended Stack

The v1.0/v1.1 stack (Flask 3.1.3, Flask-PyMongo, PyMongo, gunicorn, prometheus-flask-exporter, kubernetes==33.1.0, Flask-WTF, htmx 2.0.10, Pico.css 2.1.1) carries over completely unchanged — v2.0 adds infrastructure and one new usage of an already-installed library, no new pip packages besides what's already pinned.

**Core additions:**
- `kube-prometheus-stack` Helm chart 87.16.1 (Grafana 12.7.2, kube-state-metrics 7.8.1 bundled) — the de-facto standard umbrella chart bundling Prometheus Operator + Prometheus + Grafana + CRDs in one install, actively maintained by prometheus-community
- ServiceMonitor/PodMonitor CRDs (bundled) — the exact integration point to scrape existing `/metrics` endpoints with zero app-code or chart changes
- `requests` (already pinned, no version change) — sufficient as the Prometheus HTTP API client for 3-4 fixed instant PromQL queries; `prometheus-api-client-python` deliberately rejected as unneeded weight (pandas/numpy for a use case that doesn't need it)
- Grafana sidecar (`k8s-sidecar`, bundled and pre-configured) — watches ConfigMaps labeled `grafana_dashboard: "1"` for git-versioned dashboards-as-code
- Mission Control dark CSS layer — pure `--pico-*` custom-property overrides under `[data-theme="dark"]`, loaded after `pico.min.css`; no build step, no new vendored dependency beyond one CSS file

**Explicitly disabled for resource budget:** Alertmanager (no consumer this milestone), node-exporter (known-flaky on Docker Desktop kind nodes), and — per PITFALLS.md, a critical addition STACK.md alone didn't flag — the kubeadm-only control-plane scrape jobs (`kubeEtcd`, `kubeControllerManager`, `kubeScheduler`, `kubeProxy`), which are permanently "down" on kind's containerized-node topology and must be disabled from the first install, not discovered later as noise.

### Expected Features

**Must have (table stakes):** per-service uptime % (rolling window), p95 request latency, error rate % per service — the three golden-signal metrics already named explicitly in the project's own scope; a consistent color-coded status legend reusing v1.1's existing operational/degraded/down vocabulary (not a second taxonomy); a "last updated" freshness indicator; a drill-down path from summary to detail; a hero "All Systems Online" banner; and graceful "no data yet" degradation rather than a crash or blank page when the observability stack isn't installed.

**Should have (differentiators):** native in-app metric cards (no iframe) with an explicit dimmed "NO SIGNAL" state; Grafana dashboards-as-code via sidecar ConfigMaps (git-versioned, reproducible on a fresh cluster, not click-built); "Open in Grafana" deep links bridging native cards to full time-series panels; the deliberate dark "control room" visual theme; idempotent `make seed-demo` so first load is never an empty dashboard; and extending the existing self-diagnostics philosophy to check whether Prometheus is actually scraping both targets.

**Defer (v2.x+):** Loki/log aggregation (already deferred to v2.1 in PROJECT.md), traffic/RPS as a fourth native card, an observability self-diagnostic row, Alertmanager/paging, SLO burn-rate panels, long-term retention (Thanos/Mimir), and node-exporter host metrics. All of these are explicitly named anti-features or v2.x-deferred items whose cost/complexity is disproportionate to this milestone's 2-service demo scope.

### Architecture Approach

The system splits cleanly into two halves connected only by label-selector matching and outbound HTTP: an *existing, completely untouched* app layer (field-guide-api + launchpad, each already exposing `/metrics`) and a *new* `infra/observability/` namespace running the trimmed Helm release, standalone `ServiceMonitor` manifests (never inside the app charts), and dashboard ConfigMaps. Launchpad gains one new bare module (`app/prometheus.py`, mirroring the existing lazy `app/k8s.py`/`app/status.py` pattern — bounded timeout, narrow exception catch, `None` sentinel on failure) plus a new partial route/blueprint reusing the existing hypermedia-fragment convention (`partials.py` + htmx polling), and a third CSS cascade layer (`mission-control.css`) loaded after `pico.min.css`/`style.css`.

**Major components:**
1. **kube-prometheus-stack (trimmed)** — Prometheus Operator, Prometheus CR, Grafana, kube-state-metrics in the `observability` namespace; owns the ServiceMonitor/PodMonitor CRDs
2. **Standalone ServiceMonitors** (`infra/observability/`) — target the *existing* Services by their already-present `app.kubernetes.io/name` labels; zero chart edits required
3. **Grafana dashboard ConfigMaps** (`infra/observability/dashboards/`, one JSON per ConfigMap, labeled `grafana_dashboard: "1"`) — git-versioned dashboards-as-code, re-created on every fresh cluster
4. **`app/prometheus.py` + new partial route** — thin, never-raising PromQL HTTP-API client feeding metric-card fragments and "Open in Grafana" deep links, following the codebase's established graceful-degradation discipline exactly
5. **`mission-control.css`** — pure visual reskin layer, safest and lowest-risk to build last

The suggested build order (from ARCHITECTURE.md, corroborated by PITFALLS.md's phase mapping) is: (1) trimmed stack install + resource sizing, (2) ServiceMonitors verified via the Targets page, (3) dashboard ConfigMaps verified via Grafana's search API, (4) additive Makefile targets codifying 1-3, (5) `app/prometheus.py` built and unit-tested with mocked HTTP (no live cluster needed), (6) metric-card partial + NO-SIGNAL branch, (7) `mission-control.css` + hero/card markup, (8) `make seed-demo`, (9) `up-mission-control`/`smoke-mission-control` umbrella targets.

### Critical Pitfalls

1. **kubeadm-only control-plane scrape jobs are permanently "down" on kind** — disable `kubeEtcd`/`kubeControllerManager`/`kubeScheduler`/`kubeProxy` explicitly from the first install alongside Alertmanager/node-exporter, or the Targets page shows a wall of red that undermines the "All Systems Online" demo.
2. **ServiceMonitor `release:` label mismatch causes silent zero-target discovery** — either label every ServiceMonitor with the exact Helm release name, or (recommended for this single-tenant local cluster) set `serviceMonitorSelectorNilUsesHelmValues: false` to discover cluster-wide; verify with `up{job=...}` returning 1, not just `kubectl get servicemonitor` succeeding.
3. **Grafana sidecar cold-start race + multi-dashboard ConfigMap merge bug** — one dashboard JSON per ConfigMap (never bundled), and expect a possible one-time `kubectl rollout restart` on fresh install before dashboards appear; verify via Grafana's search API, not eyeballing the UI once.
4. **PromQL `rate()`/`increase()` windows shorter than the actual scrape interval return blank panels** — size every window to >=4x the configured scrape interval, and keep Grafana's datasource scrape-interval setting in sync with the real value (a second, independently-drifting place this breaks).
5. **Flask->Prometheus synchronous calls without a timeout can hang the single gunicorn worker and break the hermetic test suite** — mirror the existing lazy K8s-client discipline exactly: explicit short timeout, `None` sentinel on any failure, and monkeypatch the client in `conftest.py` so `pytest` never performs a real network call.
6. **Resource exhaustion on the shared kind node** — even trimmed, kube-prometheus-stack is the heaviest thing this cluster has run; unsized resource requests can evict the *already-shipped* app pods, a shared-node regression against the additive-only constraint that must be caught by re-running `make smoke`/`smoke-launchpad` immediately after `observability-up`, not at final milestone audit.

## Implications for Roadmap

Based on combined research, the suggested phase structure follows the dependency-aware build order from ARCHITECTURE.md, which PITFALLS.md's phase-mapping table independently corroborates pitfall-by-pitfall.

### Phase 1: Observability Stack Install
**Rationale:** Highest-uncertainty, most-external piece (a third-party Helm chart's resource footprint and kind-specific quirks) — de-risk in isolation before any app code depends on it.
**Delivers:** Trimmed `kube-prometheus-stack` running in its own `observability` namespace, with Alertmanager, node-exporter, and the four kubeadm-only control-plane scrape jobs explicitly disabled; conservative `resources.requests/limits` set on every remaining component; `observability-up`/`observability-down` scripts.
**Addresses:** The foundational P1 feature "trimmed kube-prometheus-stack install."
**Avoids:** Pitfall 1 (kubeadm scrape noise), Pitfall 7 (resource exhaustion), Pitfall 8 (CRD lifecycle policy — decide and document CRD teardown behavior here, not discovered later).

### Phase 2: ServiceMonitor Scraping
**Rationale:** Cheapest possible validation that existing Service labels are sufficient scrape selectors — must be proven before writing a single line of dashboard/query code against it.
**Delivers:** Standalone `ServiceMonitor` manifests for field-guide-api and launchpad in `infra/observability/`, verified via the Prometheus Targets page showing `up{job=...} == 1` for both.
**Addresses:** The scraping prerequisite underlying every P1 dashboard/card feature.
**Avoids:** Pitfall 2 (release-label / selector mismatch — silent zero-target discovery).

### Phase 3: Grafana Dashboards-as-Code
**Rationale:** Confirms the sidecar-discovery wiring independently of anything in launchpad, and requires real metric names dumped from a live `/metrics` endpoint before any PromQL is written.
**Delivers:** Three dashboard ConfigMaps (uptime %, p95 latency, error rate), one JSON per ConfigMap, verified via Grafana's own dashboard-search API.
**Addresses:** The P1 "three Grafana dashboards-as-code" feature and the differentiator "dashboards-as-code via sidecar ConfigMaps."
**Avoids:** Pitfall 3 (sidecar cold-start race, multi-dashboard merge bug), Pitfall 4 (rate-window sizing), Pitfall 5 (metric-name mismatch vs. public templates).

### Phase 4: Additive Makefile Targets (Observability)
**Rationale:** Codify Phases 1-3 into repeatable, reviewable commands now, before building on top of them — matches the project's existing compositional Makefile convention (`up-all` composing `up` + build/load/deploy).
**Delivers:** `observability-up`, `observability-down`, `port-forward-grafana` targets, each explicitly exercised in Git Bash on the real Windows dev machine.
**Uses:** Existing Makefile POSIX/MSYS-safe patterns already established in the codebase.
**Avoids:** The Windows/Git Bash MSYS path-mangling pitfall flagged for every new target.

### Phase 5: Native Metric-Card Client + Graceful Degradation
**Rationale:** Hermetically buildable and unit-testable with mocked `requests.get` calls — no live cluster required — so it should be built and tested before any UI work, exactly mirroring how the K8s client discipline was sequenced in v1.1.
**Delivers:** `app/prometheus.py` (lazy, never-raising, 2s-timeout client) + `PROMETHEUS_BASE_URL`/`GRAFANA_BASE_URL` config additions (additive keys only, same precedent as v1.1's `eventsTtlSeconds` addition) + new metric-cards partial route with a tested "NO SIGNAL" branch.
**Implements:** ARCHITECTURE.md's Pattern 2 (graceful-degradation outbound query) as the third instance of the codebase's established resiliency discipline.
**Avoids:** Pitfall 6 (blocking calls hanging the single gunicorn worker / breaking the hermetic test suite).

### Phase 6: Mission Control UI Reskin
**Rationale:** Purely visual, lowest-risk, most-iterative — deliberately last since it benefits from real data already flowing from Phases 1-5, and any visual regression is easiest to catch once the underlying plumbing is stable.
**Delivers:** `mission-control.css` (third cascade layer over `pico.min.css`/`style.css`), hero "All Systems Online" card, metric-card markup, "Open in Grafana" deep links — plus an explicit manual visual re-walk of every pre-existing v1.1 page (register/catalog/diagnostics/activity feed) under the new dark theme.
**Delivers:** The differentiator "dark control-room visual theme" and the "Open in Grafana" deep-link feature.
**Avoids:** Pitfall 9 (Pico dark reskin silently breaking existing v1.1 forms — a regression automated smoke tests structurally cannot detect).

### Phase 7: Demo Seeding + Final Wiring
**Rationale:** Independent of the observability work (only depends on already-shipped v1.1 write endpoints) but most valuable staged near the end so it can immediately populate the newly-built cards/dashboards for final demo screenshots.
**Delivers:** Idempotent `make seed-demo` (verified for double-run idempotency) + `up-mission-control`/`smoke-mission-control` umbrella targets composing everything above, following the exact compositional style of `up-all`/`smoke-all`.
**Avoids:** Pitfall listed under "Looks Done But Isn't" — `make seed-demo` tested only once from an empty database.

### Phase Ordering Rationale

- **Infrastructure before application code (Phases 1-4 before 5-6):** every research file agrees the trimmed Helm chart's behavior on this specific kind/Docker-Desktop environment is the highest-uncertainty variable and must be de-risked manually (`kubectl`/UI-verified) before any launchpad code is written against assumed Service names, metric names, or resource availability.
- **Hermetically-testable code before live-cluster-dependent UI (Phase 5 before 6):** `app/prometheus.py` can and should be built and fully unit-tested with mocked HTTP calls with zero live cluster, exactly mirroring the existing `test_status.py` pattern — this decouples correctness verification from cluster availability.
- **Visual work strictly last:** the reskin is explicitly the lowest-risk, most-iterative piece and is the one place a manual (not automated) verification step is required — sequencing it last means the data it renders is already proven correct.
- **Avoids the two biggest cross-cutting pitfall themes:** silent-failure verification gates (Targets page, Grafana search API, `up{job=...}==1`) are built into Phases 1-3's own exit criteria rather than assumed; and `make smoke`/`smoke-launchpad` re-runs after Phase 1 catch shared-node resource regressions immediately rather than at final milestone audit.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 1 (Observability Stack Install):** exact resource footprint on the actual dev machine's Docker Desktop allocation is empirically unverified — this is the one number PITFALLS.md/STACK.md both flag as needing a live check, not a values.yaml guess.
- **Phase 3 (Grafana Dashboards-as-Code):** exact PromQL query shapes and label names depend on a live `/metrics` dump not yet taken — ARCHITECTURE.md rates this MEDIUM confidence specifically because it's a phase-level design detail, not resolved in research.

Phases with standard patterns (skip research-phase):
- **Phase 2 (ServiceMonitor Scraping):** well-documented Prometheus Operator convention, HIGH confidence, direct in-repo precedent for existing Service labels.
- **Phase 4 (Additive Makefile Targets):** matches an already-established compositional convention in this codebase.
- **Phase 5 (Native Metric-Card Client):** directly mirrors two existing, already-tested patterns (`app/k8s.py`, `app/status.py`) — no new design needed.
- **Phase 6 (Mission Control UI Reskin):** Pico's official CSS-variable override mechanism is well-documented; the risk is verification discipline (manual visual walk), not unknown technique.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions verified against PyPI, official GitHub releases/README/values.yaml, and Context7; chart version, subchart pins, and library compatibility all independently cross-checked |
| Features | MEDIUM-HIGH | Golden-signals/PromQL/dashboards-as-code claims verified against Google SRE book, Prometheus official docs, and prometheus-community/grafana chart docs (HIGH); status-page UX conventions drawn from multiple agreeing industry sources (MEDIUM); the "NO SIGNAL" degradation pattern is a general reliability pattern applied by analogy to this project's own DIAG-01/02 precedent (MEDIUM) |
| Architecture | HIGH | Chart/CLI behavior verified against official prometheus-community/grafana docs plus in-repo primary-source reads of existing Helm templates and Python modules; MEDIUM only on exact PromQL query shapes, explicitly called out as a phase-level design detail rather than a research blocker |
| Pitfalls | MEDIUM-HIGH | Critical items cross-verified against prometheus-community/helm-charts and prometheus-operator issue trackers plus official docs; Windows/Docker-Desktop-specific resource numbers are MEDIUM and explicitly flagged as needing a live verification pass on the actual dev machine |

**Overall confidence:** HIGH

### Gaps to Address

- **Actual Docker Desktop resource headroom on the dev machine:** no research file can substitute for a live `make observability-up` + `kubectl top`/`describe` check — flag this as the first verification step in Phase 1, with `values-trimmed.yaml` treated as a starting point to be tuned, not a final answer.
- **Real `/metrics` output (exact metric/label names) from both apps:** PITFALLS.md and ARCHITECTURE.md both independently insist this must be dumped live before any PromQL is written — do not build Phase 3 dashboards from a public template or from this research's illustrative PromQL snippets without that verification step.
- **Exact in-cluster Service DNS names post-install:** the Prometheus Service name (`prometheus-operated`) is operator-hardcoded and reliable, but the Grafana Service name depends on the chosen Helm release name — verify with `kubectl get svc -n observability` once installed rather than hardcoding an assumed name into `GRAFANA_BASE_URL`/deep-link construction.
- **CRD teardown policy for `observability-down`:** research surfaces the tradeoff (keep CRDs for faster re-up vs. delete for full teardown) but doesn't mandate a choice — this needs an explicit decision recorded during Phase 1 planning, documented in `docs/known-limitations.md` per the project's existing accepted-risk convention.

## Sources

### Primary (HIGH confidence)
- `/prometheus-community/helm-charts` (Context7) and its raw `Chart.yaml`/`values.yaml`/`README.md` — chart version 87.16.1, subchart pins, component enable/disable flags
- [Prometheus Operator troubleshooting docs](https://prometheus-operator.dev/docs/platform/troubleshooting/) and [prometheus-operator/prometheus-operator issue #149](https://github.com/prometheus-operator/prometheus-operator/issues/149) — `prometheus-operated` Service name hardcoding
- [Google SRE Book — Monitoring Distributed Systems](https://sre.google/sre-book/monitoring-distributed-systems/) — four golden signals
- [Prometheus HTTP API official docs](https://prometheus.io/docs/prometheus/latest/querying/api/) — instant query / query_range semantics
- [Pico CSS official docs — CSS variables](https://picocss.com/docs/css-variables) and [Color schemes](https://picocss.com/docs/color-schemes) — dark-theme override mechanism
- [kind known issues docs](https://kind.sigs.k8s.io/docs/user/known-issues/) — kind-specific control-plane topology quirks
- In-repo primary sources: `charts/launchpad/templates/_helpers.tpl`/`service.yaml`, `charts/field-guide-api/templates/service.yaml`, `apps/launchpad/app/status.py`, `apps/launchpad/app/k8s.py`, `apps/launchpad/tests/test_status.py`, `Makefile`, `.planning/PROJECT.md`

### Secondary (MEDIUM confidence)
- [prometheus-community/helm-charts issues #1513, #2051, #2381, #3131](https://github.com/prometheus-community/helm-charts) — ServiceMonitor release-label discovery requirement, corroborated across multiple independent issues
- [grafana/helm-charts issue #527](https://github.com/grafana/helm-charts/issues/527) and community write-ups — sidecar dashboard cold-start race, one-dashboard-per-ConfigMap recommendation
- [prometheus/prometheus issue #3194](https://github.com/prometheus/prometheus/issues/3194), [linkerd2 #7978](https://github.com/linkerd/linkerd2/issues/7978) — rate() window vs. scrape-interval blank-panel behavior
- [prometheus-community/helm-charts issue #1500](https://github.com/prometheus-community/helm-charts/issues/1500) and [Arthur Koziel — ArgoCD "Too long" CRD fix](https://www.arthurkoziel.com/fixing-argocd-crd-too-long-error/) — CRD annotation-size limit
- [benoitc/gunicorn issues #2020, #1801](https://github.com/benoitc/gunicorn/issues/2020) — worker timeout on slow outbound HTTP calls
- Status-page UX convention surveys (Better Stack Community, UptimeRobot guide, ivbeg/awesome-status-pages) — MEDIUM, industry-convention cross-checks, not authoritative specs

### Tertiary (LOW confidence)
- None flagged — all findings across the four research files carried at least MEDIUM confidence with corroborating sources; no single-source/unverified claims were surfaced as needing explicit LOW-confidence flagging beyond the "gaps to address" items above, which are live-verification gaps rather than source-quality gaps.

---
*Research completed: 2026-07-16*
*Ready for roadmap: yes*
