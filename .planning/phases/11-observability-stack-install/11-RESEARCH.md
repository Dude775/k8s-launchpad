# Phase 11: Observability Stack Install - Research

**Researched:** 2026-07-16
**Domain:** Trimmed `kube-prometheus-stack` Helm install on a local kind/Docker-Desktop cluster, idempotent install/teardown scripting, CRD lifecycle policy, additive-only resource-safety verification
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

### CRD Teardown Policy (OBS-02)
- **D-01:** `observability-down` keeps CRDs — `helm uninstall` only, matching Helm's default behavior. Faster re-install during the v2.0 dev loop; zero cascade-delete risk to Phase 12 ServiceMonitors. Leftover CRDs documented as an accepted limitation in `docs/known-limitations.md` per the project's existing accepted-risk convention.
- **D-02:** Teardown deletes the `observability` namespace (sweeps leftover secrets/configmaps/ephemeral resources). CRDs are cluster-scoped and survive namespace deletion.
- **D-03:** Teardown ends with a built-in verification that the v1.1 app pods (field-guide-api, launchpad) are still healthy — success criterion 3 is enforced by the script itself, matching the self-verifying `cluster-setup.sh` style.

### Install Mechanism (OBS-01)
- **D-04:** Install is driven by idempotent wrapper scripts — `scripts/observability-up.sh` and `scripts/observability-down.sh` — mirroring the existing `scripts/cluster-setup.sh` pattern (idempotent re-runs, self-verifying, POSIX/Git-Bash-safe). Phase 14 wraps these in `make` targets without re-implementing logic.
- **D-05:** Chart sourced via `helm repo add prometheus-community` + `helm upgrade --install --version 87.16.1` (pinned). No vendored chart tarball in git.
- **D-06:** Install script fully self-verifies: waits for all observability pods Running/Ready, then re-checks that the v1.1 app pods are still healthy (no eviction/restart) on every install — catching shared-node resource regressions immediately, not at milestone audit.

### Grafana Admin Credentials
- **D-07:** Explicit known local-dev admin password set in `infra/observability/values-trimmed.yaml` (not the chart default, not .env-driven). Documented in `docs/known-limitations.md` exactly like the v1.1 committed local-dev MongoDB password precedent — local kind only, override for anything real.
- **D-08:** Anonymous viewer access enabled in Grafana (`grafana.ini` anonymous auth, Viewer role) so Phase 15's "Open in Grafana" deep links open without a login wall during demos. Admin login retained for editing. Noted in known-limitations.md.

### Resource Sizing
- **D-09:** Conservative explicit `resources.requests/limits` on every component in `values-trimmed.yaml` from the very first install (research-derived starting values), then verified live with `kubectl top`/`describe` and tuned within this phase. Never install unbounded.
- **D-10:** Install script runs a preflight capacity check before installing: sum the stack's requests, compare against kind node allocatable minus already-running workloads, and **abort with an actionable message** (e.g. "raise Docker Desktop memory to X GB") if it won't fit. Protects the additive-only guarantee before anything lands on the node.
- **D-11:** Prometheus storage is emptyDir (no PVC), retention ~24h — enough for Phase 13's rolling-window uptime panels, lightest footprint, nothing to sweep on teardown. Fits the disposable local demo cluster.

