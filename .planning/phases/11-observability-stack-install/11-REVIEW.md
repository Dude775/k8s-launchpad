---
phase: 11-observability-stack-install
reviewed: 2026-07-16T16:20:51Z
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
  info: 3
  total: 8
status: issues_found
---

# Phase 11: Code Review Report (Re-Review After WR-01 Gap Closure)

**Reviewed:** 2026-07-16T16:20:51Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Narrative Findings (AI reviewer)

_No structural findings block was provided for this review; all findings below are narrative._

## Summary

Re-review of the four Phase 11 files after the plan 11-04 gap closure. **The prior WR-01 fix is verified correct:** `infra/observability/values-trimmed.yaml:37-40` now places the kube-state-metrics `resources` block under the top-level hyphenated `kube-state-metrics:` subchart values key, with the camelCase `kubeStateMetrics:` key retained only as the enablement condition flag. This was verified statically against the pinned chart itself (`helm show values prometheus-community/kube-prometheus-stack --version 87.16.1` confirms `kubeStateMetrics:` at values line 2648 is condition-only and `kube-state-metrics:` at line 2653 is the subchart pass-through key). The observability stack is currently torn down (no pods in the `observability` namespace), so the live 32Mi/10m Burstable-QoS confirmation from plan 11-04 could not be re-run, but the values placement is provably correct.

The fresh review found no Critical issues. It did find five Warnings: a **live-confirmed no-op** in the documented CRD cleanup command (the label selector matches zero CRDs on the actual cluster), a documented Grafana-password override command that silently breaks the D-05 chart version pin, an error-swallowing `helm status` guard in the teardown script that reproduces the exact failure class its own comment describes, a watch-based `kubectl delete namespace` wait in the teardown script on a host where watch-based waits are documented to hang, and a `to_ki()` conversion function whose "never aborts" contract is violated by fractional Kubernetes quantities. Three Info items cover preflight approximations and cwd assumptions.

Committed local-dev credentials (`grafana-dev-password`) follow the project's established committed-dev-password discipline, are documented in `docs/known-limitations.md`, and are not flagged. The polling-instead-of-`--wait` pattern in `observability-up.sh` is the documented, correct mitigation for this host and is likewise not flagged.

## Warnings

### WR-01: Documented CRD cleanup command is a no-op — label selector matches nothing (live-confirmed)

**File:** `docs/known-limitations.md:94`
**Issue:** The "CRD Teardown" section tells the reader that a full reset can be done with:

```bash
kubectl delete crd -l app.kubernetes.io/part-of=kube-prometheus-stack
```

