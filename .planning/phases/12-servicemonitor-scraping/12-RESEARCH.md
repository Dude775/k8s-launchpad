# Phase 12: ServiceMonitor Scraping - Research

**Researched:** 2026-07-18
**Domain:** Prometheus Operator `ServiceMonitor` CRD scraping (standalone, out-of-chart) + Git-Bash-safe Prometheus HTTP API self-verification
**Confidence:** HIGH

## Summary

This phase is almost entirely a **verification and scripting** problem, not a design problem — the hard architectural decisions (namespace split, `serviceMonitorSelectorNilUsesHelmValues: false`, standalone manifest location, job naming) were already locked in Phase 11's `values-trimmed.yaml` and this phase's own CONTEXT.md (D-01..D-12). What remains is: (1) write two small, near-identical `ServiceMonitor` manifests that match the Services' already-existing labels exactly, (2) extend `scripts/observability-up.sh` with a CRD-existence guard + `kubectl apply` step, and (3) extend the same script with a self-verifying poll loop against the Prometheus HTTP API that mirrors the exact background-port-forward-with-trap pattern already used by `make smoke`/`make smoke-launchpad` in the Makefile — not a new mechanism.

Both scrape targets' Services (`charts/field-guide-api/templates/service.yaml`, `charts/launchpad/templates/service.yaml`) already carry `app.kubernetes.io/name: field-guide-api` / `app.kubernetes.io/name: launchpad` (verified by direct read of `_helpers.tpl` and `service.yaml` in both charts) and a named `http` port — zero chart edits are needed, confirming the Phase 11 ARCHITECTURE.md finding. Because `values-trimmed.yaml` already sets `serviceMonitorSelectorNilUsesHelmValues: false` (Phase 11, live-installed), the two new `ServiceMonitor` objects do **not** need a `release:` label — Pitfall 2 from the v2.0 research (silent zero-target discovery from a missing `release:` label) is already structurally avoided by a decision made one phase ago. The remaining risk surface is narrower: get the two independent selector layers right (Service labels via `spec.selector.matchLabels`, and namespace via `spec.namespaceSelector.matchNames: ["default"]`), and prove scraping with a live `up{job=...}` query — not just `kubectl get servicemonitor` succeeding.