### Claude's Discretion
- Exact per-component request/limit numbers in `values-trimmed.yaml` (starting from research values; live-tuned per D-09).
- Helm `--wait`/timeout strategy vs. script-level `kubectl wait` loops.
- values file layout within `infra/observability/` (single `values-trimmed.yaml` assumed).
- Double-run idempotency details for both scripts (follow the "double-safe teardown" precedent from Phase 2).
- Scrape interval default (coordinate with Phase 13's rate-window sizing pitfall: windows >= 4x scrape interval).

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope. (Pre-existing deferrals — Loki, Alertmanager, SLO panels — remain tracked in REQUIREMENTS.md Future Requirements.)

</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|--------------------|
| OBS-01 | Operator can install a trimmed kube-prometheus-stack (pinned chart 87.16.1; Alertmanager, node-exporter, and kind-incompatible kubeadm scrape jobs disabled; conservative resource limits) into the kind cluster from `infra/observability/` | Standard Stack (chart identity/version/subchart pins live-verified), Pattern 2 (`values-trimmed.yaml` starting point with every disable-flag confirmed against real chart defaults), Common Pitfalls 1-2 (kubeadm scrape noise, unbounded resources), Code Examples (preflight capacity check + confirmed default-value line numbers) |
| OBS-02 | Operator can tear down the observability stack cleanly with an explicit, documented CRD teardown policy — both v1.1 apps keep running untouched | Architecture Patterns (teardown flow diagram matching D-01/D-02/D-03), Common Pitfalls 4 (CRD install-once behavior confirmed via Helm's documented `crds/` mechanism), Don't Hand-Roll (CRD lifecycle — use Helm's own mechanism, don't reimplement) |

</phase_requirements>

## Summary

This phase installs a deliberately trimmed `kube-prometheus-stack` Helm release (chart 87.16.1,
pinned) into a new `observability` namespace, and delivers two self-verifying wrapper scripts —
`scripts/observability-up.sh` and `scripts/observability-down.sh` — that mirror the existing
`scripts/cluster-setup.sh`/`scripts/cluster-teardown.sh` idempotency and self-check style. All
implementation decisions were already locked during `/gsd:discuss-phase` (see User Constraints
below); this research's job is to verify those decisions against the actual chart defaults and
the actual dev machine, not to re-litigate them.

Live verification in this session confirms every load-bearing claim from the milestone-level
research: chart `87.16.1` is genuinely the latest version in the `prometheus-community` repo
(`helm search repo` re-run against a freshly updated index); the bundled subchart pins are
exactly `grafana 12.7.2`, `kube-state-metrics 7.8.1`, `prometheus-node-exporter 4.56.1`; the four
kubeadm-only scrape jobs (`kubeEtcd`, `kubeControllerManager`, `kubeScheduler`, `kubeProxy`) are
genuinely `enabled: true` by default and must be explicitly disabled; almost every component's
`resources:` key defaults to `{}` (fully unbounded) — confirming D-09's "never install unbounded"
constraint is addressing a real, not hypothetical, risk; and `serviceMonitorSelectorNilUsesHelmValues`
defaults to `true`, confirming the release-label pitfall is real for any hand-written ServiceMonitor
in a later phase.

Two new, higher-value findings surfaced only by live inspection this session (not in the
milestone-level research files): (1) **the actual dev machine's Docker Desktop is capped at
9.713 GiB memory / 8 CPUs total** — this is the real number D-10's preflight check must compare
against, not an assumption; and (2) **the installed Helm binary is v4.2.1, not the "locked" Helm
3.21.2** documented in `CLAUDE.md`'s Recommended Stack table (this was already flagged and
resolved as a non-issue in Phase 4's research — `--atomic` is banned project-wide, `helm upgrade
--install --wait --timeout` syntax is identical across both major versions, and CRD/chart behavior
is unaffected). Both observability wrapper scripts must be written and tested against the actual
Helm 4.2.1 binary present on this machine.

**Primary recommendation:** Use `helm upgrade --install kube-prometheus-stack
prometheus-community/kube-prometheus-stack --version 87.16.1 --namespace observability
--create-namespace -f infra/observability/values-trimmed.yaml --wait --timeout <generous>` from
`scripts/observability-up.sh`, with `kubeEtcd/kubeControllerManager/kubeScheduler/kubeProxy`,
`alertmanager`, and `nodeExporter` all set `enabled: false`; `defaultRules.create: false`;
`serviceMonitorSelectorNilUsesHelmValues: false` / `podMonitorSelectorNilUsesHelmValues: false`;
explicit conservative `resources.requests/limits` on `prometheusOperator`, `prometheus.prometheusSpec`,
`grafana`, and `kubeStateMetrics`; Prometheus `retention: 24h` with no PVC (`emptyDir`, chart
default when no storageSpec is set); an explicit `grafana.adminPassword` (never left to the
chart's random-password fallback); and `grafana.grafana.ini` anonymous-viewer config for D-08.
Both scripts must run a live `kubectl`-based preflight/postflight capacity and health check —
never a static "should be fine" assumption — per D-06/D-10.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Observability stack lifecycle (install/upgrade/teardown) | Infra / Helm release (new `observability` namespace) | Scripts (`observability-up.sh`/`down.sh`) | Chart owns pod specs and CRDs; scripts own orchestration, preflight checks, and self-verification — matches the existing `cluster-setup.sh` split of "chart/manifest declares desired state, script drives + verifies convergence" |
| Resource-budget enforcement (preflight capacity check) | Scripts (bash, `kubectl`) | Kubernetes scheduler (final enforcement) | The scheduler already refuses to schedule Pending pods over capacity, but that's a *reactive* failure discovered after `helm install` returns; the *proactive* preflight check belongs in the wrapper script per D-10, using live `kubectl get nodes -o jsonpath` allocatable figures, not a hardcoded budget |
| CRD lifecycle (install-once, survive uninstall) | Helm chart's `crds/` mechanism (chart-owned, install-once) | Script (`observability-down.sh`, explicit non-deletion per D-01) | Helm's documented behavior is CRDs in a chart's `crds/` directory are never touched by `upgrade`/`uninstall` — the teardown script's job is only to *not fight* this behavior and to document it, not to implement CRD deletion logic itself |
| Additive-only safety verification (v1.1 apps unaffected) | Scripts (`observability-up.sh`/`down.sh`, invoking existing `make smoke`/`smoke-launchpad`) | N/A | Per D-03/D-06, this phase's scripts are the enforcement point — they call the pre-existing, already-tested smoke targets rather than re-implementing app health checks |
| Grafana/Prometheus reachability for humans | `kubectl port-forward` (manual, or Phase 14's `make port-forward-grafana`) | N/A | No Ingress/NodePort in this milestone (matches the existing field-guide-api/launchpad port-forward-only precedent); Phase 11 only needs to prove reachability once via manual port-forward as a success-criterion check, not wire a Makefile target (deferred to Phase 14) |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `kube-prometheus-stack` (Helm chart) | **87.16.1** `[VERIFIED: helm registry — helm search repo prometheus-community/kube-prometheus-stack --versions, re-run this session against a freshly-updated index]` | Prometheus Operator + Prometheus + Grafana + kube-state-metrics + CRDs in one release | De-facto standard umbrella chart for this exact workflow; actively maintained by `prometheus-community`; locked by D-05 |
| Prometheus Operator CRDs (`crds` subchart, `version: 0.0.0` per `Chart.yaml`) | ships with 87.16.1 | `ServiceMonitor`/`PodMonitor`/`Prometheus`/etc. CRDs | Install-once by Helm's own `crds/` directory convention — required by Phase 12's ServiceMonitors, which is why D-01 keeps them on teardown |
| Grafana (bundled subchart) | **12.7.2** `[VERIFIED: helm registry — Chart.yaml dependency pin, confirmed via helm pull --untar this session]` | Dashboard UI + sidecar dashboard/datasource provisioning | Bundled and pre-wired to the Prometheus datasource; do not install a second standalone `grafana/grafana` release |
| kube-state-metrics (bundled subchart) | **7.8.1** `[VERIFIED: helm registry — same Chart.yaml confirmation]` | Cluster object-state metrics (pod/deployment counts) | Kept enabled per project decision — feeds the future "All Systems Online" hero card (Phase 16), unlike Alertmanager/node-exporter which are cut |

**Explicitly disabled (`enabled: false`), all confirmed `true` by chart default this session
`[VERIFIED: helm registry — helm show values prometheus-community/kube-prometheus-stack --version 87.16.1]`:**

| Component | Chart default | Required override | Why |
|-----------|---------------|--------------------|-----|
| `alertmanager.enabled` | `true` | `false` | No alerting consumer this milestone |
| `nodeExporter.enabled` | `true` | `false` | Known-flaky DaemonSet on Docker Desktop kind nodes; out of scope (per-service metrics only) |
| `kubeEtcd.enabled` | `true` | `false` | Permanently "down" on kind's containerized control plane — confirmed the key exists and defaults `true` at line 2323 of the pulled values.yaml |
| `kubeControllerManager.enabled` | `true` | `false` | Same as above (line 2022) |
| `kubeScheduler.enabled` | `true` | `false` | Same as above (line 2437) |
| `kubeProxy.enabled` | `true` | `false` | Same as above (line 2547) |
| `defaultRules.create` | `true` | `false` | `PrometheusRule` alerting rules have no consumer without Alertmanager; trims CRD object count and rule-eval CPU |

**Kept enabled (chart defaults, no override needed):** `kubeApiServer` (works fine on kind),
`kubeStateMetrics`, `grafana`.

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `helm repo add prometheus-community https://prometheus-community.github.io/helm-charts` | n/a (repo, not package) | Chart source | One-time repo registration inside `observability-up.sh` (idempotent — `helm repo add` no-ops if the repo alias already exists at the same URL) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `kube-prometheus-stack` umbrella chart | Standalone `prometheus-community/prometheus` + `grafana/grafana` charts | Doubles Helm releases and re-solves CRD/datasource wiring the umbrella chart already does — only worth it for independent team-owned lifecycles, not this single-operator project |
| `serviceMonitorSelectorNilUsesHelmValues: false` (cluster-wide discovery) | Add `release: kube-prometheus-stack` label to every ServiceMonitor | Both work; the values-file override is simpler for a single-tenant local cluster and needs no Makefile-variable coordination for the release name — this is the approach the project's own research and this phase's decisions assume |
| `helm upgrade --install ... --wait` | Script-level `kubectl wait` loops per resource | D-04 leaves this to Claude's discretion; `--wait` is simpler and already the established idiom in this Makefile's `deploy`/`deploy-launchpad` targets (`--wait --timeout 180s`) — reuse it, but budget a longer timeout here (multi-pod rollout, CRDs install first) |

**Installation:**
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update prometheus-community
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --version 87.16.1 \
  --namespace observability --create-namespace \
  -f infra/observability/values-trimmed.yaml \
  --wait --timeout 300s
```

**Version verification:** Confirmed live this session via `helm search repo
prometheus-community/kube-prometheus-stack --versions` (after `helm repo update`) — top result is
`87.16.1`, `appVersion v0.92.1`. Subchart pins (`grafana 12.7.2`, `kube-state-metrics 7.8.1`,
`prometheus-node-exporter 4.56.1`) confirmed by `helm pull --untar` and reading `Chart.yaml`
directly this session. `[VERIFIED: helm registry]`

## Package Legitimacy Audit

This phase installs one artifact: the `kube-prometheus-stack` **Helm chart**, not an npm/pip/cargo
package — the standard slopcheck/registry-verification protocol targets language package
managers and does not have a direct Helm-chart equivalent. In lieu of slopcheck, the chart was
verified by the strongest available signal: a direct `helm repo add` + `helm repo update` +
`helm search repo --versions` + `helm pull --untar` round-trip against the chart's own official
repository URL (`https://prometheus-community.github.io/helm-charts`, matching Artifact Hub's
listed source), performed live in this research session — not a WebSearch claim, not training
data. The chart is maintained by the `prometheus-community` GitHub organization (the de-facto
upstream for this ecosystem, already relied upon and cited in this project's own milestone-level
research).

| Package | Registry | Age | Downloads | Source Repo | Verification | Disposition |
|---------|----------|-----|-----------|--------------|---------------|-------------|
| `kube-prometheus-stack` @ 87.16.1 | Helm (`prometheus-community` repo) | Years (long-running project, weekly releases) | N/A (Helm repos don't expose download counts) | `github.com/prometheus-community/helm-charts` | Live `helm repo`/`helm pull` round-trip this session — chart content matches official upstream | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none (no pip/npm/cargo packages introduced
by this phase).
**Packages flagged as suspicious [SUS]:** none.

No `[ASSUMED]` tag applies to the chart identity/version — this was independently and directly
verified against the live registry in this session, which exceeds the bar for `[VERIFIED]`
provenance (an authoritative source, not merely "the name resolves").

## Architecture Patterns

### System Architecture Diagram

```
Operator runs: scripts/observability-up.sh
        │
        ├─▶ Step 0: preflight capacity check (D-10)
        │     kubectl get nodes -o jsonpath='{.items[0].status.allocatable.memory}'
        │     kubectl get pods -A -o jsonpath='{...requests...}'  (sum existing workload)
        │     compare: (existing requests + trimmed-stack requests) vs allocatable
        │     ── FAILS ──▶ abort with actionable message
        │                  ("raise Docker Desktop memory to X GB, see Settings > Resources")
        │     ── PASSES ─▶ continue
        │
        ├─▶ Step 1: helm repo add/update prometheus-community (idempotent)
        │
        ├─▶ Step 2: helm upgrade --install kube-prometheus-stack ... --namespace observability
        │           --create-namespace -f values-trimmed.yaml --wait --timeout 300s
        │     (installs CRDs once, then Prometheus Operator, then Prometheus CR + Grafana +
        │      kube-state-metrics pods — 4 long-running pods + 1 short-lived admission-webhook
        │      patch Job)
        │
        ├─▶ Step 3: self-verify observability pods Running/Ready (D-06)
        │     kubectl -n observability get pods --field-selector=status.phase!=Running
        │     (or: kubectl wait --for=condition=Ready pod -l ... -n observability --timeout=Ns)
        │
        └─▶ Step 4: re-run make smoke && make smoke-launchpad (D-06)
              ── FAIL ──▶ existing app pods were disturbed — abort/report, additive-only violated
              ── PASS ──▶ observability-up complete, prints port-forward instructions

Operator runs: scripts/observability-down.sh
        │
        ├─▶ Step 1: helm uninstall kube-prometheus-stack -n observability  (D-01: CRDs untouched)
        │
        ├─▶ Step 2: kubectl delete namespace observability --ignore-not-found  (D-02: sweep leftovers)
        │     (CRDs are cluster-scoped — survive namespace deletion, confirmed by design)
        │
        └─▶ Step 3: re-run make smoke && make smoke-launchpad (D-03)
              ── FAIL ──▶ report — v1.1 apps were affected by teardown (should never happen)
              ── PASS ──▶ observability-down complete
```

### Recommended Project Structure

```
infra/observability/
├── values-trimmed.yaml       # single values file (per Claude's Discretion, D-09/D-10/D-11 baked in)
└── .gitkeep                  # (existing, remove once values-trimmed.yaml lands)

scripts/
├── observability-up.sh       # NEW — mirrors cluster-setup.sh: prereq gate, preflight capacity
│                              #   check, helm repo add/update, helm upgrade --install --wait,
│                              #   pod-readiness self-check, make smoke/smoke-launchpad re-run
└── observability-down.sh     # NEW — mirrors cluster-teardown.sh: helm uninstall, namespace
                               #   delete, make smoke/smoke-launchpad re-run
```

### Pattern 1: Idempotent, self-verifying wrapper script (existing project convention)

**What:** `scripts/cluster-setup.sh` establishes the house style this phase must follow: `set -o
errexit` (no `pipefail`, since idempotency guards rely on `|| true`), `export
MSYS_NO_PATHCONV=1` at the top, a prerequisite tool-gate before any mutating step, guarded
"already exists — skipping" branches for every mutating step, and an explicit self-verification
step at the end (registry push/pull round-trip) rather than trusting the tool's own exit code
alone.

**When to use:** Both new scripts in this phase.

**Example (adapted skeleton for `observability-up.sh`):**
```bash
#!/usr/bin/env bash
# scripts/observability-up.sh
set -o errexit
export MSYS_NO_PATHCONV=1
KCTX='--context=kind-kind'

command -v helm >/dev/null 2>&1 || { echo "ERROR: helm not installed."; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo "ERROR: kubectl not installed."; exit 1; }

echo "==> Step 0: Preflight capacity check..."
ALLOCATABLE_MI=$(kubectl ${KCTX} get nodes -o jsonpath='{.items[0].status.allocatable.memory}')
# ... convert Ki/Mi, sum existing pod requests via kubectl get pods -A -o json + jq (or awk),
# compare against the trimmed stack's known requests total; abort with an actionable message
# naming the exact Docker Desktop setting to change if it won't fit.

echo "==> Step 1: Ensuring prometheus-community repo is registered..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
helm repo update prometheus-community

echo "==> Step 2: Installing/upgrading trimmed kube-prometheus-stack..."
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --version 87.16.1 \
  --namespace observability --create-namespace \
  -f infra/observability/values-trimmed.yaml \
  --wait --timeout 300s

echo "==> Step 3: Verifying all observability pods are Running/Ready..."
kubectl ${KCTX} wait --for=condition=Ready pod --all -n observability --timeout=180s

echo "==> Step 4: Re-verifying v1.1 apps are unaffected..."
make smoke
make smoke-launchpad

echo "==> observability-up complete."
```

### Pattern 2: values-trimmed.yaml starting point (live-verified against actual chart defaults)

**What:** All keys below were checked this session against the real `87.16.1` `values.yaml`
(not assumed) — every `resources:` key for `prometheusOperator`, `prometheus.prometheusSpec`,
`grafana`, and (separately, in the `kube-state-metrics` subchart) defaults to `{}` (fully
unbounded), confirming D-09 is addressing a genuine gap, not a defensive-but-unnecessary
precaution.

```yaml
# infra/observability/values-trimmed.yaml
# Chart: prometheus-community/kube-prometheus-stack @ 87.16.1 (pinned, D-05)

alertmanager:
  enabled: false          # chart default: true — no alerting consumer this milestone
nodeExporter:
  enabled: false          # chart default: true — flaky DaemonSet on Docker Desktop kind nodes
kubeEtcd:
  enabled: false          # chart default: true — permanently down on kind (Pitfall 1)
kubeControllerManager:
  enabled: false          # chart default: true — same
kubeScheduler:
  enabled: false          # chart default: true — same
kubeProxy:
  enabled: false          # chart default: true — same
defaultRules:
  create: false           # chart default: true — no Alertmanager consumer for these rules

kubeStateMetrics:
  enabled: true           # chart default; kept for future hero-card cluster-state metrics

grafana:
  enabled: true
  adminUser: admin
  adminPassword: <explicit-local-dev-value>   # D-07 — chart falls back to a RANDOM password
                                                # (grafana.password helper) if this is left unset;
                                                # verified in charts/grafana/templates/_config.tpl
                                                # this session — never leave this unset
  "grafana.ini":
    auth.anonymous:
      enabled: true
      org_role: Viewer     # D-08 — Phase 15/16 "Open in Grafana" deep links must not hit a login wall
  sidecar:
    dashboards:
      enabled: true         # already the chart default — kept explicit for readability
      label: grafana_dashboard
      labelValue: "1"
      searchNamespace: ALL  # already the chart default (confirmed this session) — Phase 13 dashboards
                             # land in infra/observability/ or wherever the sidecar is told to look
  resources:
    requests: { cpu: 50m, memory: 128Mi }
    limits: { cpu: 200m, memory: 256Mi }

prometheusOperator:
  resources:
    requests: { cpu: 50m, memory: 100Mi }
    limits: { cpu: 200m, memory: 256Mi }

prometheus:
  prometheusSpec:
    retention: 24h          # chart default: 10d — shortened per D-11 (disposable local cluster,
                             # enough for Phase 13's rolling-window uptime panels)
    resources:
      requests: { cpu: 100m, memory: 256Mi }
      limits: { cpu: 500m, memory: 512Mi }
    serviceMonitorSelectorNilUsesHelmValues: false   # chart default: true — required so Phase 12's
                                                       # standalone ServiceMonitors (no `release:`
                                                       # label) are discovered cluster-wide
    podMonitorSelectorNilUsesHelmValues: false        # same, for PodMonitors
    # No storageSpec set => Prometheus uses emptyDir by default (D-11: no PVC, nothing to sweep
    # on teardown; verified this is the chart's own no-storageSpec-set behavior, not a special flag)
```

### Anti-Patterns to Avoid

- **Leaving any `resources:` block at its chart default `{}`:** Confirmed live this session —
  `prometheusOperator.resources`, `prometheus.prometheusSpec.resources`, `grafana.resources`, and
  the admission-webhook Job's `resources` all default to `{}` (fully unbounded). On a
  9.7 GiB-total Docker Desktop VM already running two Flask apps + two MongoDB pods, this is the
  single highest-risk default to leave untouched.
- **`kubectl apply -f` directly against any Prometheus Operator CRD manifest:** The `Prometheus`
  CRD alone is ~830 KB (`crd-prometheuses.yaml`, measured this session) — client-side apply's
  `last-applied-configuration` annotation has a hard 262144-byte Kubernetes API limit, so a direct
  `kubectl apply` on this CRD can fail outright. Not a risk for this phase's install flow (Helm's
  own `crds/` mechanism installs CRDs without going through that annotation path), but a hard
  ban for any *manual* CRD reapply during debugging.
