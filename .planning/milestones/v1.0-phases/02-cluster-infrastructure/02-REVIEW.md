---
phase: 02-cluster-infrastructure
reviewed: 2026-07-05T12:37:20Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - infra/kind/kind-config.yaml
  - scripts/cluster-setup.sh
  - scripts/cluster-teardown.sh
  - Makefile
findings:
  critical: 1
  warning: 3
  info: 5
  total: 9
status: issues_found
---

# Phase 02: Code Review Report

**Reviewed:** 2026-07-05T12:37:20Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed the kind cluster + local registry lifecycle for Phase 02: kind config, setup/teardown scripts, and the Makefile targets. The implementation closely tracks the official kind local-registry pattern, the Windows/Git Bash hardening (`MSYS_NO_PATHCONV=1`, `SHELL := /bin/bash`) is present, and the previously reported Step 6 false-timeout bug is correctly fixed (`--for=jsonpath='{.status.phase}'=Succeeded` plus pre-delete). The Makefile's coverage claim was cross-checked against `apps/field-guide-api/pytest.ini` (`--cov-fail-under=95`) and holds.

One critical defect remains: every `kubectl` call in cluster-setup.sh runs against whatever kubeconfig context happens to be active, and on the idempotent re-run path nothing guarantees that context is the kind cluster — the script can apply and delete resources on an unrelated cluster. Three warnings cover an idempotency gap (stopped registry container), an incomplete prerequisite gate, and poor failure-path behavior in the Step 6 verification.

## Critical Issues

### CR-01: kubectl commands are not pinned to the kind context — can mutate/delete resources on the wrong cluster

