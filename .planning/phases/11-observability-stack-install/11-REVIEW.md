---
phase: 11-observability-stack-install
reviewed: 2026-07-16T12:12:22Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - docs/known-limitations.md
  - infra/observability/values-trimmed.yaml
  - scripts/observability-down.sh
  - scripts/observability-up.sh
findings:
  critical: 0
  warning: 5
  info: 5
  total: 10
status: issues_found
---

# Phase 11: Code Review Report

**Reviewed:** 2026-07-16T12:12:22Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed the trimmed kube-prometheus-stack values file, the idempotent install/teardown
bash scripts, and the known-limitations documentation added in Phase 11. The accepted
decisions (D-01 CRD retention, D-07 dev Grafana password, D-08 anonymous viewer) match
their documentation and are not re-flagged.

Five warnings were found. The most significant: (1) the kube-state-metrics resource
bounds in `values-trimmed.yaml` are placed under the wrong key and are silently ignored
by the chart — the project's own live measurement in `docs/known-limitations.md`
confirms the pod runs BestEffort, contradicting the file's header claim; (2) the
teardown script uses `kubectl delete namespace` with its default watch-based `--wait`,
the exact mechanism the project itself live-verified as hanging indefinitely on this
Windows/Docker Desktop environment; (3) the install script's readiness self-check has a
race that can declare success before the operator has even created the Prometheus pod.

No critical (security / data-loss / crash) issues found. The committed passwords are
documented accepted local-dev decisions.

## Warnings

### WR-01: kube-state-metrics resource bounds set under the wrong values key — silently ignored