- **Assuming `grafana.adminPassword` can be safely omitted "since it's local-dev anyway":**
  Confirmed via direct chart-template read this session (`charts/grafana/templates/_config.tpl`)
  — if `adminPassword` is unset, the chart falls back to `{{ include "grafana.password" . }}`,
  which generates a value (not a fixed, known, git-diffable string). D-07 exists precisely to
  avoid this non-determinism, not merely to avoid the chart's own "example" password.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Prometheus Operator + CRD RBAC wiring | A hand-rolled Deployment + manually-applied CRDs + custom RBAC | `kube-prometheus-stack` chart (already locked, D-05) | The chart already solves CRD installation ordering, operator RBAC, and Prometheus CR reconciliation — reimplementing any piece of this reintroduces exactly the CRD-ordering and annotation-size pitfalls documented above |
| Random-password generation avoidance for Grafana | A custom post-install `kubectl patch secret` script to force a known password after install | `grafana.adminPassword` set directly in `values-trimmed.yaml` (D-07) | The values-file key already exists and is the chart's own supported mechanism — patching the Secret after the fact is a race against the chart's own Secret-creation Job and unnecessary complexity |
| Pod-readiness waiting | A custom polling loop with sleep/retry logic reinventing `kubectl wait` | `kubectl wait --for=condition=Ready pod --all -n observability --timeout=Ns` (or Helm's own `--wait`) | Kubernetes already exposes exactly this readiness-gate primitive; a hand-rolled sleep loop is both slower to write and more failure-prone (must handle CrashLoopBackOff, ImagePullBackOff, etc. that `kubectl wait` already surfaces via its own timeout/error path) |
| Resource-capacity math | A hardcoded "should fit" assumption baked into documentation only | A live `kubectl get nodes -o jsonpath=...allocatable...` + `kubectl get pods -A` sum, computed at script runtime (D-10) | The actual number (9.713 GiB total on this exact dev machine, confirmed this session) is a fact about *this* machine at *this* moment — Docker Desktop's allocation is operator-configurable and can change; a script-time live check is the only approach that stays correct across machines/reconfigurations |

**Key insight:** Every "don't hand-roll" item above already has a first-class solution shipped by
either the chart itself or `kubectl`/Helm's own CLI surface — the discipline this phase needs is
*wiring these correctly together in bash*, not building any new mechanism from scratch.

## Common Pitfalls

### Pitfall 1: kubeadm-only control-plane scrape jobs are enabled by default and permanently "down" on kind

**What goes wrong:** Immediately after a naive `helm install` with only Alertmanager/node-exporter
disabled, the Prometheus Targets page shows `kube-etcd`, `kube-scheduler`,
`kube-controller-manager`, and `kube-proxy` jobs all stuck `down` — undermining any later
"All Systems Online" demo (Phase 16).
**Why it happens:** Confirmed live this session — all four keys (`kubeEtcd`, `kubeControllerManager`,
`kubeScheduler`, `kubeProxy`) default to `enabled: true` in chart 87.16.1's `values.yaml`; these
scrape jobs assume a kubeadm cluster where control-plane components bind metrics to a
non-loopback address, which kind's containerized nodes don't provide.
**How to avoid:** Set all four `enabled: false` in `values-trimmed.yaml` from the very first
install (already reflected in Pattern 2 above).
**Warning signs:** `kubectl -n observability port-forward svc/kube-prometheus-stack-prometheus
9090:9090` then visiting `/targets` shows red/down entries for any of these four jobs.

### Pitfall 2: Every remaining component's `resources:` defaults to fully unbounded

**What goes wrong:** Even with Alertmanager/node-exporter/kubeadm-jobs disabled, the four
remaining components (`prometheusOperator`, `prometheus.prometheusSpec`, `grafana`,
`kube-state-metrics`) still schedule with **no resource requests at all** unless explicitly set —
confirmed by direct inspection of the pulled chart's `values.yaml` this session (`resources: {}`
appears 10 times across the file, including at every one of these four components' relevant
key). On a 9.7 GiB Docker Desktop VM already running field-guide-api + launchpad + two MongoDB
pods (themselves also unbounded — confirmed by reading `charts/*/templates/mongodb/deployment.yaml`,
which has no `resources:` block at all), this is the direct, verified mechanism behind
PITFALLS.md's Pitfall 7 (resource exhaustion / evicted app pods).
**Why it happens:** The chart's defaults target production clusters with generous node capacity,
not a single-laptop-shared kind node.
**How to avoid:** Set explicit conservative `resources.requests/limits` for all four components
(Pattern 2 above) from the first install, and run the D-10 preflight capacity check before
`helm upgrade --install` ever executes.
**Warning signs:** `kubectl get pods -n observability` shows `Pending` with `kubectl describe`
reporting `Insufficient cpu`/`Insufficient memory`; field-guide-api or launchpad pods start
getting evicted/OOMKilled after `observability-up` even though their own charts didn't change.