Verified against the live cluster: all 10 `monitoring.coreos.com` CRDs exist (installed 2026-07-16 by this phase), but they carry **no labels at all** — `kubectl get crd prometheuses.monitoring.coreos.com -o jsonpath='{.metadata.labels}'` returns empty, and the documented command returns `No resources found` and deletes nothing. The kube-prometheus-stack `crds/` manifests are shipped without Helm-managed labels, which is exactly why `helm uninstall` doesn't remove them. A user following this doc will believe the CRDs are gone when they are not.
**Fix:** Replace with a name-based deletion (matches the upstream chart README's uninstall guidance):

```bash
kubectl get crd -o name | grep '\.monitoring\.coreos\.com$' | xargs kubectl delete
```

### WR-02: Grafana password override command in docs drops the pinned chart version

**File:** `docs/known-limitations.md:80-81`
**Issue:** The documented override command:

```bash
helm upgrade kube-prometheus-stack prometheus-community/kube-prometheus-stack -n observability \
  --reuse-values --set grafana.adminPassword=<real-password>
```

omits `--version 87.16.1`. Without it, Helm resolves the **latest** chart version from the repo, silently upgrading the entire stack and violating the D-05 pin that `scripts/observability-up.sh:94` enforces. kube-prometheus-stack major versions routinely carry breaking changes (CRD schema bumps, value renames), so a user following this doc to rotate a password could break the stack.
**Fix:** Add the pin to the documented command:

```bash
helm upgrade kube-prometheus-stack prometheus-community/kube-prometheus-stack -n observability \
  --version 87.16.1 --reuse-values --set grafana.adminPassword=<real-password>
```

### WR-03: `helm status` guard conflates "release not found" with every other Helm failure

**File:** `scripts/observability-down.sh:27-32`
**Issue:** The guard `if helm status ... &>/dev/null` treats **any** nonzero exit — bad flag, auth failure, transient API error, helm not on PATH — as "release not found" and skips the uninstall. This is precisely the failure class the comment at lines 21-25 documents (the original `--context` flag bug went undetected because the error was swallowed and the `if` always took the skip branch). The bug pattern was fixed for one instance but the error-swallowing structure that hid it is unchanged, so the next Helm-side error will again silently skip uninstall while the namespace delete proceeds. Note also that `observability-down.sh` has no prerequisite gate (unlike `observability-up.sh:25-34`), so a missing `helm` binary takes this same silent path.
**Fix:** The project pins Helm 3.21.2; `helm uninstall --ignore-not-found` (available since Helm 3.13) removes the need for the status probe entirely — absence is tolerated, every other error surfaces and trips `errexit`:

```bash
helm uninstall kube-prometheus-stack -n observability ${HELM_KCTX} --ignore-not-found
```

### WR-04: `kubectl delete namespace` uses the default watch-based wait that this host is documented to hang on

**File:** `scripts/observability-down.sh:38`
**Issue:** `kubectl delete` defaults to `--wait=true`, and kubectl's deletion waiter is implemented on the watch API (initial LIST, then WATCH until the object is gone). Namespace deletion is never instantaneous — finalizers must sweep the stack's resources — so the watch path is exercised on every teardown. `docs/known-limitations.md:117-131` documents (live-reproduced, twice) that watch/chunked-transfer connections through Docker Desktop's Windows port-forward proxy stall indefinitely on this host, which is why `observability-up.sh` deliberately avoids `--wait` and `kubectl wait`. The teardown script applies no such mitigation and can hang at this line.
**Fix:** Disable the built-in wait and poll, mirroring the up-script's Step 3 pattern:

```bash
kubectl "${KCTX}" delete namespace observability --ignore-not-found --wait=false
DEADLINE=$(( $(date +%s) + 180 ))
while kubectl "${KCTX}" get namespace observability >/dev/null 2>&1; do
  [ "$(date +%s)" -ge "$DEADLINE" ] && { echo "ERROR: namespace stuck terminating"; exit 1; }
  sleep 5
done
```

### WR-05: `to_ki()` aborts the whole preflight on fractional quantities, violating its own contract

**File:** `scripts/observability-up.sh:39-52`
**Issue:** The function's contract (line 38) is "Unknown/empty input contributes 0 — never aborts the sum on a single odd value." But fractional Kubernetes quantities — `0.5Gi`, `1.5Gi`, `1.5M` — are valid quantity syntax and match the suffix arms (`*Gi)` etc.) **before** the non-numeric guard on line 49. `$(( 0.5 * 1024 * 1024 ))` is a bash arithmetic syntax error: the `echo` never runs, `to_ki` outputs nothing, and the caller's `EXISTING_REQ_KI=$(( EXISTING_REQ_KI + ))` (line 62) is itself a syntax error that kills the script under `errexit`. Any pod on the cluster — including third-party charts installed later — whose memory request uses a fractional quantity makes `observability-up.sh` die mid-preflight with a cryptic arithmetic error. Additionally, the lowercase decimal suffix `k` (e.g. `500k`), which is the actual Kubernetes spelling (uppercase `K` is not valid quantity syntax), falls to the 0 branch — a silent undercount that weakens the preflight but at least honors the contract.
**Fix:** Validate the numeric part after stripping the suffix, before any arithmetic:

```bash
to_ki() {
  local val="$1" num
  [ -z "$val" ] && { echo 0; return; }
  num="${val%[KMGT]i}"; num="${num%[kKMG]}"
  case "$num" in ''|*[!0-9]*) echo 0; return ;; esac
  case "$val" in
    *Ki) echo "$num" ;;
    *Mi) echo $(( num * 1024 )) ;;
    *Gi) echo $(( num * 1024 * 1024 )) ;;
    *k|*K) echo $(( num * 1000 / 1024 )) ;;
    *M)  echo $(( num * 1000 * 1000 / 1024 )) ;;
    *G)  echo $(( num * 1000 * 1000 * 1000 / 1024 )) ;;
    *)   echo $(( num / 1024 )) ;;
  esac
}
```

## Info

### IN-01: Hardcoded 516Mi preflight constant must be manually kept in sync with values-trimmed.yaml

**File:** `scripts/observability-up.sh:20-22`
**Issue:** `TRIMMED_STACK_REQ_KI=$((516 * 1024))` duplicates the sum of the four resource requests in `infra/observability/values-trimmed.yaml`. Bumping any request in the YAML silently invalidates the preflight, and the YAML file carries no back-reference to this constant. The comment at line 21 also still names the component "kubeStateMetrics" although the values now live under the `kube-state-metrics:` key (cosmetic drift from the 11-04 fix).
**Fix:** Add a reciprocal comment in `values-trimmed.yaml` ("resource requests here are summed into TRIMMED_STACK_REQ_KI in scripts/observability-up.sh — update both"), and rename the comment token to `kube-state-metrics`.

### IN-02: Preflight sums only `.spec.containers` requests, ignoring initContainers

**File:** `scripts/observability-up.sh:60-65`
**Issue:** Kubernetes computes a pod's effective request as `max(initContainers, sum(containers))`; the preflight sums only regular containers, slightly undercounting existing cluster requests when init containers request more than the main containers. Acceptable approximation for a headroom check on a dev cluster; noted for accuracy.
**Fix:** If precision ever matters, include `.spec.initContainers[*].resources.requests.memory` in a second jsonpath range and take the per-pod max — otherwise leave as-is with a comment noting the approximation.

### IN-03: Both scripts assume cwd is the repo root

**File:** `scripts/observability-up.sh:96`, `scripts/observability-down.sh:45-46`
**Issue:** The relative path `-f infra/observability/values-trimmed.yaml` and the bare `make smoke` / `make smoke-launchpad` calls only resolve from the repo root. Running `bash observability-up.sh` from inside `scripts/` fails midway (up.sh at Step 2 after already mutating helm repo state; down.sh at the health re-check after the namespace is already deleted).
**Fix:** Anchor the scripts near the top:

```bash
cd "$(dirname "${BASH_SOURCE[0]}")/.."
```

---

_Reviewed: 2026-07-16T16:20:51Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