**File:** `infra/observability/values-trimmed.yaml:24-28`
**Issue:** In kube-prometheus-stack, `kubeStateMetrics.enabled` is only the subchart
*condition* flag. Values passed *to* the kube-state-metrics subchart (including
`resources`) must live under the subchart's dependency key `kube-state-metrics:`
(with dashes). As written, `kubeStateMetrics.resources` is not consumed by any
template, so the kube-state-metrics pod runs with no requests/limits. This is
corroborated by the project's own live measurement in
`docs/known-limitations.md:109-110` ("kube-state-metrics ... run without an explicit
memory request, i.e. BestEffort") — the observed behavior proves the values were
dropped. The file header (`values-trimmed.yaml:3`, "sets explicit bounded resources on
every kept-enabled component") is therefore false, and the preflight budget in
`scripts/observability-up.sh:21-22` counts 32Mi that is never actually requested.
**Fix:**
```yaml
kubeStateMetrics:
  enabled: true           # condition flag only

kube-state-metrics:       # subchart values key
  resources:
    requests: { cpu: 10m, memory: 32Mi }
    limits: { cpu: 50m, memory: 64Mi }
```
Then update the header comment and the known-limitations measurement note once the
bound actually applies (measured requests become ~516Mi, matching the preflight sum).

### WR-02: Teardown uses default watch-based `kubectl delete --wait` — the exact wait mechanism live-verified to hang on this environment

**File:** `scripts/observability-down.sh:38`
**Issue:** `kubectl delete namespace observability --ignore-not-found` runs with the
default `--wait=true`, which blocks on a **watch-based** waiter until the namespace
finishes finalizing. `docs/known-limitations.md:116-130` documents (live-reproduced
twice) that watch-based waits hang indefinitely on this Windows + Docker Desktop + kind
setup, which is precisely why `observability-up.sh` Step 3 was rewritten to use polling
`kubectl get` instead of `kubectl wait`. Namespace deletion always takes at least a few
seconds (finalizers), so the initial list will show it still Terminating and the waiter
will depend on watch events that this environment does not deliver — the teardown
script is likely to hang indefinitely at this line on the primary supported platform.
**Fix:**
```bash
kubectl "${KCTX}" delete namespace observability --ignore-not-found --wait=false
# Poll (no watch) until the namespace is gone, bounded deadline — mirrors up.sh Step 3
NS_DEADLINE=$(( $(date +%s) + 120 ))
while kubectl "${KCTX}" get namespace observability >/dev/null 2>&1; do
  if [ "$(date +%s)" -ge "$NS_DEADLINE" ]; then
    echo "ERROR: namespace observability still terminating after 120s."
    exit 1
  fi
  sleep 5
done
```

### WR-03: Readiness self-check can pass before the Prometheus pod exists (race)

**File:** `scripts/observability-up.sh:105-124`
**Issue:** The Step 3 loop succeeds as soon as `POD_COUNT -gt 0` and every *currently
existing* pod is Running/Ready. But the Prometheus pod
(`prometheus-kube-prometheus-stack-prometheus-0`) is not created by `helm install` — it
is created later by the operator after the operator pod starts and reconciles the
`Prometheus` CR. There is a window where grafana, kube-state-metrics, and the operator
are all Ready while the Prometheus StatefulSet pod has not yet been created; the check
then reports "All 3 observability pod(s) Running/Ready" and Step 4 declares success
with the core component of the stack absent. This defeats the D-06 self-verification
the step exists to provide.
**Fix:** Assert the expected component set, not just "some pods". For this trimmed
stack the steady state is 4 pods (operator, grafana, kube-state-metrics, prometheus):
```bash
EXPECTED_PODS=4
if [ "$POD_COUNT" -ge "$EXPECTED_PODS" ] && [ -z "$NOT_READY" ]; then
```
or explicitly require the operator-created pod before accepting readiness:
```bash
kubectl ${KCTX} get pod -n "${NAMESPACE}" -l app.kubernetes.io/name=prometheus --no-headers 2>/dev/null | grep -q . || continue-waiting
```

### WR-04: `to_ki` misses Kubernetes' lowercase `k` suffix; `*K` branch is dead code

**File:** `scripts/observability-up.sh:39-52`
**Issue:** Kubernetes quantity serialization uses **lowercase `k`** for decimal kilo
(suffixes are `k, M, G, T, P, E` — only kilo is lowercase). The `*K)` branch at line 46
can never match real API output, while a real `128k` value falls through to
`*[!0-9]*)` and is counted as **0**, silently under-counting existing requests and
inflating the computed headroom — the preflight gate (D-10) can then pass on a cluster
that does not actually have room. Same for milli-quantities (`1500m`), which the API
can emit for sub-byte-granularity requests. Low likelihood (most manifests use Mi/Gi),
but it is a logic error in the exact function the safety gate depends on.
**Fix:**
```bash
    *k)  echo $(( ${val%k} * 1000 / 1024 )) ;;
    *m)  echo $(( ${val%m} / 1000 / 1024 )) ;;   # millibytes -> Ki (floor)
```
and delete the unreachable `*K)` branch (or keep both `*K|*k`).

### WR-05: Documented CRD "full reset" command likely deletes nothing

**File:** `docs/known-limitations.md:94`
**Issue:** The documented manual cleanup
`kubectl delete crd -l app.kubernetes.io/part-of=kube-prometheus-stack` relies on the
CRDs carrying that label. But — as the same section correctly explains — these CRDs are
installed via Helm's `crds/` directory mechanism, i.e. verbatim upstream
prometheus-operator manifests, which carry `operator.prometheus.io/*` annotations but
no `app.kubernetes.io/part-of` label. The label selector will match zero CRDs and the
command exits 0 having deleted nothing, so a user following the "full reset"
instruction silently gets no reset. (kube-prometheus-stack's own README documents
name-based CRD deletion for this reason.)
**Fix:** Use name-based deletion:
```bash
kubectl get crd -o name | grep 'monitoring\.coreos\.com' | xargs -r kubectl delete
```
or verify the label actually exists on chart 87.16.1's CRDs before shipping the
label-selector form.

## Info

### IN-01: Scripts and docs reference `make observability-up` / `make observability-down`, which do not exist yet

**File:** `scripts/observability-up.sh:9`, `scripts/observability-down.sh:7`, `docs/known-limitations.md:85`
**Issue:** The Makefile contains no `observability-*` targets (they are planned for
Phase 14 per ROADMAP.md). The script usage headers and the known-limitations page
present `make observability-down` as a currently available command; running it today
fails with "No rule to make target". Forward reference is acceptable if intentional,
but the docs should not present it as current until Phase 14 lands.
**Fix:** Either add a "(Phase 14)" qualifier next to the `make` invocations, or lead
with the `bash scripts/...` form as the canonical command until Phase 14.

### IN-02: Preflight sums requests cluster-wide but compares against a single node's allocatable; init containers excluded

**File:** `scripts/observability-up.sh:56,63-64`
**Issue:** `.items[0].status.allocatable.memory` assumes a single-node cluster, while
the request sum spans all pods on all nodes; on a multi-node kind config the headroom
math is wrong. The jsonpath also iterates only `.spec.containers`, ignoring
`initContainers` (a pod's effective request is `max(init, sum(containers))`). Fine for
the current single-node kind cluster; will silently mislead if the cluster config grows.
**Fix:** Add a comment stating the single-node assumption, or sum allocatable across
nodes: `-o jsonpath='{range .items[*]}{.status.allocatable.memory}{"\n"}{end}'` and
accumulate with `to_ki`.

### IN-03: Timeout diagnostics skip Running-but-not-Ready pods

**File:** `scripts/observability-up.sh:119-120`
**Issue:** On timeout, the `describe` pass filters with
`status.phase!=Running,status.phase!=Succeeded` — but the most common not-Ready failure
mode is a **Running** pod with a failing readiness probe, which this filter excludes.
The operator would time out "describing not-ready pods" while describing none of them.
**Fix:** Describe from the `$NOT_READY` list already computed (first field is the pod
name): `printf '%s\n' "$NOT_READY" | awk '{print $1}' | xargs -r -n1 kubectl ${KCTX} describe pod -n "${NAMESPACE}"`.

### IN-04: `defaultRules.create: false` also disables recording rules that the still-enabled default Grafana dashboards consume

**File:** `infra/observability/values-trimmed.yaml:21-22`
**Issue:** The comment justifies disabling `defaultRules` purely as "no Alertmanager
consumer", but `defaultRules` also creates the **recording rules** (e.g.
`node_namespace_pod_container:*`, `cluster:*` series) that the chart's bundled Grafana
dashboards (enabled by default via `grafana.defaultDashboardsEnabled`) query. Those
dashboards will render "No data" panels. Not a defect for Phase 13's custom dashboards,
but the stated rationale is incomplete and the resulting empty built-in dashboards will
look like a scrape failure during demos.
**Fix:** Either note the trade-off in the comment, or disable the bundled dashboards
too (`grafana.defaultDashboardsEnabled: false`) so only intentional dashboards appear.

### IN-05: Both scripts assume repo-root CWD with no guard

**File:** `scripts/observability-up.sh:96,128-129`, `scripts/observability-down.sh:45-46`
**Issue:** The relative values path (`-f infra/observability/values-trimmed.yaml`) and
the `make smoke` / `make smoke-launchpad` calls only work when invoked from the repo
root. Invoked from elsewhere, up.sh fails midway (after mutating helm repo state) with
a "file not found" from Helm.
**Fix:** Anchor at the top of both scripts:
```bash
cd "$(dirname "${BASH_SOURCE[0]}")/.."
```

---

_Reviewed: 2026-07-16T12:12:22Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