### Pitfall 3: ServiceMonitor discovery requires the `release:` label unless explicitly disabled

**What goes wrong:** Standalone ServiceMonitors created in a later phase (12) without a
`release: kube-prometheus-stack` label are silently discovered as zero targets — no error
anywhere.
**Why it happens:** Confirmed live this session — `prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues`
defaults to `true` in the pulled 87.16.1 `values.yaml` (and the equivalent
`podMonitorSelectorNilUsesHelmValues`), which restricts ServiceMonitor discovery to objects
carrying that exact label.
**How to avoid:** This phase sets both to `false` in `values-trimmed.yaml` (Pattern 2 above) so
Phase 12's standalone ServiceMonitors need no coordinating label — this decision must be made
*here*, in the values file this phase writes, not deferred to Phase 12.
**Warning signs:** N/A for this phase directly (Phase 12's concern), but the values-file
override is this phase's responsibility to land correctly the first time.

### Pitfall 4: `helm uninstall` never removes CRDs — this is Helm's documented, intentional behavior

**What goes wrong:** An operator expecting `observability-down` to fully "reset" the cluster is
surprised that `kubectl get crd | grep monitoring.coreos.com` still shows CRDs after teardown.
**Why it happens:** Helm's `crds/` directory convention is install-once, never touched by
`upgrade` or `uninstall` — by design, to avoid accidentally deleting user data tied to CRDs.
**How to avoid:** This is D-01's explicit, already-locked decision (keep CRDs on
`observability-down`) — document it plainly in `docs/known-limitations.md` as an accepted
tradeoff (faster re-`up`, zero cascade-delete risk to Phase 12's future ServiceMonitors), not as
a bug.
**Warning signs:** None to guard against — this is the intended, documented behavior per D-01.

### Pitfall 5: `grafana.adminPassword` silently becomes a random value if left unset

**What goes wrong:** An operator assumes "no adminPassword set = chart uses some sane documented
default like `prom-operator`" and is surprised the Grafana login doesn't work with a value copied
from an old blog post.
**Why it happens:** Confirmed by direct template inspection this session
(`charts/grafana/templates/_config.tpl`, `grafana.secretsData` helper): if `.Values.adminPassword`
is falsy, the chart calls `{{ include "grafana.password" . }}` instead — a generated value, not a
fixed public default.
**How to avoid:** D-07 already mandates setting `grafana.adminPassword` explicitly in
`values-trimmed.yaml` to a known, git-diffable local-dev value, documented in
`docs/known-limitations.md` exactly like the existing MongoDB dev-password precedent.
**Warning signs:** Login fails with `admin`/`prom-operator` (a commonly-assumed community
default) after a fresh install where `adminPassword` was left unset.

### Pitfall 6: Windows Git Bash / MSYS path-mangling on new script arguments

**What goes wrong:** Any argument in the new scripts that looks like an absolute POSIX path
(label selectors, `/api/v1/...`-shaped strings, `-f infra/observability/values-trimmed.yaml`) can
be silently mangled by Git Bash's MSYS path-conversion layer.
**Why it happens:** This is the same, already-documented project-wide Windows/Git-Bash pitfall
`cluster-setup.sh` already guards against via `export MSYS_NO_PATHCONV=1` at the top of the
script.
**How to avoid:** Both new scripts must open with the same `export MSYS_NO_PATHCONV=1` line —
copy the existing precedent verbatim, don't re-derive it.
**Warning signs:** A path argument that "looks right" in the script source fails at runtime with
a mangled absolute Windows path substituted in.

## Code Examples

### Preflight capacity check (D-10) — sketch, tune exact jq/awk parsing during implementation

```bash
# Source: kubectl's own JSONPath support — standard project convention (already used in
# cluster-setup.sh's registry-verification step)
ALLOCATABLE_KI=$(kubectl --context=kind-kind get nodes -o jsonpath='{.items[0].status.allocatable.memory}' | tr -d 'Ki')
# Sum existing pod memory requests across all namespaces (field-guide-api, launchpad, their
# mongos, kube-system) — kubectl's own jsonpath range syntax avoids a jq dependency:
EXISTING_REQ_KI=$(kubectl --context=kind-kind get pods -A -o jsonpath='{range .items[*].spec.containers[*]}{.resources.requests.memory}{"\n"}{end}' | ...)  # convert/sum
TRIMMED_STACK_REQ_KI=<sum of the values-trimmed.yaml requests above, or re-derive from the file>
if [ $(( ALLOCATABLE_KI - EXISTING_REQ_KI )) -lt "$TRIMMED_STACK_REQ_KI" ]; then
  echo "ERROR: insufficient memory headroom for the observability stack."
  echo "  Allocatable: ${ALLOCATABLE_KI}Ki | Already requested: ${EXISTING_REQ_KI}Ki | Stack needs: ${TRIMMED_STACK_REQ_KI}Ki"
  echo "  ACTION: raise Docker Desktop's memory allocation (Settings > Resources > Memory) to at least <N> GB and retry."
  exit 1
fi
```

### Confirmed default value locations (for implementer cross-reference, chart 87.16.1)

```
# From `helm pull prometheus-community/kube-prometheus-stack --version 87.16.1 --untar`,
# reading kube-prometheus-stack/values.yaml directly:
kubeControllerManager: (line 2022)  enabled: true
kubeEtcd:              (line 2323)  enabled: true
kubeScheduler:         (line 2437)  enabled: true
kubeProxy:             (line 2547)  enabled: true
prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues: (line 4445) true
prometheus.prometheusSpec.podMonitorSelectorNilUsesHelmValues:     (line 4468) true
prometheus.prometheusSpec.retention:                                (line 4536) 10d
grafana.sidecar.dashboards.enabled/label/labelValue/searchNamespace: already
  enabled: true, grafana_dashboard, "1", ALL — no override strictly required, kept explicit anyway
grafana.adminPassword: commented out by default (line 1466) — chart falls back to a
  randomly-generated value via the `grafana.password` template helper if left unset
  (charts/grafana/templates/_config.tpl:172-180, read directly this session)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|-------------------|---------------|--------|
| Helm 3.21.2 (as documented in `CLAUDE.md`'s Recommended Stack table) | Helm **4.2.1** is the actual binary installed on this dev machine (confirmed via `helm version --short` this session) | Already resolved during Phase 4 (v1.0) — `--atomic` banned project-wide, `--rollback-on-failure` is the Helm-4-correct equivalent if ever needed | No action needed for this phase: neither new script uses `--atomic`; `helm upgrade --install --wait --timeout` syntax is identical across Helm 3/4. Flag this explicitly so Phase 11's scripts are tested against the real Helm 4.2.1 binary, not an assumed Helm 3 one. |
| `kubeStateMetrics` used to require a manually-added `release:` label for its own ServiceMonitor | Chart 87.16.1's `kube-state-metrics.releaseLabel: true` already adds it automatically (confirmed via `Chart.yaml`/values inspection this session) | Bundled subchart default, current in 87.16.1 | No action needed for this phase — only relevant context for Phase 12's own ServiceMonitors, which are standalone (not this bundled one) |

**Deprecated/outdated:** None specific to this phase beyond the Helm 3→4 note above, which is
already a resolved, documented non-issue project-wide.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The trimmed stack's total resource *limits* (per Pattern 2's conservative starting values: ~200m/200m/500m/~50m CPU and ~256Mi/256Mi/512Mi/~64Mi memory across grafana/operator/prometheus/kube-state-metrics) will fit comfortably alongside the existing field-guide-api + launchpad + two MongoDB pods on this machine's 9.713 GiB Docker Desktop allocation | Standard Stack, Pattern 2 | If wrong, `observability-up.sh`'s own preflight check (D-10) and postflight `make smoke`/`smoke-launchpad` re-run (D-06) are the safety net — this assumption is not load-bearing on its own, only a starting point per D-09, explicitly meant to be live-tuned |
| A2 | `kube-state-metrics`'s own default `resources:` (not independently pulled/verified this session — only the parent chart's `values.yaml` keys were read directly) also defaults to unbounded, consistent with every other component checked | Common Pitfalls, Pitfall 2 | Low risk — kube-state-metrics is a lightweight, well-known component (typically <50Mi RSS); even if its chart-level default resource block differs slightly from the pattern observed in the other three components, its absolute footprint is small enough not to threaten the capacity budget |
| A3 | `--wait --timeout 300s` is sufficient for a first-time CRD install + 4-pod rollout on this machine | Pattern 1 code example | If the timeout is too short, `helm upgrade --install` returns a non-zero exit and the script's own errexit halts — safe failure mode, just requires a retry with a longer timeout; not a correctness risk, only a possible false-negative on a slow first pull (images not yet cached in the local registry/Docker Desktop) |

**If this table is empty:** N/A — see entries above; none of these are decisions requiring user
reconfirmation (they are tuning/timing parameters explicitly delegated to Claude's Discretion in
CONTEXT.md), but are logged here per the assumptions-log discipline since they weren't
independently re-verified with the same rigor as the chart-default claims above.

## Open Questions

1. **Exact conservative resource numbers for `kube-state-metrics.resources`**
   - What we know: The parent chart's four other components all default to unbounded
     `resources: {}`; kube-state-metrics is a lightweight component in every other project that
     runs it (typically tens of Mi RSS, negligible CPU).
   - What's unclear: The exact chart-level default for `kube-state-metrics.resources` specifically
     was not independently pulled and read this session (only referenced by extension from the
     pattern observed elsewhere in the parent chart).
   - Recommendation: Set an explicit small `resources.requests: {cpu: 10m, memory: 32Mi}` /
     `limits: {cpu: 50m, memory: 64Mi}` for `kubeStateMetrics` in `values-trimmed.yaml` regardless
     of what its own chart default turns out to be — consistent with D-09's "never install
     unbounded" rule, and cheap enough that being slightly over-conservative costs nothing.

2. **Exact total Docker Desktop headroom needed, expressed as an actionable operator message**
   - What we know: The dev machine currently reports 9.713 GiB total / 8 CPUs, with no kind
     cluster currently running (this session found `kind get clusters` returned nothing) — so the
     live number reflects an idle Docker Desktop, not one already running the full v1.1 stack.
   - What's unclear: The precise combined footprint of a running kind node (kubelet/containerd/
     CoreDNS/kube-proxy system overhead) + field-guide-api + launchpad + two MongoDB pods +
     the trimmed observability stack, all simultaneously, has not been measured live in this
     session (no cluster was up to measure against).
   - Recommendation: The D-10 preflight check should be a **live, runtime** calculation (already
     the plan) rather than a number baked into `values-trimmed.yaml` comments — this defers the
     precise threshold to the moment `make cluster-up && make up-all && make observability-up` are
     actually run together, which is the only point a true measurement is possible. Document the
     first live-measured number in `docs/known-limitations.md` once observed during
     implementation/verification, per the Blockers/Concerns note already in `STATE.md`.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|--------------|-----------|---------|----------|
| Docker Desktop | kind cluster host | Yes | 4.81.0 (engine 29.6.1) | — |
| Docker Desktop memory/CPU allocation | Observability stack capacity budget | Yes | **9.713 GiB / 8 CPUs total** (confirmed live via `docker info` this session — this is the number D-10's preflight check must compare against) | Operator raises the setting manually if the preflight check fails; no code fallback |
| kind | Local Kubernetes cluster | Yes (binary present; no cluster currently running — `kind get clusters` returned empty this session) | Not independently re-checked this session (v0.32.0 per CLAUDE.md, unchanged) | — |
| kubectl | Cluster interaction | Yes | Client present; no live cluster to query server version against this session | — |
| helm | Chart install | Yes | **v4.2.1+gd591a19** (confirmed via `helm version --short` this session — NOT the "locked" 3.21.2 documented in `CLAUDE.md`; already a resolved non-issue per Phase 4 research) | — |
| `prometheus-community` Helm repo | Chart source | Yes (already registered in this environment's Helm config; `helm repo update` succeeded this session) | Chart 87.16.1 confirmed current | — |
| `bitnami` Helm repo | (unrelated to this phase — pre-existing repo registration, noted only because `helm repo list` surfaced it) | Yes, registered | N/A | Not used by this phase (Bitnami charts are explicitly banned per project convention) |

**Missing dependencies with no fallback:** None identified — all required tools are present on
this dev machine.

**Missing dependencies with fallback:** None — this phase's only "soft" dependency is Docker
Desktop's memory allocation being sufficient, which has an operator-actionable fallback (raise
the setting) already built into D-10's design.

## Security Domain

`security_enforcement` is not explicitly disabled in `.planning/config.json` (absent = enabled),
so this section is included, scoped to what's actually relevant for an infra-install phase with
no new application code or user-facing endpoints.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|--------------------|
| V2 Authentication | Partial | Grafana admin login only (local, no external exposure — port-forward only, matching the existing field-guide-api/launchpad precedent) |
| V3 Session Management | No | No new session-bearing surface introduced by this phase |
| V4 Access Control | Partial | Kubernetes RBAC is chart-managed (Prometheus Operator's own ServiceAccount/ClusterRole, bundled); no custom RBAC authored this phase |
| V5 Input Validation | No | No user input surface in this phase (bash scripts take no untrusted arguments; `values-trimmed.yaml` is a static, committed file) |
| V6 Cryptography | Partial | Grafana admin password is a plaintext committed local-dev value (D-07) — same accepted-risk pattern already established for MongoDB in `docs/known-limitations.md`; never a real credential |

### Known Threat Patterns for this phase's stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|-----------------------|
| Committed Grafana admin password looking like a leaked credential to a repo scanner | Information Disclosure (cosmetic) | Use an obviously-fake local-dev value (mirroring the existing `fieldguide-dev-password`/`launchpad-dev-password` naming convention), documented explicitly in `docs/known-limitations.md` as accepted local-dev-only risk (D-07) |
| Grafana/Prometheus exposed via NodePort/LoadBalancer "for convenience" | Elevation of Privilege / widened attack surface | Keep access to `kubectl port-forward` only — no Ingress, no NodePort, consistent with the existing field-guide-api/launchpad access pattern |
| Anonymous Grafana viewer access (D-08) broadening exposure beyond intended local-only use | Information Disclosure | Scoped to `Viewer` role only (no edit/admin), and only reachable via port-forward (never exposed beyond localhost) — acceptable tradeoff explicitly chosen for Phase 15/16's frictionless demo requirement, documented in `docs/known-limitations.md` |

## Sources

### Primary (HIGH confidence — live-verified this session)

- `helm search repo prometheus-community/kube-prometheus-stack --versions` (after `helm repo
  update`) — confirms chart `87.16.1` is current, `appVersion v0.92.1`
- `helm pull prometheus-community/kube-prometheus-stack --version 87.16.1 --untar` +
  direct reads of the untarred `Chart.yaml` and `values.yaml` — confirms subchart pins
  (grafana 12.7.2, kube-state-metrics 7.8.1, prometheus-node-exporter 4.56.1), all four
  kubeadm-scrape-job defaults (`enabled: true`), `serviceMonitorSelectorNilUsesHelmValues: true`
  default, `retention: 10d` default, `grafana.sidecar.dashboards.*` already-enabled defaults,
  and the ~10 occurrences of unbounded `resources: {}`
- `charts/grafana/templates/_config.tpl` (from the same untarred pull) — confirms the
  `grafana.password` random-fallback behavior when `adminPassword` is unset
- `find ... -iname "*.yaml" -path "*crds*" | xargs wc -c` on the untarred chart — confirms the
  `Prometheus` CRD is ~830 KB, well past the 262144-byte client-side-apply annotation limit
- `docker version` / `docker info` on this dev machine — confirms Docker Desktop 4.81.0,
  9.713 GiB total memory, 8 CPUs, no kind cluster currently running
- `helm version --short` on this dev machine — confirms Helm **v4.2.1+gd591a19** is the actual
  installed binary (not the "locked" 3.21.2 in `CLAUDE.md`, an already-resolved non-issue)
- In-repo: `scripts/cluster-setup.sh`, `scripts/cluster-teardown.sh` — the idempotent,
  self-verifying script style this phase's two new scripts must mirror (read directly)
- In-repo: `charts/field-guide-api/values.yaml`, `charts/launchpad/values.yaml`,
  `charts/*/templates/mongodb/deployment.yaml` — confirms existing app resource footprint
  (50m/128Mi req, 250m/256Mi limit per Flask app; MongoDB deployments have **no** `resources:`
  block at all — fully unbounded, same risk class as the new observability components)
  Makefile — confirms `deploy`/`deploy-launchpad` targets already use `--wait --timeout 180s`,
  no `--atomic`, and the existing `smoke`/`smoke-launchpad`/`smoke-all` targets this phase's
  scripts must invoke, not reimplement
- `docs/known-limitations.md` — confirms the existing accepted-risk documentation convention
  (committed MongoDB dev passwords) that D-01/D-07/D-08 extend

### Secondary (inherited from milestone-level research, cross-checked, not re-verified live this
session beyond what's listed above)

- `.planning/research/SUMMARY.md`, `STACK.md`, `PITFALLS.md`, `ARCHITECTURE.md` — full v2.0
  milestone research, HIGH confidence per their own source hierarchies; this phase's research
  narrows and live-verifies their Phase-11-relevant claims specifically

### Tertiary (LOW confidence)

- None — every claim in this document is either a direct live-tool-verified fact from this
  session or an explicitly-flagged assumption in the Assumptions Log above.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — chart version, subchart pins, and every default-value claim were
  independently re-verified this session via direct `helm` commands and file reads, not carried
  over from training data or unverified WebSearch
- Architecture: HIGH — the install/teardown flow directly extends an already-proven, in-repo
  script pattern (`cluster-setup.sh`/`cluster-teardown.sh`); no novel architecture introduced
- Pitfalls: HIGH — all five phase-relevant pitfalls were confirmed against the actual pulled
  chart's `values.yaml`/templates this session, not merely cited from milestone research

**Research date:** 2026-07-16
**Valid until:** 14 days (chart releases ~weekly; re-verify the pinned version and default-value
claims if planning is delayed beyond two weeks, per the project's own "verify empirically" flag
in `STATE.md`)
