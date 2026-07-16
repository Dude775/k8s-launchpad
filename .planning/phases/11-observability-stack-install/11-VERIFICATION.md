---
phase: 11-observability-stack-install
verified: 2026-07-16T14:00:00Z
status: gaps_found
score: 13/14 must-haves verified
overrides_applied: 0
gaps:
  - truth: "D-09: Every kept-enabled component has explicit resource requests and limits (nothing unbounded)"
    status: failed
    reason: "kube-state-metrics resources are set under the wrong Helm values key (`kubeStateMetrics.resources` instead of the subchart key `kube-state-metrics.resources`) and are silently dropped by the chart. The project's own live measurement in docs/known-limitations.md confirms the kube-state-metrics pod (and the two Grafana sidecar containers) run BestEffort with no memory request. This directly contradicts the locked decision D-09 (\"Never install unbounded\") and the file's own header comment (\"sets explicit bounded resources on every kept-enabled component\"), which is currently false."
    artifacts:
      - path: "infra/observability/values-trimmed.yaml"
        issue: "Lines 24-28: `kubeStateMetrics.resources` block is not consumed by any chart template — must be moved to the top-level `kube-state-metrics:` (hyphenated) subchart values key to actually apply."
    missing:
      - "Move the `resources:` block to a top-level `kube-state-metrics:` key in values-trimmed.yaml (keep `kubeStateMetrics.enabled: true` as the separate condition flag)."
      - "Re-run scripts/observability-up.sh and confirm via `kubectl get pod -n observability -o jsonpath='{...resources.requests}'` that the kube-state-metrics pod now carries the 10m/32Mi request."
      - "Update the file header comment and the known-limitations.md 'Measured observability headroom' note once the bound actually applies (expected total ~516Mi, matching the original preflight estimate)."
---

# Phase 11: Observability Stack Install Verification Report