**File:** `scripts/cluster-setup.sh:71`, `scripts/cluster-setup.sh:89-99`
**Issue:** All five `kubectl` invocations (apply ConfigMap to `kube-public`, `delete pod registry-verify` twice, `run`, `wait`) operate on the *current* kubeconfig context. On first run, `kind create cluster` (line 43) switches the context to `kind-kind`, masking the problem. But on the idempotent re-run path — line 46, "Cluster already exists — skipping" — the context switch never happens. If the user has since pointed kubectl at any other cluster (work cluster, another local cluster), re-running `make cluster-up` will: create a ConfigMap in that cluster's `kube-public` namespace, **delete any pod named `registry-verify` in its default namespace**, and launch a pod pulling from `localhost:5001` there. That is silent mutation and deletion on an unintended cluster. The one-command idempotent re-run was explicitly live-verified today, so this path is exercised in normal use.
**Fix:** Pin every kubectl call to the kind context:
```bash
KCTX="--context kind-kind"

cat <<EOF | kubectl ${KCTX} apply -f -
...
EOF
...
kubectl ${KCTX} delete pod registry-verify --ignore-not-found
kubectl ${KCTX} run registry-verify ...
kubectl ${KCTX} wait --for=jsonpath='{.status.phase}'=Succeeded pod/registry-verify --timeout=60s
kubectl ${KCTX} delete pod registry-verify --ignore-not-found
```
(Alternatively `kubectl config use-context kind-kind` immediately after Step 2, but per-command `--context` avoids mutating the user's global kubectl state.)

## Warnings

### WR-01: Step 1 idempotency breaks when the registry container exists but is stopped

**File:** `scripts/cluster-setup.sh:28-38`
**Issue:** The guard checks `.State.Running != 'true'`. If the `kind-registry` container exists but is stopped (e.g., `docker stop kind-registry`, or Docker Desktop restarted before `--restart=always` re-created state), `docker inspect` returns `false`, the branch runs `docker run --name kind-registry`, which fails with `Conflict. The container name "/kind-registry" is already in use`, and `errexit` aborts the entire setup. The script's stated contract is idempotent re-run, and this state violates it. (This flaw is inherited from the upstream kind docs script — it is still a defect.)
**Fix:**
```bash
if [ "$(docker inspect -f '{{.State.Running}}' "${reg_name}" 2>/dev/null || true)" != 'true' ]; then
  if docker inspect "${reg_name}" >/dev/null 2>&1; then
    docker start "${reg_name}"
    echo "    Existing registry container started."
  else
    docker run -d --restart=always -p "127.0.0.1:${reg_port}:5000" \
      --network bridge --name "${reg_name}" registry:3
    echo "    Registry started."
  fi
fi
```

### WR-02: Prerequisite gate checks only `kind`; `docker` and `kubectl` are equally hard dependencies

**File:** `scripts/cluster-setup.sh:19-24`
**Issue:** The gate validates `kind` with a helpful install message, but the script uses `docker` starting at line 28 and `kubectl` starting at line 71. Missing docker (or docker CLI present but daemon down) fails Step 1 with a raw daemon error; missing kubectl fails only at Step 5 — *after* the cluster has been created — leaving the run half-complete with an unhelpful `command not found`. Fail fast on all three before doing any work.
**Fix:**
```bash
for tool in kind docker kubectl; do
  command -v "$tool" >/dev/null 2>&1 || { echo "ERROR: $tool is not installed or not on PATH."; exit 1; }
done
docker info >/dev/null 2>&1 || { echo "ERROR: Docker daemon is not running."; exit 1; }
```

### WR-03: Step 6 verification failure leaves the pod behind and produces no diagnostics

**File:** `scripts/cluster-setup.sh:98-99`
**Issue:** If registry wiring is broken, the pod never reaches `Succeeded` (it stays `Pending` in `ImagePullBackOff`). `kubectl wait` then exits non-zero after 60s, `errexit` aborts the script, line 99's cleanup never runs, and the only output is a generic `timed out waiting for the condition` — the actual cause (image pull error, wrong hosts.toml, registry not on the kind network) is invisible. The next run's pre-delete (line 89) masks the leak but not the missing diagnostics.
**Fix:**
```bash
if ! kubectl --context kind-kind wait --for=jsonpath='{.status.phase}'=Succeeded pod/registry-verify --timeout=60s; then
  echo "ERROR: registry verification failed — pod status:"
  kubectl --context kind-kind describe pod registry-verify | sed -n '/Events:/,$p'
  kubectl --context kind-kind delete pod registry-verify --ignore-not-found
  exit 1
fi
kubectl --context kind-kind delete pod registry-verify --ignore-not-found
```

## Info

### IN-01: Comment misstates why `pipefail` is omitted; `set -u` also missing

**File:** `scripts/cluster-setup.sh:10-11`
**Issue:** The comment claims `pipefail` "conflicts with the `|| true` idempotency guards" — it does not: `cmd | cmd2 || true` still succeeds under pipefail, since `|| true` applies to the whole pipeline. The *actual* pipefail hazard in this script is line 42, where `grep -q` exiting on first match can SIGPIPE `kind get clusters` and fail the pipeline despite a successful match. The omission is correct; the justification is wrong and will mislead future editors. Separately, `set -u` (nounset) would catch typo'd variable references for free in both scripts.
**Fix:** Correct the comment to cite the `grep -q` SIGPIPE case, and add `set -o nounset` to both scripts.

### IN-02: Scripts hardcode the default cluster name without declaring it in kind-config.yaml

**File:** `infra/kind/kind-config.yaml:3-4`, `scripts/cluster-setup.sh:42`, `scripts/cluster-teardown.sh:18`
**Issue:** `grep -q '^kind$'` and bare `kind delete cluster` both silently depend on the default cluster name `kind`. The config file is the natural single source of truth but omits it, so the coupling is invisible.
**Fix:** Add `name: kind` to `kind-config.yaml` and (optionally) a `cluster_name='kind'` variable in both scripts.

### IN-03: Makefile venv fallback path is not existence-checked

**File:** `Makefile:17`
**Issue:** `VENV_PY=$$([ -x .venv/bin/python ] && echo .venv/bin/python || echo .venv/Scripts/python)` echoes the Windows path unconditionally when the POSIX path is absent. If venv creation half-failed (neither interpreter exists), the next line dies with a confusing `.venv/Scripts/python: No such file or directory` instead of "venv creation failed".
**Fix:** Check both paths and fail with an explicit message when neither exists.

### IN-04: Teardown script has no prerequisite gate (asymmetric with setup)

**File:** `scripts/cluster-teardown.sh:18`
**Issue:** Setup gives a friendly install hint when `kind` is missing; teardown just dies with `kind: command not found` (exit 127) at line 18 under `errexit`, before attempting the docker cleanup that could still succeed.
**Fix:** Mirror the setup gate, or guard `kind delete cluster` with `command -v kind >/dev/null 2>&1 && kind delete cluster` so registry cleanup still runs.

### IN-05: Verification images accumulate on the host

**File:** `scripts/cluster-setup.sh:85-87`
**Issue:** Every setup run leaves `alpine:3.20` and the `localhost:5001/verify:v1` tag on the host Docker daemon (and the pushed blob in the registry volume). Harmless for a local dev loop, but it is silent residue the script creates and never removes.
**Fix:** `docker rmi localhost:5001/verify:v1 >/dev/null 2>&1 || true` after the push, or document the residue in the script header.

---

_Reviewed: 2026-07-05T12:37:20Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
