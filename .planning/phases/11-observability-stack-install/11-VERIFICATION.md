---
phase: 11-observability-stack-install
verified: 2026-07-16T20:00:00Z
status: passed
score: 14/14 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 13/14
  gaps_closed:
    - "D-09: Every kept-enabled component has explicit resource requests and limits (nothing unbounded) — kube-state-metrics resources moved to the chart-consumed top-level `kube-state-metrics:` subchart key; pod live-confirmed carrying 32Mi/10m request with Burstable QoS."
  gaps_remaining: []
  regressions: []
---

# Phase 11: Observability Stack Install Verification Report

**Phase Goal:** A trimmed `kube-prometheus-stack` (Prometheus Operator + Prometheus + Grafana + kube-state-metrics) runs in its own `observability` namespace on the kind cluster, with a documented teardown policy, and without disturbing the already-running v1.1 apps.
**Verified:** 2026-07-16T20:00:00Z
**Status:** passed
**Re-verification:** Yes — after gap closure (plan 11-04)

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | D-04: Idempotent install wrapper mirroring cluster-setup.sh in infra/observability/ | ✓ VERIFIED | `scripts/observability-up.sh` mirrors `scripts/cluster-setup.sh` house style (errexit, MSYS_NO_PATHCONV, KCTX, prereq gate, step echoes); live-run confirmed idempotent (`helm upgrade --install`, `helm repo add ... \|\| true`) |
| 2 | D-05: Chart sourced via `helm repo add prometheus-community`, pinned `--version 87.16.1`, no vendored tarball | ✓ VERIFIED | `scripts/observability-up.sh:81,94` — repo add + `--version 87.16.1`; no chart tarball in git; independently confirmed against the live pinned chart with `helm show values prometheus-community/kube-prometheus-stack --version 87.16.1` |
| 3 | Alertmanager, node-exporter, defaultRules, and the four kubeadm scrape jobs disabled | ✓ VERIFIED | `infra/observability/values-trimmed.yaml:15-28` sets all 7 `enabled: false`/`create: false` flags; live-verified in 11-03-SUMMARY.md ("no alertmanager pod or node-exporter DaemonSet exist") |
| 4 | D-09: Every kept-enabled component has explicit resource requests and limits (nothing unbounded) | ✓ VERIFIED (gap closed by 11-04) | `infra/observability/values-trimmed.yaml:37-40` now places `resources:` (10m/32Mi requests, 50m/64Mi limits) under the top-level hyphenated `kube-state-metrics:` subchart key; `kubeStateMetrics:` (camelCase, lines 30-33) retains only `enabled: true`. Independently confirmed against the live pinned chart: `helm show values ... --version 87.16.1` shows `kubeStateMetrics:` at values line 2648 (condition-only) and `kube-state-metrics:` at line 2653 (subchart pass-through) — exactly matching the fix. Live pod evidence recorded in 11-04-SUMMARY.md: `resources.requests.memory=32Mi`, `resources.requests.cpu=10m`, `status.qosClass=Burstable` (not BestEffort). 11-REVIEW.md re-review (2026-07-16T16:20:51Z) independently confirms the fix is "provably correct" via the same static chart check. |
| 5 | D-10: Install script preflight capacity check, aborts with actionable Docker Desktop message if insufficient headroom | ✓ VERIFIED | `scripts/observability-up.sh:54-77` computes allocatable/existing/headroom via kubectl jsonpath, aborts with "raise Docker Desktop's memory allocation..." message; live-measured numbers recorded in known-limitations.md (9.71 GiB allocatable, ~9.18 GiB headroom) |
| 6 | D-06: Install script self-verifies pod readiness and re-runs `make smoke`/`make smoke-launchpad` | ✓ VERIFIED (with noted risk) | `scripts/observability-up.sh:104-129` — Step 3 readiness poll + Step 4 `make smoke && make smoke-launchpad`; live-verified pass in 11-03-SUMMARY.md and re-verified again in 11-04-SUMMARY.md (both PASS both runs, 0 app restarts). 11-REVIEW.md WR-05 flags a `to_ki()` fractional-quantity edge case (non-blocking, tracked as a warning below). |
| 7 | D-07: Grafana admin uses committed password `grafana-dev-password` | ✓ VERIFIED | `infra/observability/values-trimmed.yaml:44-46`; human-checkpoint approved login in 11-03-SUMMARY.md ("admin login with the D-07 password succeeds") |
| 8 | D-08: Anonymous Viewer-role Grafana access via `grafana.ini` | ✓ VERIFIED | `infra/observability/values-trimmed.yaml:47-50` (`auth.anonymous.enabled: true`, `org_role: Viewer`); human-checkpoint approved ("anonymous Viewer read-only access works per D-08") |
| 9 | D-11: Prometheus storage is emptyDir (no PVC), retention 24h | ✓ VERIFIED | `infra/observability/values-trimmed.yaml:66-79` — `retention: 24h`, no `storageSpec:` key present |
| 10 | D-04: Idempotent teardown wrapper mirroring cluster-teardown.sh | ✓ VERIFIED | `scripts/observability-down.sh` mirrors `scripts/cluster-teardown.sh`; live-verified safe/idempotent (namespace NotFound after teardown), re-confirmed live again by this verification run |
| 11 | Teardown runs `helm uninstall` only, deliberately leaves `monitoring.coreos.com` CRDs (D-01) | ✓ VERIFIED | `scripts/observability-down.sh:15-32` — no CRD-deletion command; live-verified "10 monitoring.coreos.com CRDs present" after teardown in 11-03-SUMMARY.md and again independently confirmed by this verifier's own `kubectl get crd \| grep -c monitoring.coreos.com` → 10 |
| 12 | Teardown deletes the `observability` namespace (D-02) | ✓ VERIFIED | `scripts/observability-down.sh:38` `kubectl delete namespace observability --ignore-not-found`; independently confirmed by this verifier's own `kubectl --context=kind-kind get ns observability` → `Error from server (NotFound)` |
| 13 | Teardown re-runs `make smoke`/`make smoke-launchpad` (D-03) | ✓ VERIFIED | `scripts/observability-down.sh:44-46`; live-verified both PASS post-teardown in 11-03 and 11-04, 0 app restarts; independently confirmed by this verifier's own `kubectl get pods -A` showing both v1.1 apps `Running`, `RESTARTS 0`, age ~5h50m (consistent with no disruptive event since before the 11-04 re-run) |
| 14 | CRD-retention, committed Grafana password, anonymous-viewer decisions documented as accepted risks | ✓ VERIFIED | `docs/known-limitations.md` — "Committed Grafana Admin Password", "CRD Teardown Leaves monitoring.coreos.com CRDs Installed", "Anonymous Grafana Viewer Access", and the corrected "Measured observability headroom" section (~516 MiB total, no BestEffort claim) all present |

