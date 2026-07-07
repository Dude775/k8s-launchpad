---
phase: 02-cluster-infrastructure
plan: 01
subsystem: cluster-lifecycle
tags: [kind, registry, kubernetes, bash, makefile, infrastructure]
dependency_graph:
  requires: []
  provides: [infra/kind/kind-config.yaml, scripts/cluster-setup.sh, scripts/cluster-teardown.sh, Makefile:cluster-up, Makefile:cluster-down]
  affects: [Makefile]
tech_stack:
  added: [kind v0.32.0, registry:3, kindest/node:v1.36.1]
  patterns: [idempotent-bash-guards, containerd-certs.d-hosts.toml, kind-local-registry-official-pattern]
key_files:
  created:
    - infra/kind/kind-config.yaml
    - scripts/cluster-setup.sh
    - scripts/cluster-teardown.sh
  modified:
    - Makefile
key_decisions:
  - registry bound to 127.0.0.1:5001 only (loopback) — security control from threat register T-02-01
  - set -o pipefail omitted from scripts — conflicts with || true idempotency guards
  - verification step inline in cluster-setup.sh (not a separate target) — makes make cluster-up self-verifying
  - no name/image fields in kind-config.yaml — uses kind default cluster name and node image
metrics:
  duration: 6m
  completed: "2026-07-05T08:03:01Z"
  tasks_completed: 3
  files_created: 3
  files_modified: 1
---

# Phase 2 Plan 1: Cluster Infrastructure Artifacts Summary

**One-liner:** Six-step kind + registry:3 wiring with loopback-only binding, hosts.toml containerd patch per node, and self-verifying push+pull-from-pod at cluster-up time.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | kind cluster config (containerd certs.d mode) | c87dbae | infra/kind/kind-config.yaml (created), infra/kind/.gitkeep (removed) |
| 2 | cluster-setup.sh — six-step wiring + registry verification | 1d8e494 | scripts/cluster-setup.sh (created) |
| 3 | cluster-teardown.sh + Makefile cluster-up/cluster-down | 773e6b2 | scripts/cluster-teardown.sh (created), scripts/.gitkeep (removed), Makefile (modified) |

## Artifacts

### infra/kind/kind-config.yaml
kind v1alpha4 Cluster config with `containerdConfigPatches` setting `config_path = "/etc/containerd/certs.d"`. This is the load-bearing config that enables per-registry `hosts.toml` directory mode in containerd — without it, Step 3 of cluster-setup.sh silently fails and image pulls from the local registry return TLS errors.

No `name:` field (uses default cluster name `kind`), no `image:` field (uses kind v0.32.0 default `kindest/node:v1.36.1`).

### scripts/cluster-setup.sh (99 lines)
Idempotent six-step setup script following the official kind local-registry pattern:
1. **Registry** — starts `registry:3` bound to `127.0.0.1:5001:5000` (loopback only); guarded by `docker inspect`
2. **Cluster** — `kind create cluster --config infra/kind/kind-config.yaml`; guarded by `kind get clusters | grep -q '^kind$'`
3. **hosts.toml** — injects `[host."http://kind-registry:5000"]` into each node's containerd certs.d directory via `docker exec`
4. **Network** — connects `kind-registry` to the `kind` docker network; guarded by `NetworkSettings.Networks.kind` == `null` check
5. **ConfigMap** — applies `local-registry-hosting` in `kube-public` namespace (KEP-1755)
6. **Verification** — pushes `alpine:3.20` as `localhost:5001/verify:v1`, runs a pod with `--image-pull-policy=Always`, waits for `condition=Completed`, exits non-zero on failure

Security controls enforced:
- `-p "127.0.0.1:${reg_port}:5000"` — never `0.0.0.0`
- `export MSYS_NO_PATHCONV=1` — suppresses Git Bash path mangling for port specs and `/dev/stdin`
- Prerequisite gate: exits with `winget install Kubernetes.kind` instructions if kind not on PATH

### scripts/cluster-teardown.sh (35 lines)
Idempotent teardown:
- `kind delete cluster` — natively idempotent, no error if cluster absent
- `docker stop kind-registry` — guarded by running-state inspect
- `docker rm kind-registry` — guarded by container-existence inspect

### Makefile
Extended `.PHONY` to include `cluster-up cluster-down`. Added two targets:
```makefile
cluster-up:
    bash scripts/cluster-setup.sh

cluster-down:
    bash scripts/cluster-teardown.sh
```
Existing `SHELL := /bin/bash`, `export MSYS_NO_PATHCONV=1`, `PYTHON ?=` header, and `test` target preserved byte-for-byte.

## Verification Results

All automated checks passed:
- `bash -n scripts/cluster-setup.sh` — exit 0
- `bash -n scripts/cluster-teardown.sh` — exit 0
- `make -n cluster-up` → prints `bash scripts/cluster-setup.sh`
- `make -n cluster-down` → prints `bash scripts/cluster-teardown.sh`
- `make -n test` — not regressed (VENV_PY pattern intact)
- No `0.0.0.0` binding in cluster-setup.sh
- All files have LF line endings (gitattributes: `*.sh text eol=lf`, `*.yaml text eol=lf`)
- kind-config.yaml contains `kind: Cluster`, `apiVersion: kind.x-k8s.io/v1alpha4`, and `config_path = "/etc/containerd/certs.d"`

Runtime verification (actual cluster + pod pull) deferred to plan 02 per plan specification.

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| `set -o pipefail` omitted from both scripts | Conflicts with `... \|\| true` idempotency guards; errexit alone is sufficient |
| Verification inline in cluster-setup.sh, not a separate Makefile target | Makes `make cluster-up` self-verifying; failed wiring exits non-zero before Phase 3 can start |
| No `name:` or `image:` in kind-config.yaml | Uses kind default cluster name `kind`; avoids `--name` on every subsequent kind/kubectl call |
| `export MSYS_NO_PATHCONV=1` in each script header | Ensures standalone `bash scripts/cluster-setup.sh` (outside of make) also suppresses Git Bash path mangling |
| `alpine:3.20` for verification image | Official Docker library image ~7MB; guaranteed runnable shell; exits cleanly after `echo` |

## Deviations from Plan

None — plan executed exactly as written. All six steps, all idempotency guards, and the loopback-only binding are present.

## Known Stubs

None. All scripts implement real behavior; no placeholder values or TODO markers.

## Threat Flags

No new security surface beyond what is covered in the plan's threat model. All T-02-01 mitigations confirmed:
- Loopback-only registry binding enforced and verified by grep check
- kubeconfig written to `~/.kube/config` (system path, not repo)
- HTTP node-to-registry traffic is intentional (loopback-scoped kind docker network)

## Self-Check: PASSED

- [x] `infra/kind/kind-config.yaml` exists
- [x] `scripts/cluster-setup.sh` exists (99 lines, min 45)
- [x] `scripts/cluster-teardown.sh` exists (35 lines, min 12)
- [x] `infra/kind/.gitkeep` removed
- [x] `scripts/.gitkeep` removed
- [x] Makefile has `.PHONY: test cluster-up cluster-down`
- [x] Commits c87dbae, 1d8e494, 773e6b2 exist in git log