**Primary recommendation:** Two flat `ServiceMonitor` YAML files in `infra/observability/`, applied via `kubectl apply -f <file1> -f <file2>` from an extended `scripts/observability-up.sh`, verified with a background `kubectl port-forward` to the already-confirmed `svc/kube-prometheus-stack-prometheus` (empirically live-verified in Phase 11's human-checkpoint task) + a plain `curl`/`grep` poll loop against `/api/v1/query` — no `jq` dependency (confirmed absent from this environment and unused anywhere else in the repo), no new script mechanism, no new library.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Scrape target discovery (which Services to scrape) | API / Backend (Kubernetes control plane — Prometheus Operator reconciler) | — | `ServiceMonitor` is a Kubernetes CRD reconciled by the Prometheus Operator running in the `observability` namespace; it is not application code and not a client-side concern |
| Scrape execution (`GET /metrics`) | API / Backend (Prometheus server, in-cluster) | — | Prometheus itself performs the scrape over the cluster network; field-guide-api/launchpad are passive scrape targets, already instrumented (Phase 1.0/1.1, `prometheus-flask-exporter`), unchanged this phase |
| Scrape health verification (`up == 1`) | API / Backend (Prometheus HTTP API `/api/v1/query`) | Developer CLI (`scripts/observability-up.sh` as the HTTP client) | The install script is the query client; Prometheus's own HTTP API is authoritative. No browser/UI component in this phase — that's Phase 15/16 |
| CRD existence guard | Developer CLI (`scripts/observability-up.sh` preflight) | — | Pure `kubectl get crd` check before applying dependent objects; mirrors Phase 11's D-10 preflight-and-abort style |
| Manifest storage/versioning | Database / Storage analog: git (`infra/observability/`) | — | Standalone YAML, not templated by either app chart — explicit architectural boundary from CONTEXT.md D-07 |

## User Constraints (from CONTEXT.md)

<user_constraints>
### Locked Decisions

**Apply Mechanism & Lifecycle**
- D-01: ServiceMonitors are applied by extending `scripts/observability-up.sh` — a new step after the stack is Running/Ready runs `kubectl apply -f` on the manifests. One lifecycle, one command; exactly what Phase 14's `make observability-up` success criterion expects. No separate apply script.
- D-02: Before applying, the script guards on CRD existence (`kubectl get crd servicemonitors.monitoring.coreos.com`) and aborts with an actionable message ("run scripts/observability-up.sh first" / stack-not-installed hint) if absent — matching the Phase 11 preflight style (11/D-10) and the project's actionable-error convention.
- D-03: If the v1.1 apps aren't deployed (no `field-guide-api` / `launchpad` Services), apply the ServiceMonitors anyway, print a warning ("apps not deployed — targets will appear after make up-all"), and skip the `up == 1` verification for the missing app(s). A ServiceMonitor with no matching Service is valid and harmless; install order stays flexible.
- D-04: `observability-down.sh` gets NO explicit ServiceMonitor delete step. Because the ServiceMonitors live in the `observability` namespace (D-06), the existing namespace deletion (11/D-02) sweeps them as a side effect — accepted. `observability-up.sh` re-applies them on every install, so the lifecycle is self-healing.

**Job Naming & Manifest Layout**
- D-05: Job names use the Service-name defaults — `up{job="field-guide-api"}` and `up{job="launchpad"}` — no jobLabel overrides, no relabeling. The Services are named after the Helm releases, which already match the ROADMAP success criteria and the queries Phases 13/15 will write.
- D-06: The ServiceMonitor objects live in the `observability` namespace (with the stack), using `spec.namespaceSelector` to target the `default` namespace where both app Services run. Phase 11 already set `serviceMonitorSelectorNilUsesHelmValues: false`, so no `release:` label is needed (pitfall 2 pre-solved).
- D-07: One manifest file per app: `infra/observability/servicemonitor-field-guide-api.yaml` and `infra/observability/servicemonitor-launchpad.yaml`. Mirrors the repo's one-concern-per-file style; Phase 13 adds `dashboards/` alongside.

**Scrape Tuning**
- D-08: Explicit `interval: 15s` on both ServiceMonitor endpoints. Snappiest for the Mission Control demo; Phase 13 PromQL rate windows must be ≥ 4x the interval, so 1m windows become available. Cost negligible for two small Flask targets on 24h emptyDir retention.
- D-09: All other scrape parameters stay default: `path` defaults to `/metrics`, endpoints target the Services' named `http` port, `scrapeTimeout` default 10s. Not pinned in YAML unless a default is actually overridden.

**Verification**
- D-10: `observability-up.sh` self-verifies scraping: after applying the ServiceMonitors, it polls the Prometheus HTTP API (`/api/v1/query?query=up{job=...}`) until both jobs return 1, aborting with an actionable message on timeout. Extends the 11/D-06 self-verification pattern — scrape health is proven on every install (skipped per-app when apps are absent, per D-03).
- D-11: In addition to the automated check, one plan task ends with a human checkpoint: operator opens the Prometheus Targets page via port-forward and confirms both scrape jobs show UP.
- D-12: The phase's certified end state is torn down — run the full up → verify `up == 1` → down lifecycle, matching Phase 11's convention. This also proves ServiceMonitor re-apply on reinstall works. Phase 13 starts from a clean slate with one `observability-up`.

### Claude's Discretion
- How the script reaches the Prometheus query API (port-forward vs in-cluster curl pod vs exec) and poll/timeout values for the `up == 1` wait.
- Exact wording of warnings/abort messages (follow the Phase 11 actionable-message style, name the fix).
- Whether `kubectl apply` targets the two files explicitly or a glob — as long as D-07's layout holds.
- Scrape-appearance patience: operator reconcile + first 15s scrape typically lands within ~30-60s; choose a poll timeout with sensible headroom.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope. (Pre-existing deferrals — Loki, Alertmanager, SLO panels — remain tracked in REQUIREMENTS.md Future Requirements.)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OBS-03 | Prometheus discovers and scrapes the existing `/metrics` of field-guide-api and launchpad via standalone ServiceMonitors in `infra/observability/` (zero changes to existing charts); both targets report `up == 1` | Confirms both Services' existing labels (`app.kubernetes.io/name`) and named `http` port are sufficient selectors (verified by direct read of `_helpers.tpl`/`service.yaml`); provides exact `ServiceMonitor` YAML for both apps; documents the CRD-guard and live-verification patterns for `observability-up.sh` extension |
</phase_requirements>

## Project Constraints (from CLAUDE.md)

- **Tech stack (LOCKED):** Python 3.11 + Flask backend; MongoDB; Docker; kind; local registry; Helm 3; monorepo — not touched by this phase (no app-chart or Python changes).
- **Security:** `.env` for local config, Kubernetes Secrets in-cluster; never commit real secrets — no secrets are introduced by this phase (ServiceMonitors carry no credentials).
- **Platform:** Windows host with WSL2/Git Bash — make targets and scripts must work in that environment. This phase's script extension MUST avoid `jq` (confirmed absent from this environment), avoid `kubectl wait`/watch-based waits (documented hang on this exact Windows/Docker-Desktop/kind setup per `docs/known-limitations.md`), and must be `MSYS_NO_PATHCONV=1`-safe for any argument resembling an absolute path (e.g. `/api/v1/query`, `/metrics`).
- **Git:** Many small human-style commits (lowercase, short messages) — applies to this phase's commits (manifests, script diff).
- **Autonomy:** Operate autonomously on routine implementation choices; this phase's CONTEXT.md already resolved all locked decisions (D-01..D-12) and leaves 4 explicit discretion areas, all addressed below.

## Standard Stack

No new libraries, packages, or CLI tools are introduced by this phase. It is exclusively:
1. Two new static YAML manifests (`ServiceMonitor` CRD instances) in `infra/observability/`.
2. An extension to the existing `scripts/observability-up.sh` (already-installed `kubectl`, `helm`, `bash`/`curl` — all present per Phase 11's prerequisite gate).

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| Prometheus Operator `ServiceMonitor` CRD | `monitoring.coreos.com/v1` (bundled with kube-prometheus-stack 87.16.1, already installed Phase 11) | Declares a scrape target by Service label selector | The exact, de-facto-standard integration point for adding scraping to a workload whose chart cannot be modified — already confirmed installed and reconciling in this cluster (Phase 11) |
| `kubectl` | already on PATH (Phase 11 prerequisite gate) | Apply manifests, run the CRD-existence guard, poll pod/Service state | No new tool; same binary used throughout `scripts/observability-up.sh` |
| `curl` | Git-Bash-bundled (already relied on by `make smoke`/`smoke-launchpad`) | Query the Prometheus HTTP API for the `up == 1` self-check | Already the project's only HTTP client in shell scripts — no new dependency |

### Supporting
None — this phase adds zero new supporting libraries.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `curl` + `grep`/plain string match for parsing the Prometheus JSON response | `jq` | `jq` is not installed in this environment (`command -v jq` fails) and is used nowhere else in the repo; requiring it would add an undocumented host dependency to a script whose entire design philosophy (per Phase 11's `to_ki()` helper and the prerequisite gate) is "check what's on PATH, degrade or fail loudly, never assume a tool beyond docker/kubectl/helm/bash" |
| Port-forward-based Prometheus query | In-cluster ephemeral curl pod (`kubectl run --rm -it curlpod --image=curlimages/curl -- curl ...`) | Ephemeral-pod image pulls add latency and a new external image dependency (`curlimages/curl` from Docker Hub) for a single query; port-forward reuses the exact pattern (`make smoke`'s background-port-forward + trap + curl) already proven reliable on this Windows/Docker-Desktop host, with zero new image pulls |
| Port-forward-based Prometheus query | `kubectl exec` into the Prometheus pod and curl `localhost:9090` from inside it | Prometheus's `quay.io/prometheus/prometheus` image is a minimal/distroless-style image with no shell/curl bundled by default — `kubectl exec ... curl` would fail; port-forward avoids depending on the target pod's own toolset entirely |

**Installation:** N/A — no new packages to install.

**Version verification:** N/A — no new packages/libraries introduced. The `ServiceMonitor` CRD's API version (`monitoring.coreos.com/v1`) is fixed by the already-pinned kube-prometheus-stack chart version 87.16.1 (Phase 11, `docs/known-limitations.md` confirms live install).

## Package Legitimacy Audit

Not applicable — this phase installs no new pip/npm/cargo packages, and pulls no new container images. The only new artifacts are two Kubernetes YAML manifests (no executable payload) and a diff to an existing bash script. The Package Legitimacy Gate is skipped per its own scope (external package installs only).

## Architecture Patterns

### System Architecture Diagram

```
scripts/observability-up.sh (extended this phase)
│
├─ Step 0 (Phase 11, unchanged): preflight capacity check
├─ Step 1 (Phase 11, unchanged): helm repo add/update
├─ Step 2 (Phase 11, unchanged): helm upgrade --install kube-prometheus-stack
├─ Step 3 (Phase 11, unchanged): poll observability pods Running/Ready
│
├─ Step 4 (NEW — D-02): CRD existence guard
│    kubectl get crd servicemonitors.monitoring.coreos.com
│         │
│         ├─ absent → print actionable abort message → exit 1
│         └─ present → continue
│
├─ Step 5 (NEW — D-01, D-07): kubectl apply -f the two ServiceMonitor manifests
│    infra/observability/servicemonitor-field-guide-api.yaml
│    infra/observability/servicemonitor-launchpad.yaml
│         │
│         ▼
│    Prometheus Operator (running since Phase 11, `observability` ns)
│         │  reconciles ServiceMonitor.spec.selector.matchLabels against
│         │  Service.metadata.labels in spec.namespaceSelector's namespace
│         ▼
│    Service field-guide-api (default ns) ──▶ Pod :8000/metrics
│    Service launchpad        (default ns) ──▶ Pod :8000/metrics
│         │
│         ▼  Prometheus scrapes both targets every 15s (D-08)
│    Prometheus TSDB (emptyDir, 24h retention — Phase 11)
│
├─ Step 6 (NEW — D-03): per-app presence check
│    kubectl -n default get svc field-guide-api / launchpad
│         │
│         ├─ Service absent → print warning, SKIP that app's up==1 check
│         └─ Service present → include in Step 7's verification set
│
├─ Step 7 (NEW — D-10): self-verify scraping
│    background: kubectl port-forward -n observability svc/kube-prometheus-stack-prometheus 9090:9090
│    trap: kill the port-forward PID on exit (mirrors `make smoke`)
│    poll loop (bounded deadline): curl -s "http://localhost:9090/api/v1/query?query=up{job=\"<app>\"}"
│         │
│         ├─ response contains `"value":[<ts>,"1"]` for every present app → PASS, continue
│         └─ deadline exceeded → print actionable abort message → exit 1
│
├─ Step 8 (Phase 11, renumbered): re-verify v1.1 apps (make smoke / smoke-launchpad) — UNCHANGED
│
└─ Human checkpoint (D-11, separate plan task, not in the script):
     operator port-forwards Prometheus, opens Targets page in a browser,
     visually confirms both jobs show state=UP
```

### Recommended Project Structure

```
infra/
└── observability/
    ├── values-trimmed.yaml                       # Phase 11, unchanged
    ├── servicemonitor-field-guide-api.yaml        # NEW (D-07)
    └── servicemonitor-launchpad.yaml               # NEW (D-07)
scripts/
├── observability-up.sh     # EXTENDED this phase (Steps 4-7 inserted, Step "4" renumbered "8")
└── observability-down.sh   # UNCHANGED (D-04 — no new step; namespace delete sweeps ServiceMonitors)
docs/
└── known-limitations.md    # optionally appended if the poll timeout / port-forward choice needs a documented accepted-risk note (pattern precedent, not mandatory this phase)
```

### Pattern 1: Standalone `ServiceMonitor` targeting an existing Service by label (no chart edits)

**What:** A `ServiceMonitor` is reconciled by the Prometheus Operator purely via `spec.selector.matchLabels` matched against `Service.metadata.labels`, plus `spec.namespaceSelector` to scope which namespace(s) are searched. Neither field requires the target Service or its owning chart to be aware the `ServiceMonitor` exists.

**When to use:** Exactly this project's situation — scraping a workload whose Helm chart is contractually frozen (ADDITIVE ONLY hard constraint).

**Verified against this repo's actual Service labels** (confirmed by direct read of `charts/field-guide-api/templates/_helpers.tpl` / `charts/launchpad/templates/_helpers.tpl` / both `service.yaml` files):

```yaml
# infra/observability/servicemonitor-field-guide-api.yaml
# Source: .planning/phases/12-servicemonitor-scraping/12-RESEARCH.md
# No `release:` label required — infra/observability/values-trimmed.yaml already sets
# prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues: false (Phase 11),
# so the Prometheus CR discovers ServiceMonitors cluster-wide regardless of label.
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: field-guide-api
  namespace: observability
spec:
  namespaceSelector:
    matchNames: ["default"]
  selector:
    matchLabels:
      app.kubernetes.io/name: field-guide-api
  endpoints:
    - port: http        # matches charts/field-guide-api/templates/service.yaml's `name: http`
      interval: 15s      # D-08 — explicit, all other params left at chart default (D-09)
```

```yaml
# infra/observability/servicemonitor-launchpad.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: launchpad
  namespace: observability
spec:
  namespaceSelector:
    matchNames: ["default"]
  selector:
    matchLabels:
      app.kubernetes.io/name: launchpad
  endpoints:
    - port: http
      interval: 15s
```

**Why `app.kubernetes.io/name` alone (no `app.kubernetes.io/instance`) is a safe selector here:** Both charts' `_helpers.tpl` selectorLabels helper stamps `app.kubernetes.io/name: field-guide-api` / `app.kubernetes.io/name: launchpad` distinctly per chart (confirmed: `field-guide-api.name` derives from `.Chart.Name`, i.e. `field-guide-api`; `launchpad.name` derives from `.Chart.Name`, i.e. `launchpad`) — there is no risk of the two Services' `name` labels colliding, and each chart's own mongodb sub-Service intentionally carries a *different* `app.kubernetes.io/name` (`field-guide-api-mongodb` / `launchpad-mongodb`) specifically to avoid selector collisions (documented in-repo in `_helpers.tpl`'s own comments). Matching on `name` alone is therefore sufficient and correctly excludes the MongoDB Services.

**Job name confirmation:** Neither manifest sets `spec.jobLabel`. Per Prometheus Operator's documented default behavior, when `jobLabel` is unset the `job` label on scraped metrics defaults to the **Service's `metadata.name`** — i.e. `field-guide-api` and `launchpad` respectively (both charts' `service.yaml` sets `metadata.name: {{ include "<chart>.fullname" . }}`, which collapses to the bare chart name because `RELEASE=field-guide-api` / `LP_RELEASE=launchpad` already contain the chart name — confirmed via the `fullname` helper's `contains $name .Release.Name` branch and the Makefile's `RELEASE ?= field-guide-api` / `LP_RELEASE ?= launchpad` defaults). This directly satisfies D-05's `up{job="field-guide-api"}` / `up{job="launchpad"}` expectation with zero relabeling. [CITED: Prometheus Operator community/GitHub issue #3033 discussion — MEDIUM-HIGH, cross-referenced against the official jobLabel field description]

### Pattern 2: CRD-existence guard before applying dependent objects (D-02)

**What:** Before `kubectl apply -f` on any `ServiceMonitor` manifest, confirm the CRD is actually installed — `kubectl apply` against an unknown `kind` fails with a generic `error: unable to recognize ... no matches for kind "ServiceMonitor"`, which is not actionable for an operator who hasn't run Phase 11 yet.

**Example (mirrors the existing prerequisite-gate style at the top of `observability-up.sh`):**

```bash
# ── Step 4: CRD existence guard (D-02) ───────────────────────────────────────
echo "==> Step 4: Verifying ServiceMonitor CRD is installed..."
if ! kubectl ${KCTX} get crd servicemonitors.monitoring.coreos.com >/dev/null 2>&1; then
  echo "ERROR: CRD servicemonitors.monitoring.coreos.com not found."
  echo "  ACTION: the observability stack install (Steps 0-3 above) must complete"
  echo "  successfully before ServiceMonitors can be applied — re-run this script"
  echo "  (bash scripts/observability-up.sh) from a clean state, or check"
  echo "  'kubectl ${KCTX} get pods -n observability' for a stuck install."
  exit 1
fi
echo "    CRD present — continuing."
```

Note: since this guard runs *after* Steps 0-3 of the same script (which install the chart that owns this CRD), in the normal one-command flow the guard should never actually fail — its value is defensive, for the case where a prior run partially failed, or the script is later refactored/called out of order. Keep the message actionable regardless.

### Pattern 3: Background port-forward + polling curl + trap cleanup, reused from `make smoke` (D-10)

**What:** This exact idiom already exists twice in the Makefile (`smoke`, `smoke-launchpad`) — start a `kubectl port-forward` in the background, capture its PID, `trap` a kill on exit, `sleep` briefly to let it bind, then loop `curl` against `localhost:<port>`. Bash scripts and Makefile recipes share the same shell (bash via `SHELL := /bin/bash` / `#!/usr/bin/env bash`), so the same idiom transfers directly into `observability-up.sh` without translation.

**Why port-forward over `kubectl exec` or an ephemeral curl pod:** See Alternatives Considered above — port-forward has zero new image-pull dependency and is the only approach already proven not to hang on this specific Windows/Docker-Desktop host (the `--wait`/watch-based-wait failure mode documented in `docs/known-limitations.md` is specific to *long-lived watch connections*; a `port-forward` + short-lived `curl` request pattern is architecturally different and is exactly what `make smoke`/`smoke-launchpad` already do successfully against this same host/proxy).

**Verified Service name for the port-forward target:** `svc/kube-prometheus-stack-prometheus`, port `9090`. [VERIFIED: in-repo, live-confirmed] — this exact Service name was used successfully in Phase 11's human-verify checkpoint (11-03-PLAN.md Task 2, approved per STATE.md: "UIs load ... admin login and anonymous Viewer access confirmed") and is printed by `observability-up.sh`'s own Step 4 completion message. This is the chart-managed frontend Service (`<release>-kube-prometheus-stack-prometheus`, release name `kube-prometheus-stack`), distinct from the operator-hardcoded `prometheus-operated` headless Service also present in the cluster — either works for this purpose; the chart-managed name is used here for consistency with the rest of `observability-up.sh`'s existing output and Phase 11's already-verified checkpoint.

**Example (extends `observability-up.sh`, no `jq` dependency):**

```bash
# ── Step 7: Self-verify scraping — up == 1 (D-10) ────────────────────────────
echo "==> Step 7: Verifying Prometheus is scraping the applied targets..."

# D-03: only verify apps that are actually deployed.
VERIFY_JOBS=""
for job in field-guide-api launchpad; do
  if kubectl ${KCTX} -n default get svc "$job" >/dev/null 2>&1; then
    VERIFY_JOBS="${VERIFY_JOBS} ${job}"
  else
    echo "    WARNING: Service '${job}' not found in namespace 'default' — apps not"
    echo "    deployed yet. ServiceMonitor applied anyway; skipping its up==1 check."
    echo "    Targets will appear after 'make up-all' (or the app-specific deploy target)."
  fi
done

if [ -z "$VERIFY_JOBS" ]; then
  echo "    No deployed apps to verify against — skipping scrape self-check entirely."
else
  if command -v pkill >/dev/null 2>&1; then
    pkill -f "kubectl port-forward -n ${NAMESPACE} svc/kube-prometheus-stack-prometheus" 2>/dev/null || true
  fi
  kubectl ${KCTX} port-forward -n "${NAMESPACE}" svc/kube-prometheus-stack-prometheus 9090:9090 &>/dev/null &
  PF_PID=$!
  trap "kill ${PF_PID} 2>/dev/null || true" EXIT
  sleep 3   # let the port-forward bind, mirrors make smoke's sleep 3

  # Headroom: operator reconcile + first 15s scrape typically lands within 30-60s
  # (per CONTEXT.md D-12 discretion note). 150s deadline gives ~2.5x that ceiling
  # to absorb a cold Prometheus config reload on a freshly-applied ServiceMonitor.
  DEADLINE=$(( $(date +%s) + 150 ))
  for job in $VERIFY_JOBS; do
    echo "    Waiting for up{job=\"${job}\"} == 1..."
    while true; do
      RESPONSE=$(curl -s "http://localhost:9090/api/v1/query" --data-urlencode "query=up{job=\"${job}\"}")
      if echo "$RESPONSE" | grep -qE '"value":\[[0-9.]+,"1"\]'; then
        echo "      PASS  up{job=\"${job}\"} == 1"
        break
      fi
      if [ "$(date +%s)" -ge "$DEADLINE" ]; then
        echo "ERROR: up{job=\"${job}\"} did not reach 1 within 150s."
        echo "  Last response: ${RESPONSE}"
        echo "  ACTION: check 'kubectl ${KCTX} -n ${NAMESPACE} port-forward svc/kube-prometheus-stack-prometheus 9090:9090'"
        echo "  and open http://localhost:9090/targets — look for job=\"${job}\" and its error reason."
        exit 1
      fi
      sleep 5
    done
  done
fi
```

**Note on `curl --data-urlencode`:** Using `--data-urlencode` (which forces a POST unless combined with `-G`) or `-G --data-urlencode` for the query string is safer than hand-splicing `{}`/`"` characters into a URL under Git Bash — avoids any MSYS quoting surprises with the `{job="..."}` PromQL label-matcher syntax. Use `curl -s -G "http://localhost:9090/api/v1/query" --data-urlencode "query=up{job=\"${job}\"}"` (the `-G` flag ensures `--data-urlencode` builds a GET query string, matching the Prometheus HTTP API's documented GET support for `/api/v1/query`). [CITED: Prometheus HTTP API official docs — `/api/v1/query` supports both GET and POST]

### Anti-Patterns to Avoid

- **Adding a `release: kube-prometheus-stack` label "just to be safe":** Unnecessary and slightly misleading — `values-trimmed.yaml` already sets `serviceMonitorSelectorNilUsesHelmValues: false`, so the label plays no role in discovery here. Adding it anyway doesn't break anything, but it implies a coupling to the Helm release name that doesn't actually exist in this configuration, and a future reader could incorrectly assume it's load-bearing. Leave it off per D-06's stated rationale.
- **Verifying only with `kubectl get servicemonitor`:** This confirms the Kubernetes object was created, not that Prometheus discovered it or that the scrape is succeeding — exactly Pitfall 2 from the v2.0 PITFALLS.md research ("fails silently, not loudly"). D-10/D-11 already mandate the live `up{job=...}` query as the real gate; do not treat `kubectl apply` success as sufficient.
- **Using `kubectl wait` or `helm --wait`-style long-lived watch connections for the up==1 poll:** Already documented as hanging indefinitely on this Windows/Docker-Desktop/kind host (`docs/known-limitations.md`, Phase 11). Use plain polling `curl` in a `while` loop with a `sleep`, exactly as Pattern 3 above and the existing Step 3 pod-readiness check already do.
- **Deleting ServiceMonitors explicitly in `observability-down.sh`:** Explicitly rejected by D-04 — the namespace delete already sweeps them, and adding a redundant delete step both violates "don't touch what D-04 already covers" and risks a race if the delete runs before the namespace delete (harmless either way, but adds a maintenance surface for no benefit).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|--------------|-----|
| Discovering scrape targets by label | A custom controller/sidecar watching Services and generating static Prometheus scrape_configs | The `ServiceMonitor` CRD (already installed, Phase 11) | This is exactly the problem the Prometheus Operator exists to solve; hand-rolling target discovery would mean re-implementing Kubernetes watch/reconcile logic that's already battle-tested |
| Parsing a Prometheus instant-query JSON response | A bespoke JSON parser in bash | `grep -qE '"value":\[[0-9.]+,"1"\]'` (string-shape match) on the known, stable Prometheus HTTP API v1 response schema | The schema is small, stable, and documented; a full JSON parser (`jq`) isn't installed in this environment and isn't needed for a single boolean "did the value become 1" check — over-engineering for the actual requirement |
| Waiting for eventual consistency (operator reconcile + first scrape) | A fixed `sleep N` with no verification | The bounded poll loop (Pattern 3) | A fixed sleep either wastes time (if scraping succeeds early) or silently under-waits (if it's slow) — a poll loop with a generous deadline and an explicit PASS/FAIL is the same discipline already used for Step 3's pod-readiness check in this same script |

**Key insight:** Every mechanism this phase needs (CRD guard, background port-forward + trap, polling loop, actionable abort messages) already exists somewhere in this repository (`observability-up.sh` Steps 0/3, `Makefile`'s `smoke`/`smoke-launchpad`). The entire task is composition and light editing, not new design — treat any solution that introduces a genuinely new pattern (a new Python script, a new CLI tool, a templating layer for the two nearly-identical manifests) as over-engineering relative to what CONTEXT.md's decisions actually require.

## Common Pitfalls

### Pitfall 1: Selector mismatch — Prometheus discovers zero targets silently

**What goes wrong:** A `ServiceMonitor` is created and `kubectl get servicemonitor` shows it exists, but Prometheus's Service Discovery/Targets page shows nothing for it — no error anywhere.

**Why it happens:** Two independent selector layers must both match: (1) `spec.selector.matchLabels` against the target Service's labels, and (2) `spec.namespaceSelector` against the namespace the Service actually lives in. Getting either wrong produces silent zero-target discovery, not an error.

**How to avoid:** Use the exact label/namespace values confirmed by direct in-repo read in this document (Pattern 1 above) — `app.kubernetes.io/name: field-guide-api` / `launchpad`, `namespaceSelector.matchNames: ["default"]`. Do not guess or copy from a generic example. Verify with the live `up{job=...}` query (D-10/D-11), never with object-creation success alone.

**Warning signs:** `kubectl get servicemonitors -n observability` shows both objects; Prometheus's `/targets` page or the `up{job=...}` query shows nothing for one or both jobs.

**Already mitigated by this phase's design:** Because `serviceMonitorSelectorNilUsesHelmValues: false` was already set in Phase 11, the most commonly-cited version of this pitfall (missing `release:` label) cannot occur here — only the Service-label and namespace layers remain as real risk, both of which are pinned to verified in-repo values above.

### Pitfall 2: CRD not yet installed when `kubectl apply` runs

**What goes wrong:** `kubectl apply -f servicemonitor-*.yaml` fails with `error: unable to recognize "...": no matches for kind "ServiceMonitor" in version "monitoring.coreos.com/v1"` if run before the chart (and its bundled CRDs) has finished installing.

**Why it happens:** CRDs installed via a chart's `crds/` directory are available asynchronously relative to `helm upgrade --install` returning — this is Pitfall 8 from the broader v2.0 PITFALLS.md research, one layer of which (CRD-not-yet-present) is directly relevant here.

**How to avoid:** D-02's explicit CRD-existence guard (Pattern 2 above), placed after Step 3's pod-readiness wait (by which point the CRDs are certainly installed, since the pods that reconcile them are already Running).

**Warning signs:** `kubectl apply` output literally contains `no matches for kind`.

### Pitfall 3: `curl`'s PromQL query string mangled by MSYS/Git-Bash path conversion or shell quoting

**What goes wrong:** PromQL label matchers use `{job="..."}` syntax containing characters (`{`, `}`, `"`) that can interact badly with Git Bash's argument handling, and any argument that looks like a POSIX absolute path (starting with `/`) risks MSYS auto-conversion to a Windows path — a documented class of pitfall for this exact host/shell combination (`docs/known-limitations.md`, Phase 11 already sets `MSYS_NO_PATHCONV=1` at the top of both observability scripts for this reason).

**How to avoid:** Use `curl -G --data-urlencode "query=up{job=\"${job}\"}"` (Pattern 3) rather than hand-building a URL with the raw PromQL string spliced in — `--data-urlencode` percent-encodes the special characters, sidestepping shell-quoting and MSYS path-mangling risk simultaneously. `MSYS_NO_PATHCONV=1` is already exported at the top of `observability-up.sh` and covers the `/api/v1/query` path segment.

**Warning signs:** `curl` returns a 400 from Prometheus, or the query string in a verbose `curl -v` trace looks visibly mangled (unexpected backslashes, drive-letter prefixes).

### Pitfall 4: Treating a `0` value or empty `result` array as "still warming up" indefinitely

**What goes wrong:** A poll loop that only checks "did curl succeed" (HTTP 200) rather than inspecting the actual PromQL result will falsely PASS even when the target is genuinely down (`up{job="field-guide-api"} == 0`) or not yet discovered (`"result":[]`) — Prometheus's `/api/v1/query` returns HTTP 200 with a `"status":"success"` envelope in both of those cases; the failure signal is in the *body*, not the status code.

**How to avoid:** The grep pattern in Pattern 3 (`'"value":\[[0-9.]+,"1"\]'`) specifically requires the numeric value `1`, not just a `200` response or a non-empty body — this correctly distinguishes "up and scraping" from "target exists but down" or "not discovered yet."

**Warning signs:** The self-check script reports PASS immediately even when `kubectl get pods -n default` shows field-guide-api/launchpad pods aren't actually Running, or when manually curling the same endpoint shows `"value":[<ts>,"0"]`.

## Code Examples

See the full `ServiceMonitor` manifests and script step diffs under **Architecture Patterns** above — those are the verified, ready-to-use code for this phase (not illustrative snippets).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|-------------------|---------------|--------|
| ServiceMonitor requiring a `release: <helm-release-name>` label to be discovered (`serviceMonitorSelectorNilUsesHelmValues: true`, chart default) | `serviceMonitorSelectorNilUsesHelmValues: false` — discover all ServiceMonitors cluster-wide regardless of label | Set in this project's Phase 11 (`values-trimmed.yaml`), not a chart-wide upstream default change | Removes the single most commonly-cited kube-prometheus-stack footgun (Pitfall 2) for this specific single-tenant local cluster; standalone manifests in this phase need no `release:` label |

**Deprecated/outdated:** None specific to this phase — the Prometheus Operator's `ServiceMonitor` CRD and default job-labeling behavior are stable, unchanged APIs (`monitoring.coreos.com/v1`).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|----------------|
| A1 | Default `job` label (unset `jobLabel`) resolves to the Service's `metadata.name`, not the ServiceMonitor's own `metadata.name` | Pattern 1 — Job name confirmation | If wrong, `up{job="field-guide-api"}` would return no series even with correct scraping, and the poll loop would time out; the CONTEXT.md D-05 decision already assumes this behavior, so this is a shared assumption, not new risk introduced here. Confidence is MEDIUM-HIGH (community/GitHub-issue corroborated, not pulled from the official Prometheus Operator API reference page directly in this research pass) — recommend a quick live spot-check (`curl .../api/v1/query?query=up` with no job filter, inspect the `job` label on returned series) as the very first verification step in implementation, before trusting the filtered queries |

**If this table is empty:** N/A — see A1 above; all other claims in this research are either `[VERIFIED: in-repo]` (Service labels, port names, chart names, Makefile RELEASE variables, the `kube-prometheus-stack-prometheus` Service name from Phase 11's own checkpoint) or `[CITED: official Prometheus HTTP API docs]` (query endpoint shape, already cited HIGH confidence in the existing v2.0 ARCHITECTURE.md).

## Open Questions (RESOLVED)

1. **Does the operator's reconcile-to-first-successful-scrape latency ever exceed 150s on this specific host under load (e.g. immediately after the Step 3 pod-readiness wait, when the node may still be under I/O pressure from the fresh install)?**
   - What we know: CONTEXT.md's own discretion note estimates ~30-60s typical; Prometheus's global `scrape_interval`/`evaluation_interval` and the ServiceMonitor's own `interval: 15s` bound the *steady-state* cadence, but the *first* reconcile-to-scrape latency after a fresh `kubectl apply` is not something this research measured live.
   - What's unclear: Whether 150s (the deadline chosen in Pattern 3, ~2.5x the estimated ceiling) is generous enough on a Windows/Docker-Desktop host that has already shown one confirmed proxy-related timing quirk (`--wait` hangs, per `docs/known-limitations.md`).
   - Recommendation: Treat 150s as a starting point (matches this phase's discretion-area guidance to "choose a poll timeout with sensible headroom"), and if the live plan-execution run times out, raise it rather than treating a single timeout as a design failure — this mirrors how Phase 11's own resource numbers were explicitly flagged as "starting point, not final answer" and then live-tuned.
   - **RESOLVED (planning, 2026-07-18):** Handled by the contingency designed into 12-02 Task 1 — on a Step 7 timeout, first spot-check unfiltered `up` to validate the A1 job-label assumption (flag a jobLabel finding for a 12-01 revision if wrong), otherwise raise the Step 7 deadline in `scripts/observability-up.sh` as a tuning change (12-02 lists the script as a conditional `files_modified` entry for exactly this branch). 150s stands as the starting value.

2. **Is `port: http` in `spec.endpoints` guaranteed to resolve correctly given both Services use the identical port name `http`, or could Prometheus's Operator conflate the two when both ServiceMonitors exist simultaneously in the same `observability` namespace?**
   - What we know: Each `ServiceMonitor` has its own independent `spec.selector.matchLabels`, so `field-guide-api`'s ServiceMonitor only ever matches the `field-guide-api` Service (via `app.kubernetes.io/name`), never `launchpad`'s Service, regardless of both using the same port *name*. Port names are resolved per-matched-Service, not globally.
   - What's unclear: Nothing substantive — this is a common early doubt but not a real ambiguity given the Operator's per-object reconciliation model. Included here for completeness/transparency, not because it's a genuine risk.
   - Recommendation: No action needed; confidence is HIGH this is a non-issue, included only so the planner doesn't need to re-derive this reasoning independently.
   - **RESOLVED (planning, 2026-07-18):** Confirmed a non-issue — each ServiceMonitor's independent `spec.selector.matchLabels` scopes port-name resolution per matched Service; both manifests may share `port: http` safely. No plan action needed.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| `kubectl` | CRD guard, apply, port-forward, presence checks | ✓ (Phase 11 prerequisite gate) | Whatever Phase 11 already confirmed | — |
| `helm` | Not directly used by this phase's new steps (only Steps 0-3, unchanged) | ✓ (Phase 11) | 3.21.2 (locked, CLAUDE.md) | — |
| `curl` | Prometheus HTTP API self-check | ✓ (Git Bash bundled; already used by `make smoke`/`smoke-launchpad`) | Git-Bash-bundled | — |
| `jq` | Not used — deliberately avoided | ✗ (confirmed absent: `command -v jq` fails) | — | `grep -qE` pattern match on the known-stable Prometheus JSON response shape (Pattern 3) — no fallback needed because the dependency was avoided by design |
| `pkill` | Stale port-forward cleanup before Step 7's own port-forward | Unconfirmed on stock Git Bash (Makefile's own `smoke` target already has a documented fallback: `command -v pkill` guard, printed note, continue without cleanup) | — | Mirror the exact same `command -v pkill` guard already present in `smoke`/`smoke-launchpad` — no new fallback logic needed, reuse the existing one |
| `servicemonitors.monitoring.coreos.com` CRD | Applying the two manifests | ✓ if Phase 11 install succeeded (Steps 0-3 of the same script run first) | Bundled with kube-prometheus-stack 87.16.1 | D-02's guard aborts with an actionable message if somehow absent |

**Missing dependencies with no fallback:** None.

**Missing dependencies with fallback:** `jq` (avoided by design, not needed); `pkill` (existing Makefile fallback pattern reused as-is).

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|----------------|---------|--------------------|
| V2 Authentication | No | This phase adds no new authenticated surface — Prometheus's HTTP API is queried only from an already-trusted local port-forward, exactly like the existing Prometheus/Grafana UI access pattern (`docs/known-limitations.md`, "Port-Forward Only — No Ingress or TLS") |
| V3 Session Management | No | No sessions introduced |
| V4 Access Control | No | `ServiceMonitor`'s `namespaceSelector`/`selector` fields are a scrape-scoping mechanism, not an access-control boundary in the ASVS sense — no new RBAC surface is introduced (the two manifests carry no `ServiceAccount`/`Role` changes) |
| V5 Input Validation | Yes | All PromQL strings in this phase are fixed, code-defined constants (`up{job="field-guide-api"}`, `up{job="launchpad"}`) — never built by concatenating any user-controlled input. `curl -G --data-urlencode` further ensures no shell-injection or PromQL-injection vector exists even for these fixed strings |
| V6 Cryptography | No | In-cluster HTTP (cleartext) to Prometheus's `/api/v1/query` is the existing, already-documented accepted-risk pattern for this local-only kind cluster (no TLS anywhere in this platform's current scope, per `docs/known-limitations.md`) — this phase introduces no new cryptographic surface and does not change that posture |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|-----------------------|
| Overly broad `namespaceSelector` (e.g. `{}` matching all namespaces) accidentally scraping unintended Services in future namespaces | Information Disclosure | `namespaceSelector.matchNames: ["default"]` is explicit and narrow (D-06) — scoped to exactly the one namespace both apps currently deploy into, not a wildcard |
| PromQL injection via string-concatenated user input | Tampering | Not applicable this phase — no user input reaches any PromQL string; all queries are fixed constants. Documented here as a forward-looking note for Phase 15 (native metric cards), which the existing v2.0 PITFALLS.md research already flags under Security Mistakes |
| A stray `ServiceMonitor` left applied after the app it targets is removed | Information Disclosure (minor) / none in practice | D-03 explicitly accepts this as harmless ("A ServiceMonitor with no matching Service is valid and harmless") — a ServiceMonitor with zero matched Services simply produces zero scraped series, no error, no data exposure |

## Sources

### Primary (HIGH confidence)
- In-repo: `charts/field-guide-api/templates/service.yaml`, `charts/field-guide-api/templates/_helpers.tpl`, `charts/launchpad/templates/service.yaml`, `charts/launchpad/templates/_helpers.tpl` — confirms exact Service labels (`app.kubernetes.io/name: field-guide-api` / `launchpad`) and named `http` port; direct read, this session
- In-repo: `charts/field-guide-api/Chart.yaml`, `charts/launchpad/Chart.yaml` — confirms chart `name:` fields backing the `.name`/`.fullname` helper outputs; direct read, this session
- In-repo: `Makefile` (lines 1-19, 68-92, 116-140ish) — confirms `RELEASE ?= field-guide-api`, `LP_RELEASE ?= launchpad`, and the exact background-port-forward + trap + curl-loop idiom (`smoke`, `smoke-launchpad` targets) this phase's Pattern 3 reuses; direct read, this session
- In-repo: `scripts/observability-up.sh`, `scripts/observability-down.sh` — confirms existing step structure, `MSYS_NO_PATHCONV=1` convention, `KCTX`/`NAMESPACE` variables, and the documented reason `kubectl wait`/watch-based waits are avoided on this host; direct read, this session
- In-repo: `infra/observability/values-trimmed.yaml` — confirms `serviceMonitorSelectorNilUsesHelmValues: false` is already live (Phase 11), eliminating the `release:` label requirement for this phase's manifests; direct read, this session
- In-repo: `docs/known-limitations.md` — confirms the live-verified Service name `kube-prometheus-stack-prometheus`:9090 (used successfully in Phase 11's approved human checkpoint), the `helm --wait`/watch-hang finding, and the committed accepted-risk documentation convention this phase should follow if any new accepted risk surfaces; direct read, this session
- `.planning/research/ARCHITECTURE.md`, `.planning/research/PITFALLS.md`, `.planning/research/STACK.md` (v2.0 milestone research, dated 2026-07-16) — Pattern 1 (out-of-chart ServiceMonitor), Pitfall 2 (selector mismatch/silent zero-target discovery), CRD smoke-check convention; already HIGH-confidence per that research's own sourcing (prometheus-community/helm-charts GitHub issues, official Prometheus Operator troubleshooting docs)

### Secondary (MEDIUM confidence)
- [prometheus-operator/prometheus-operator issue #3033 — "How to get the original job tag?"](https://github.com/coreos/prometheus-operator/issues/3033) — confirms unset `jobLabel` defaults the `job` metric label to the Service's `metadata.name` (A1 in Assumptions Log; not independently re-verified against the primary API reference doc in this research pass, hence MEDIUM-HIGH rather than HIGH)
- [Prometheus HTTP API official docs](https://prometheus.io/docs/prometheus/latest/querying/api/) — `/api/v1/query` GET/POST support and response envelope shape (already cited HIGH confidence in the existing v2.0 ARCHITECTURE.md research; not re-fetched this session, carried forward)

### Tertiary (LOW confidence)
None used — this phase's scope was narrow enough that in-repo verification plus the already-HIGH-confidence v2.0 milestone research covered every claim except A1, which is flagged MEDIUM-HIGH above rather than treated as settled fact.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all tools already confirmed present by Phase 11
- Architecture: HIGH — every selector/label/port value verified by direct in-repo read, not assumed from a template
- Pitfalls: HIGH — Pitfall 2 (selector mismatch) directly sourced from the already-HIGH-confidence v2.0 PITFALLS.md; CRD-guard and MSYS-quoting pitfalls verified against this repo's own documented history (`docs/known-limitations.md`)

**Research date:** 2026-07-18
**Valid until:** 30 days (stable domain — Prometheus Operator CRD behavior and this repo's chart/label conventions are not fast-moving; re-verify only if Phase 11's `values-trimmed.yaml` or either app chart's labels change)

---
*Phase: 12-ServiceMonitor Scraping*
*Researched: 2026-07-18*