**Score:** 14/14 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `infra/observability/values-trimmed.yaml` | Trimmed kube-prometheus-stack values (disable flags, resources, grafana creds, retention) | ✓ VERIFIED | 80 lines; all disable flags/creds/retention correct; kube-state-metrics resources now under the correct `kube-state-metrics:` (hyphenated) key and independently confirmed against the live chart's own values schema. Header comment accurately describes the two-key mechanism (camelCase = condition, hyphenated = subchart values). |
| `scripts/observability-up.sh` | Idempotent, self-verifying install wrapper | ✓ VERIFIED | Preflight, `helm upgrade --install`, readiness wait, app-survival re-check all present and live-verified working across two separate live runs (11-03, 11-04) |
| `scripts/observability-down.sh` | Idempotent teardown wrapper | ✓ VERIFIED | Guarded helm uninstall, namespace delete, app-survival re-check; live-verified working end to end across two separate live runs; current cluster state independently confirms a clean torn-down result |
| `docs/known-limitations.md` | Accepted-risk records + measured headroom | ✓ VERIFIED | Contains `grafana-dev-password`, `monitoring.coreos.com`, `Anonymous Grafana Viewer Access`, `infra/observability/`, and the corrected `Measured observability headroom` section (~516 MiB, kube-state-metrics no longer described as BestEffort) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `scripts/observability-up.sh` | `infra/observability/values-trimmed.yaml` | `-f` flag | ✓ WIRED | `-f infra/observability/values-trimmed.yaml` present in the `helm upgrade --install` invocation |
| `scripts/observability-up.sh` | `make smoke` / `make smoke-launchpad` | post-install app-survival check | ✓ WIRED | Step 4 invokes both targets; live-verified PASS on both the 11-03 and 11-04 runs |
| `scripts/observability-down.sh` | `make smoke` / `make smoke-launchpad` | post-teardown app-survival check | ✓ WIRED | Present at end of script; live-verified PASS on both runs |
| `docs/known-limitations.md` | D-01 CRD retention policy | accepted-risk section | ✓ WIRED | "CRD Teardown Leaves monitoring.coreos.com CRDs Installed" section cross-references `helm uninstall` and Phase 12 |
| `infra/observability/values-trimmed.yaml` (`kube-state-metrics:`) | kube-state-metrics pod spec `resources` | Helm subchart dependency values key | ✓ WIRED | Confirmed both statically (matches the pinned chart's own `kubeStateMetrics:`/`kube-state-metrics:` split, independently re-verified by this verifier via `helm show values`) and live (11-04-SUMMARY.md pod jsonpath evidence: `32Mi`/`10m`/`Burstable`) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `infra/observability/values-trimmed.yaml` (`kube-state-metrics:`) | Helm values → chart template → Pod spec `resources` field | Static YAML → `helm upgrade --install -f values-trimmed.yaml` | Yes — value now reaches the rendered Pod manifest; confirmed live (32Mi/10m/Burstable) and statically against the chart's own values schema | ✓ FLOWING |
| `infra/observability/values-trimmed.yaml` (`prometheusOperator.resources`, `grafana.resources`, `prometheus.prometheusSpec.resources`) | Same path | Same | Yes — confirmed applied (484 MiB requests: Grafana 128 + Prometheus 256 + operator 100, plus kube-state-metrics 32 = ~516 MiB total, per `docs/known-limitations.md`) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Observability namespace is absent (certified torn-down end state) | `kubectl --context=kind-kind get ns observability` (run directly by this verifier) | `Error from server (NotFound)` | ✓ PASS |
| `monitoring.coreos.com` CRDs retained (D-01) | `kubectl --context=kind-kind get crd \| grep -c monitoring.coreos.com` (run directly by this verifier) | `10` | ✓ PASS |
| v1.1 apps healthy, zero restarts | `kubectl --context=kind-kind get pods -A` (run directly by this verifier) | `field-guide-api`, `field-guide-api-mongodb`, `launchpad`, `launchpad-mongodb` all `Running`, `RESTARTS 0`, age ~5h49m-5h50m | ✓ PASS |
| Chart subchart-values structure matches the fix | `helm show values prometheus-community/kube-prometheus-stack --version 87.16.1 \| grep -n -E "^kubeStateMetrics:\|^kube-state-metrics:"` (run directly by this verifier) | `2648:kubeStateMetrics:` / `2653:kube-state-metrics:` — confirms condition-key vs. subchart-values-key split exactly as the fix assumes | ✓ PASS |
| No debt markers in modified files | `grep -nE "TBD\|FIXME\|XXX\|TODO\|HACK\|PLACEHOLDER" infra/observability/values-trimmed.yaml docs/known-limitations.md scripts/observability-up.sh scripts/observability-down.sh` | No matches | ✓ PASS |
| Live install/readiness/teardown lifecycle (kube-state-metrics fix) | `bash scripts/observability-up.sh` → jsonpath assertions → `bash scripts/observability-down.sh` → assertions | Already executed live in plan 11-04 (recorded jsonpath outputs: 32Mi / 10m / Burstable); current live cluster state independently corroborates the certified torn-down end state (see spot-checks above) — not re-run in full here per task instructions (do not require live pods; verify via recorded lifecycle evidence + current state) | ✓ PASS (evidence: 11-04-SUMMARY.md + this verifier's independent live namespace/CRD/app-health checks) |

### Probe Execution

No `scripts/*/tests/probe-*.sh` files exist in this repo and none are referenced by the Phase 11 plans/summaries. Step 7c: SKIPPED (no probe scripts declared or discovered for this phase).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|--------------|------------|-------------|--------|----------|
| OBS-01 | 11-01-PLAN.md, 11-03-PLAN.md, 11-04-PLAN.md | Operator can install a trimmed kube-prometheus-stack (pinned 87.16.1; Alertmanager/node-exporter/default-rules/kubeadm jobs disabled; conservative resource limits) into the kind cluster from `infra/observability/` | ✓ SATISFIED | Install path fully works, disables the right components, and the "conservative resource limits / nothing unbounded" clause is now met for all four kept-enabled components (grafana, prometheusOperator, prometheus, kube-state-metrics), confirmed live and statically |
| OBS-02 | 11-02-PLAN.md, 11-03-PLAN.md | Operator can tear down the observability stack cleanly with an explicit, documented CRD teardown policy — both v1.1 apps keep running untouched | ✓ SATISFIED | Live-verified across two runs (11-03, 11-04) and independently re-confirmed by this verifier: `helm uninstall` + namespace delete + CRDs retained + both v1.1 apps healthy (0 restarts) |

REQUIREMENTS.md marks both OBS-01 and OBS-02 as `[x] Complete` — both are now fully justified with no unresolved must-have gaps.

No orphaned requirements found for Phase 11 beyond OBS-01/OBS-02 (both are the full requirement set declared across the phase's plans: 11-01 declares OBS-01, 11-02 declares OBS-02, 11-03 declares both, 11-04 declares OBS-01 for the gap closure).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `docs/known-limitations.md` | 94 | Documented "full CRD reset" command (`kubectl delete crd -l app.kubernetes.io/part-of=kube-prometheus-stack`) is a live-confirmed no-op — the label selector matches zero CRDs (11-REVIEW.md WR-01, re-review) | ⚠️ Warning | Optional/manual command only; does not affect any must-have or automated path. A user following this doc would wrongly believe CRDs were removed. |
| `docs/known-limitations.md` | 80-81 | Documented Grafana-password override `helm upgrade` command omits `--version 87.16.1`, silently dropping the D-05 chart pin if followed (11-REVIEW.md WR-02) | ⚠️ Warning | Manual/optional doc command, not exercised by any automated path or must-have; real risk only if a human copies the command verbatim |
| `scripts/observability-down.sh` | 27-32 | `helm status ... &>/dev/null` guard conflates "release not found" with every other Helm failure (missing binary, auth error, etc.) — same error-swallowing class the script's own comment warns about (11-REVIEW.md WR-03) | ⚠️ Warning | Did not manifest in either live run (11-03, 11-04) performed so far; latent risk for a future Helm-side failure to silently skip uninstall |
| `scripts/observability-down.sh` | 38 | `kubectl delete namespace ... --ignore-not-found` uses the default watch-based `--wait=true`, the same wait mechanism documented elsewhere in this repo as hanging on this Windows/Docker Desktop/kind host (11-REVIEW.md WR-04, carried over from the initial verification) | ⚠️ Warning | Did not manifest in either live-verified run (both completed with namespace deleted); unmitigated recurrence risk for the failure mode already reproduced once for the sibling `helm --wait` case |
| `scripts/observability-up.sh` | 39-52 | `to_ki()` helper's "never aborts" contract is violated by fractional Kubernetes quantities (e.g. `0.5Gi`) — causes a bash arithmetic syntax error under `errexit`; also does not handle the lowercase decimal-kilo suffix `k` (11-REVIEW.md WR-05) | ⚠️ Warning | Low likelihood at current Mi/Gi-only usage on this cluster; did not manifest in any live run so far |
| `scripts/observability-up.sh` | 20-22 | Hardcoded `TRIMMED_STACK_REQ_KI=516*1024` preflight constant must be manually kept in sync with `values-trimmed.yaml`; inline comment still says "kubeStateMetrics" though the values now live under `kube-state-metrics:` (11-REVIEW.md IN-01) | ℹ️ Info | Cosmetic drift; no functional impact on any must-have |
| `scripts/observability-up.sh` | 60-65 | Preflight sums only `.spec.containers` requests, ignoring `initContainers` (11-REVIEW.md IN-02) | ℹ️ Info | Acceptable approximation for a dev-cluster headroom check |
| `scripts/observability-up.sh`, `scripts/observability-down.sh` | 96 / 45-46 | Both scripts assume cwd is the repo root (11-REVIEW.md IN-03) | ℹ️ Info | Not exercised as a failure in any live run; Makefile always invokes from repo root |

No `TBD`/`FIXME`/`XXX` unresolved debt markers found in any Phase 11 file (verified directly by this verifier's own grep, in addition to the code review's independent narrative confirmation).

None of the Warnings above affect a phase must-have or requirement; all are either pre-existing (already known and non-blocking at the initial verification, e.g. WR-04/the namespace-delete wait risk) or newly surfaced doc/script robustness issues (WR-01, WR-02, WR-03, WR-05) that did not manifest in any of the three live install/teardown runs performed across Phase 11 (11-03, 11-04, and this verifier's own independent live checks). They are recorded here as recommended follow-up hardening, not as gaps blocking phase completion.

## Human Verification Required

None outstanding. The phase's single human-verify checkpoint (Task 2 of 11-03-PLAN.md: Prometheus/Grafana UI reachability, admin login D-07, anonymous viewer D-08) was already executed and approved by the user on 2026-07-16, per 11-03-SUMMARY.md's Task 2 record. No new items require human testing beyond what was already checkpointed; the 11-04 gap closure (D-09) was verified via live `kubectl` jsonpath output and independently re-confirmed by this verifier via direct chart-schema and live-cluster checks — no human judgment call was needed for this fix.

## Gaps Summary

None. The single gap from the initial verification — D-09 must-have truth #4 (kube-state-metrics resources silently ignored under the wrong values key, causing BestEffort QoS) — was closed by gap-closure plan 11-04:

1. `infra/observability/values-trimmed.yaml` now places the kube-state-metrics `resources` block under the chart-consumed top-level hyphenated `kube-state-metrics:` subchart key (verified in the file directly by this verifier), with `kubeStateMetrics.enabled: true` retained as the pure condition flag.
2. This verifier independently re-derived the chart's own values schema (`helm show values prometheus-community/kube-prometheus-stack --version 87.16.1`) and confirmed line 2648 `kubeStateMetrics:` is condition-only and line 2653 `kube-state-metrics:` is the subchart pass-through key — exactly matching the fix, with no reliance on SUMMARY.md narration alone.
3. 11-04-SUMMARY.md records live `kubectl` jsonpath proof (`resources.requests.memory=32Mi`, `resources.requests.cpu=10m`, `status.qosClass=Burstable`) captured during a real install run on the kind cluster; 11-REVIEW.md's independent re-review corroborates the fix is "provably correct."
4. This verifier independently confirmed the current live cluster state matches the certified torn-down end state: `observability` namespace returns NotFound, 10 `monitoring.coreos.com` CRDs remain, and both v1.1 apps (`field-guide-api`, `launchpad`, plus their MongoDB pods) are `Running` with 0 restarts at ~5h50m age — consistent with no disruptive event since the 11-04 fix was applied and torn back down.
5. `docs/known-limitations.md` was independently read and confirmed to state the corrected ~516 MiB total and no longer contains the retracted "kube-state-metrics ... BestEffort" claim.

All 14 observable truths, all 4 (now 5, including the new kube-state-metrics key link) key links, all required artifacts, and both requirements (OBS-01, OBS-02) are verified. Five non-blocking Warnings and three Info items remain from the code-review re-review (documentation/robustness issues, none of which touch a must-have or have manifested in any live run) — recorded above for optional follow-up, not as phase-blocking gaps.

---

_Verified: 2026-07-16T20:00:00Z_
_Verifier: Claude (gsd-verifier)_