**Phase Goal:** A trimmed kube-prometheus-stack (Prometheus Operator + Prometheus + Grafana + kube-state-metrics) runs in its own `observability` namespace on the kind cluster, with a documented teardown policy, and without disturbing the already-running v1.1 apps.
**Verified:** 2026-07-16T14:00:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | D-04: Idempotent install wrapper mirroring cluster-setup.sh in infra/observability/ | ✓ VERIFIED | `scripts/observability-up.sh` mirrors `scripts/cluster-setup.sh` house style (errexit, MSYS_NO_PATHCONV, KCTX, prereq gate, step echoes); live-run confirmed idempotent (helm upgrade --install, `helm repo add ... \|\| true`) |
| 2 | D-05: Chart sourced via `helm repo add prometheus-community`, pinned `--version 87.16.1`, no vendored tarball | ✓ VERIFIED | `scripts/observability-up.sh:81,94` — repo add + `--version 87.16.1`; no chart tarball found anywhere in git (`ls infra/observability/` shows only `values-trimmed.yaml`) |
| 3 | Alertmanager, node-exporter, defaultRules, and the four kubeadm scrape jobs disabled | ✓ VERIFIED | `infra/observability/values-trimmed.yaml:9-22` sets all 7 `enabled: false`/`create: false` flags; live-verified in 11-03-SUMMARY.md ("no alertmanager pod or node-exporter DaemonSet exist") |
| 4 | D-09: Every kept-enabled component has explicit resource requests and limits (nothing unbounded) | ✗ FAILED | `kube-state-metrics` resources set under the wrong values key (`kubeStateMetrics.resources`, not the subchart key `kube-state-metrics.resources`) and silently dropped. Confirmed by the project's own live measurement in `docs/known-limitations.md:107-110`: "kube-state-metrics ... run without an explicit memory request, i.e. BestEffort". Flagged in 11-REVIEW.md WR-01, unfixed as of this verification (no commit after `55125b4`). |
| 5 | D-10: Install script preflight capacity check, aborts with actionable Docker Desktop message if insufficient headroom | ✓ VERIFIED | `scripts/observability-up.sh:54-77` computes allocatable/existing/headroom via kubectl jsonpath, aborts with "raise Docker Desktop's memory allocation..." message; live-measured numbers recorded in known-limitations.md (9.71 GiB allocatable, ~9.18 GiB headroom) |
| 6 | D-06: Install script self-verifies pod readiness and re-runs `make smoke`/`make smoke-launchpad` | ✓ VERIFIED (with noted risk) | `scripts/observability-up.sh:104-129` — Step 3 readiness poll + Step 4 `make smoke && make smoke-launchpad`; live-verified pass in 11-03-SUMMARY.md (4 pods Running/Ready, 0 app restarts). Note: 11-REVIEW.md WR-03 flags a theoretical race (pod-count check can pass before the Prometheus pod is created by the operator) — did not manifest in the one live run performed, tracked as a warning below, not a truth failure. |
| 7 | D-07: Grafana admin uses committed password `grafana-dev-password` | ✓ VERIFIED | `infra/observability/values-trimmed.yaml:32-34`; human-checkpoint approved login in 11-03-SUMMARY.md ("admin login with the D-07 password succeeds") |
| 8 | D-08: Anonymous Viewer-role Grafana access via `grafana.ini` | ✓ VERIFIED | `infra/observability/values-trimmed.yaml:35-38` (`auth.anonymous.enabled: true`, `org_role: Viewer`); human-checkpoint approved ("anonymous Viewer read-only access works per D-08") |
| 9 | D-11: Prometheus storage is emptyDir (no PVC), retention 24h | ✓ VERIFIED | `infra/observability/values-trimmed.yaml:56-67` — `retention: 24h`, no `storageSpec:` key present (`grep -c 'storageSpec:'` = 0) |
| 10 | D-04: Idempotent teardown wrapper mirroring cluster-teardown.sh | ✓ VERIFIED | `scripts/observability-down.sh` mirrors `scripts/cluster-teardown.sh`; live-verified safe/idempotent (namespace NotFound after teardown, per 11-03-SUMMARY.md) |
| 11 | Teardown runs `helm uninstall` only, deliberately leaves `monitoring.coreos.com` CRDs (D-01) | ✓ VERIFIED | `scripts/observability-down.sh:15-32` — no CRD-deletion command (`grep -c 'delete crd'` = 0); live-verified "all 10 monitoring.coreos.com CRDs present" after teardown |
| 12 | Teardown deletes the `observability` namespace (D-02) | ✓ VERIFIED | `scripts/observability-down.sh:38` `kubectl delete namespace observability --ignore-not-found`; live-verified `kubectl get ns observability` → NotFound |
| 13 | Teardown re-runs `make smoke`/`make smoke-launchpad` (D-03) | ✓ VERIFIED | `scripts/observability-down.sh:44-46`; live-verified both PASS post-teardown, 0 app restarts |
| 14 | CRD-retention, committed Grafana password, anonymous-viewer decisions documented as accepted risks | ✓ VERIFIED | `docs/known-limitations.md` — "Committed Grafana Admin Password", "CRD Teardown Leaves monitoring.coreos.com CRDs Installed", "Anonymous Grafana Viewer Access" sections all present; stale PRD-4 section amended |

**Score:** 13/14 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `infra/observability/values-trimmed.yaml` | Trimmed kube-prometheus-stack values (disable flags, resources, grafana creds, retention) | ⚠️ SUBSTANTIVE BUT PARTIALLY HOLLOW | File exists, 68 lines, all disable flags/creds/retention correct. One config block (`kubeStateMetrics.resources`) is present in the file but inert at runtime — configured intent does not reach the cluster (see gap above). |
| `scripts/observability-up.sh` | Idempotent, self-verifying install wrapper | ✓ VERIFIED | 134 lines; preflight, helm upgrade --install, readiness wait, app-survival re-check all present and live-verified working. Diverges from the original plan text by omitting `--wait` on the helm command (replaced with polling in Step 3) — this is a documented, live-justified fix (see `docs/known-limitations.md` "Windows/Docker Desktop: helm --wait ... hang" section), not a regression. |
| `scripts/observability-down.sh` | Idempotent teardown wrapper | ✓ VERIFIED | 48 lines; guarded helm uninstall, namespace delete, app-survival re-check; live-verified working end to end |
| `docs/known-limitations.md` | Accepted-risk records + measured headroom | ✓ VERIFIED | Contains `grafana-dev-password`, `monitoring.coreos.com`, `Anonymous Grafana Viewer Access`, `infra/observability/`, and `Measured observability headroom:` marker; stale PRD-4 section corrected |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `scripts/observability-up.sh` | `infra/observability/values-trimmed.yaml` | `-f` flag | ✓ WIRED | `-f infra/observability/values-trimmed.yaml` present in the `helm upgrade --install` invocation |
| `scripts/observability-up.sh` | `make smoke` / `make smoke-launchpad` | post-install app-survival check | ✓ WIRED | Step 4 invokes both targets; live-verified PASS |
| `scripts/observability-down.sh` | `make smoke` / `make smoke-launchpad` | post-teardown app-survival check | ✓ WIRED | Present at end of script; live-verified PASS |
| `docs/known-limitations.md` | D-01 CRD retention policy | accepted-risk section | ✓ WIRED | "CRD Teardown Leaves monitoring.coreos.com CRDs Installed" section cross-references `helm uninstall` and Phase 12 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `infra/observability/values-trimmed.yaml` (`kubeStateMetrics.resources`) | Helm values → chart template → Pod spec `resources` field | Static YAML → `helm upgrade --install -f values-trimmed.yaml` | No — value never reaches the rendered Pod manifest because it is set under the wrong values key | ✗ DISCONNECTED |
| `infra/observability/values-trimmed.yaml` (`prometheusOperator.resources`, `grafana.resources`, `prometheus.prometheusSpec.resources`) | Same path | Same | Yes — confirmed applied (484 MiB total measured requests = Grafana 128 + Prometheus 256 + operator 100, per `docs/known-limitations.md`) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Script syntax valid | `bash -n scripts/observability-up.sh` / `bash -n scripts/observability-down.sh` | Not re-run (static syntax already exercised live in Plan 03's execution — a real cluster run implies valid syntax) | ? SKIP (superseded by live run) |
| Live install/readiness/teardown lifecycle | `bash scripts/observability-up.sh` → assertions → `bash scripts/observability-down.sh` → assertions | Already executed live in Plan 03; not re-run here per task instructions (torn-down state is the certified end state, do not re-run live cluster installs) | ✓ PASS (evidence: 11-03-SUMMARY.md, self-check block) |

### Probe Execution

No `scripts/*/tests/probe-*.sh` files exist in this repo and none are referenced by the Phase 11 plans/summaries. Step 7c: SKIPPED (no probe scripts declared or discovered for this phase).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|--------------|------------|-------------|--------|----------|
| OBS-01 | 11-01-PLAN.md | Operator can install a trimmed kube-prometheus-stack (pinned 87.16.1; Alertmanager/node-exporter/default-rules/kubeadm jobs disabled; conservative resource limits) into the kind cluster from `infra/observability/` | ⚠️ PARTIALLY SATISFIED | Install path fully works and disables the right components; however the "conservative resource limits" / "nothing unbounded" clause is violated for kube-state-metrics (see gap). Functionally the stack installs and does not currently starve the node (ample headroom), but the requirement's explicit resource-boundedness clause is not met as written. |
| OBS-02 | 11-02-PLAN.md, 11-03-PLAN.md | Operator can tear down the observability stack cleanly with an explicit, documented CRD teardown policy — both v1.1 apps keep running untouched | ✓ SATISFIED | Live-verified: `helm uninstall` + namespace delete + CRDs retained + both v1.1 apps healthy (0 restarts) before/after |

REQUIREMENTS.md marks both OBS-01 and OBS-02 as `[x] Complete` — OBS-02 is fully justified; OBS-01 carries an unresolved gap against its own "conservative resource limits" clause that should not yet be marked fully closed without either a fix or an explicit override.

No orphaned requirements found for Phase 11 beyond OBS-01/OBS-02 (both are the full requirement set declared across the phase's plans).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `infra/observability/values-trimmed.yaml` | 24-28 | Config block silently ignored by the chart (wrong values key) — matches "hardcoded/ineffective config" stub pattern | 🛑 Blocker | Directly falsifies the file's own header claim and the locked D-09 decision; kube-state-metrics runs unbounded |
| `scripts/observability-down.sh` | 38 | `kubectl delete namespace ... --ignore-not-found` uses default watch-based `--wait=true`, the same wait mechanism the project's own `docs/known-limitations.md` documents as hanging indefinitely on this Windows/Docker Desktop/kind setup (for the analogous `helm --wait` case) | ⚠️ Warning | Did not manifest in the one live-verified run (namespace deletion completed), but is an unmitigated recurrence risk for the exact failure mode already reproduced once in this environment for the sibling `helm --wait` case |
| `scripts/observability-up.sh` | 104-124 | Readiness self-check accepts "N pods Ready" without asserting the expected component count (operator/grafana/kube-state-metrics/prometheus = 4); could theoretically report success before the operator-created Prometheus pod exists | ℹ️ Info | Did not manifest in the live run (4 pods reached Ready), tracked as a latent race per 11-REVIEW.md WR-03 |
| `scripts/observability-up.sh` | 39-52 | `to_ki()` helper does not handle Kubernetes' lowercase `k` decimal-kilo suffix or milli-quantities; falls through to 0 | ℹ️ Info | Low likelihood at current Mi/Gi-only usage; tracked per 11-REVIEW.md WR-04 |
| `docs/known-limitations.md` | 94 | Documented "full CRD reset" command (`kubectl delete crd -l app.kubernetes.io/part-of=kube-prometheus-stack`) likely matches zero CRDs (label not present on Helm `crds/`-installed CRDs) | ℹ️ Info | Optional/manual command only; does not affect any must-have or automated path |

No `TBD`/`FIXME`/`XXX` unresolved debt markers found in any Phase 11 file.

## Human Verification Required

None outstanding. The phase's single human-verify checkpoint (Task 2 of 11-03-PLAN.md: Prometheus/Grafana UI reachability, admin login D-07, anonymous viewer D-08) was already executed and approved by the user on 2026-07-16, per 11-03-SUMMARY.md's Task 2 record. No new items require human testing beyond what was already checkpointed.

## Gaps Summary

One must-have truth fails: **D-09 ("Every kept-enabled component has explicit resource requests and limits — nothing unbounded")**. The `values-trimmed.yaml` file sets `kubeStateMetrics.resources`, but kube-prometheus-stack only reads pod resource overrides for the bundled kube-state-metrics subchart from the top-level hyphenated key `kube-state-metrics:` (the `kubeStateMetrics:` key is the chart's own condition/serviceMonitor-override block, not a pass-through to the subchart). As a direct result, the kube-state-metrics pod (and the Grafana sidecar containers) run with no memory request — BestEffort QoS — which the project's own live-measured data in `docs/known-limitations.md` explicitly confirms ("kube-state-metrics ... run without an explicit memory request, i.e. BestEffort"). This was independently caught in code review (`11-REVIEW.md` WR-01) and remains unfixed as of this verification — there is no commit after the review commit (`55125b4`) touching `values-trimmed.yaml`.

This is not a cosmetic issue: D-09 was a locked decision explicitly stated as "Never install unbounded," and the phase's own values file header claims (falsely, as written) that "every kept-enabled component" has bounded resources. Because the current dev machine has ample headroom (~9.18 GiB free), the unbounded component has not caused any observed disruption to the v1.1 apps — but the phase goal's explicit resource-safety guarantee is not actually delivered for this component, and the gap is trivial to fix (move one block to the correct values key) and cheap to re-verify (re-run `observability-up.sh` and check the pod's resource requests).

Everything else — install/teardown scripts, disable flags, Grafana access (D-07/D-08), Prometheus retention/storage (D-11), preflight capacity gate (D-10), CRD retention policy (D-01/D-02), app-survival re-checks (D-06/D-03), and accepted-risk documentation — is verified working, both statically and via the live lifecycle already executed and recorded in `11-03-SUMMARY.md`, with the human UI checkpoint already approved.

**This looks like an oversight, not an intentional deviation** (the review flagged it as a bug, not the executor). No override is suggested; recommend closing via a small follow-up plan that moves the `resources:` block to the `kube-state-metrics:` subchart key, re-runs the live install, and confirms the pod now carries an explicit memory request.

---

_Verified: 2026-07-16T14:00:00Z_
_Verifier: Claude (gsd-verifier)_
