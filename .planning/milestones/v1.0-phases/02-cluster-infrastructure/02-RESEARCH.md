# Phase 02: Cluster Infrastructure - Research

**Researched:** 2026-07-05
**Domain:** kind (Kubernetes in Docker), local OCI registry, bash scripting, Windows/Git Bash compatibility
**Confidence:** HIGH

---

## Summary

Phase 2 provisions a local kind cluster with a wired local OCI registry (`registry:3`) so that
cluster pods can pull images pushed from the host. The canonical setup script comes directly from
the official kind documentation and has been verified in this session. The five-step pattern
(create registry → create cluster with containerdConfigPatches → patch each node's hosts.toml →
connect registry to kind network → document via ConfigMap) is the only supported approach and must
be reproduced exactly to avoid the "HTTP to HTTPS" pitfall.

**Critical blocker discovered:** `kind` is NOT installed on this machine. It is not on PATH in Git
Bash, not in WinGet packages, not in Chocolatey (which has only `make`). The plan MUST include a
prerequisite-check step and installation instructions before any cluster work can proceed. The
recommended install path on Windows is `winget install Kubernetes.kind` (v0.32.0 confirmed in the
WinGet manifest at microsoft/winget-pkgs). This is a one-time human action, not automatable from
a Makefile target.

**Secondary finding:** The CLAUDE.md states kind v0.32.0 defaults to Kubernetes 1.33.1 — this is
stale. The GitHub releases page confirms kind v0.32.0 (released June 2026) defaults to
`kindest/node:v1.36.1`. This has no impact on Phase 2 behaviour, but the plan should use the
correct digest.

**Primary recommendation:** Create `scripts/cluster-setup.sh` and `scripts/cluster-teardown.sh`
from the official kind local-registry pattern, store the kind cluster config in
`infra/kind/kind-config.yaml`, add `cluster-up` and `cluster-down` Make targets, and include a
built-in registry-verify step inside `cluster-up` that pushes a test image and confirms it pulls
from within a pod.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| kind cluster lifecycle (create/delete) | Host OS (bash script) | Makefile target | `kind` is a host-side CLI; cluster lives in Docker containers on the host |
| OCI registry container lifecycle | Host OS (Docker) | bash script | `registry:3` is a Docker container managed by `docker run/stop/rm` |
| Containerd mirror wiring (hosts.toml) | kind node (via docker exec) | cluster-setup.sh | containerd config lives inside each node container; must be patched after node creation |
| Network bridge between host registry and cluster | Docker networking | cluster-setup.sh | `docker network connect kind kind-registry` makes registry resolvable inside pods |
| Registry discovery (ConfigMap) | Kubernetes (kube-public ns) | kubectl apply | Standard KEP-1755 pattern; consumed by tooling in PRD-3/PRD-4 |
| Image push (build phase) | Host OS (docker push) | Makefile `build`/`load` | Phase 3 responsibility; registry is the interface point |
| Registry wiring verification | Host OS (kubectl + docker) | cluster-setup.sh | End-to-end pull test from within a pod; required by STATE.md research flag |

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CLUS-01 | `make cluster-up` creates a kind cluster with a wired local registry (containerd mirror config on every node, registry on kind network) | Five-step official kind local-registry script verified at kind.sigs.k8s.io; idempotency patterns documented below |
| CLUS-02 | `make cluster-down` tears down cluster and registry cleanly and is safe to re-run | `kind delete cluster` is natively idempotent (no error if cluster absent); registry teardown pattern from tilt-dev/kind-local verified |
</phase_requirements>

---

## Project Constraints (from CLAUDE.md)

- **Tech stack LOCKED:** kind (local cluster), registry:3 (local OCI registry on localhost:5001), Docker (container runtime), Helm 3 (Phase 3) — do not substitute
- **Platform:** Windows host, Git Bash and WSL2 must both work — `SHELL := /bin/bash` and `export MSYS_NO_PATHCONV=1` required in Makefile
- **LF enforcement:** `.gitattributes` already in place (`*.sh text eol=lf`) — all shell scripts written in this phase will get correct endings on checkout
- **No cloud, no cost:** Everything local and free
- **Git:** Small, conventional commits
- **Autonomy:** Pause only for (a) cloud cost, (b) real credentials, (c) locked-decision contradictions
- **Registry image:** `registry:3` (not registry:2 — CLAUDE.md explicitly bans the older tag)
- **Registry port:** `localhost:5001` maps to container port `5000`
- **Bitnami ban:** Out of scope for Phase 2; documented for Phase 3 awareness
- **Shell variables in Makefile:** Use `$$` for dollar signs inside recipe lines
- **Kind command to avoid:** `--atomic` / any Helm flags — Phase 2 has no Helm work
- **Existing Makefile:** Has `SHELL := /bin/bash`, `export MSYS_NO_PATHCONV=1`, and a `test` target — new targets must coexist without breaking `make test`

---

## Standard Stack

### Core

| Tool / Image | Version | Purpose | Source |
|---|---|---|---|
| kind | v0.32.0 | Local Kubernetes cluster | [VERIFIED: kind.sigs.k8s.io, WinGet manifest microsoft/winget-pkgs] |
| registry:3 | latest (Docker Hub official) | Local OCI registry container | [VERIFIED: kind.sigs.k8s.io/docs/user/local-registry/] |
| kindest/node | v1.36.1 (default for kind v0.32.0) | Kubernetes node image used by kind | [VERIFIED: github.com/kubernetes-sigs/kind/releases — June 2026] |
| Docker | 29.5.3 (host-installed, confirmed) | Container runtime for kind and registry | [VERIFIED: `docker version` on this machine] |
| kubectl | 1.34.1 (Docker Desktop bundled) | Apply ConfigMap, run verification pod | [VERIFIED: `kubectl version --client` on this machine] |
| bash | Git Bash / WSL2 | Script runtime | [VERIFIED: environment probe] |

**Note on CLAUDE.md version discrepancies (not blocking):**
- CLAUDE.md states Docker 27.x — actual installed version is **29.5.3**. Compatible with kind v0.32.0.
- CLAUDE.md states Helm 3.21.2 — actual installed is **Helm 4.2.1**. Helm is not used in Phase 2.
- CLAUDE.md states kind defaults to Kubernetes 1.33.1 — kind v0.32.0 actually defaults to **1.36.1**. The info in CLAUDE.md matches kind v0.29.0 (May 2024). This is stale but non-blocking.

### Supporting

| Tool | Purpose | Notes |
|------|---------|-------|
| `make` | Makefile task runner | Chocolatey-installed; existing Makefile has correct headers |
| `docker network` | Bridge registry into kind network | Part of Docker CLI; no extra install needed |
| `kubectl run` / `kubectl wait` | Registry wiring verification (test pod) | Part of kubectl already installed |

### No Python packages or npm packages in this phase.

---

## Package Legitimacy Audit

This phase installs no npm, PyPI, or Cargo packages. The only "packages" are Docker images
consumed at runtime.

| Image | Registry | Age | Official | Disposition |
|-------|----------|-----|----------|-------------|
| `registry:3` | Docker Hub (library/registry) | Official image, maintained by Docker | Yes — [hub.docker.com/\_/registry](https://hub.docker.com/_/registry) | Approved — official Docker library image |
| `kindest/node:v1.36.1` | Docker Hub (kindest/node) | Official kind node image | Yes — maintained by kubernetes-sigs/kind | Approved — used by kind automatically |

**slopcheck status:** slopcheck was not available at research time (`pip install slopcheck` produced
no output; `command -v slopcheck` returned not found). Docker images are not in slopcheck's scope
(npm/pip only). Both images are official and verified via primary sources.

---

## Architecture Patterns

### System Architecture Diagram

```
Developer host (Windows / Git Bash / WSL2)
│
├── make cluster-up
│     │
│     └── scripts/cluster-setup.sh
│           │
│           ├─[Step 1]─ docker run registry:3 → kind-registry container (127.0.0.1:5001:5000)
│           │
│           ├─[Step 2]─ kind create cluster --config infra/kind/kind-config.yaml
│           │              └── kind cluster (Docker containers: control-plane node)
│           │                  containerd configured: config_path=/etc/containerd/certs.d
│           │
│           ├─[Step 3]─ for each kind node:
│           │              docker exec node mkdir -p /etc/containerd/certs.d/localhost:5001
│           │              docker exec -i node cp /dev/stdin hosts.toml
│           │              hosts.toml: [host."http://kind-registry:5000"]
│           │
│           ├─[Step 4]─ docker network connect kind kind-registry
│           │              (pods can resolve kind-registry:5000 inside cluster network)
│           │
│           ├─[Step 5]─ kubectl apply ConfigMap local-registry-hosting (kube-public ns)
│           │
│           └─[Step 6]─ Registry wiring verification (STATE.md research flag):
│                         docker pull alpine:3.20
│                         docker tag alpine:3.20 localhost:5001/test-image:v1
│                         docker push localhost:5001/test-image:v1
│                         kubectl run registry-verify --image=localhost:5001/test-image:v1
│                         kubectl wait --for=condition=Completed pod/registry-verify
│                         kubectl delete pod registry-verify
│
├── make cluster-down
│     └── scripts/cluster-teardown.sh
│           ├── kind delete cluster (idempotent — no error if absent)
│           └── docker stop kind-registry && docker rm kind-registry (guarded by inspect check)
│
└── Artifacts stored in:
      infra/kind/kind-config.yaml   ← kind cluster config (containerdConfigPatches)
      scripts/cluster-setup.sh      ← idempotent setup script
      scripts/cluster-teardown.sh   ← idempotent teardown script
      Makefile                      ← cluster-up, cluster-down targets added
```

### Recommended Project Structure

The directories already exist from Phase 1. Only files need to be added:

```
infra/
└── kind/
    ├── .gitkeep                 # (exists — remove after adding real files)
    └── kind-config.yaml         # NEW: kind cluster config with containerdConfigPatches

scripts/
├── .gitkeep                     # (exists — remove after adding real files)
├── cluster-setup.sh             # NEW: idempotent cluster + registry setup
└── cluster-teardown.sh          # NEW: idempotent cluster + registry teardown

Makefile                         # UPDATE: add cluster-up, cluster-down targets
```

### Pattern 1: Official kind Local Registry Script (five-step)

**What:** Creates registry container → creates cluster with containerd certs.d config → patches
each node's hosts.toml → connects registry to kind network → applies discovery ConfigMap.
**When to use:** Always for this project. This is the only supported pattern.

```bash
#!/usr/bin/env bash
# Source: https://kind.sigs.k8s.io/docs/user/local-registry/
# VERIFIED: fetched from official docs in this research session

set -o errexit

reg_name='kind-registry'
reg_port='5001'

# Step 1 — Create registry if not already running
if [ "$(docker inspect -f '{{.State.Running}}' "${reg_name}" 2>/dev/null || true)" != 'true' ]; then
  docker run \
    -d --restart=always -p "127.0.0.1:${reg_port}:5000" --network bridge --name "${reg_name}" \
    registry:3
fi

# Step 2 — Create kind cluster (skip if already exists)
if ! kind get clusters 2>/dev/null | grep -q '^kind$'; then
  kind create cluster --config infra/kind/kind-config.yaml
fi

# Step 3 — Patch each node's containerd hosts.toml
REGISTRY_DIR="/etc/containerd/certs.d/localhost:${reg_port}"
for node in $(kind get nodes); do
  docker exec "${node}" mkdir -p "${REGISTRY_DIR}"
  cat <<EOF | docker exec -i "${node}" cp /dev/stdin "${REGISTRY_DIR}/hosts.toml"
[host."http://${reg_name}:5000"]
EOF
done

# Step 4 — Connect registry to kind network
if [ "$(docker inspect -f='{{json .NetworkSettings.Networks.kind}}' "${reg_name}")" = 'null' ]; then
  docker network connect "kind" "${reg_name}"
fi

# Step 5 — Document registry (KEP-1755 ConfigMap)
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: local-registry-hosting
  namespace: kube-public
data:
  localRegistryHosting.v1: |
    host: "localhost:${reg_port}"
    help: "https://kind.sigs.k8s.io/docs/user/local-registry/"
EOF
```

### Pattern 2: kind Cluster Config YAML

**What:** Separate YAML file for the kind cluster configuration, enabling containerd certs.d mode.
**When to use:** Pass via `kind create cluster --config infra/kind/kind-config.yaml`.

```yaml
# Source: https://kind.sigs.k8s.io/docs/user/local-registry/
# VERIFIED: fetched from official docs in this research session
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
containerdConfigPatches:
- |-
  [plugins."io.containerd.grpc.v1.cri".registry]
    config_path = "/etc/containerd/certs.d"
```

**No `name:` field** → uses default cluster name `kind`. Acceptable for a single-cluster local dev
environment; avoids having to pass `--name` to every subsequent `kind` command.

**No `image:` field** → uses kind v0.32.0's default node image (`kindest/node:v1.36.1`). Pinning
the digest is recommended for CI reproducibility but optional for local dev.

### Pattern 3: Idempotent cluster-down

**What:** Tear down cluster and registry in a way that can be re-run without errors.
**When to use:** `make cluster-down` target.

```bash
#!/usr/bin/env bash
# Source: adapted from tilt-dev/kind-local teardown script
# VERIFIED: tilt-dev/kind-local/blob/master/teardown-kind-with-registry.sh

set -o errexit

reg_name='kind-registry'

# Delete cluster (kind delete is natively idempotent — no error if absent)
kind delete cluster

# Remove registry (guarded — no error if already stopped/removed)
running="$(docker inspect -f '{{.State.Running}}' "${reg_name}" 2>/dev/null || true)"
if [ "${running}" == 'true' ]; then
  docker stop "${reg_name}"
fi
if docker inspect "${reg_name}" &>/dev/null; then
  docker rm "${reg_name}"
fi
```

### Pattern 4: Makefile targets

**What:** Add `cluster-up` and `cluster-down` to the existing Makefile without breaking `test`.

```makefile
# Add to existing Makefile — existing SHELL and MSYS_NO_PATHCONV headers already present

.PHONY: cluster-up cluster-down

## cluster-up: create kind cluster + local registry (idempotent)
cluster-up:
	bash scripts/cluster-setup.sh

## cluster-down: tear down kind cluster + registry (idempotent)
cluster-down:
	bash scripts/cluster-teardown.sh
```

**Note:** `bash` is used explicitly (not `./scripts/…`) because the existing Makefile uses
`SHELL := /bin/bash` and all script invocations follow the `bash <path>` pattern. The
`export MSYS_NO_PATHCONV=1` at the Makefile top-level propagates to child bash processes.

### Pattern 5: Registry wiring verification (STATE.md research flag)

**What:** Proves end-to-end: push from host → pull from within cluster pod.
**When to use:** At the end of `cluster-setup.sh` (or as a separate `make registry-verify` target).

```bash
# Verification block — run after Step 5 in cluster-setup.sh
echo "==> Verifying registry wiring..."
docker pull alpine:3.20 --quiet
docker tag alpine:3.20 localhost:5001/verify:v1
docker push localhost:5001/verify:v1

kubectl run registry-verify \
  --image=localhost:5001/verify:v1 \
  --restart=Never \
  --image-pull-policy=Always \
  -- echo "registry-ok"

kubectl wait --for=condition=Completed pod/registry-verify --timeout=60s
kubectl delete pod registry-verify --ignore-not-found

echo "==> Registry wiring verified OK"
```

`--image-pull-policy=Always` forces a real pull (not cached) which is required for a meaningful
verification. `alpine:3.20` (~7 MB) is fast to pull and guaranteed to have a runnable shell image
that exits cleanly after `echo`.

### Anti-Patterns to Avoid

- **Using `registry:2` instead of `registry:3`:** CLAUDE.md explicitly bans this. Official kind docs
  now reference registry:3.
- **Binding registry to `0.0.0.0:5001`:** The official script binds to `127.0.0.1:5001` — host-only.
  Never expose the unauthenticated registry to the network.
- **Skipping idempotency guards:** Running `kind create cluster` when a cluster already exists prints
  a "node(s) already exist" error and exits non-zero, breaking the script. Always check first.
- **Hardcoding the cluster name:** The default name `kind` is used; do not add `--name` flags unless
  the project decides to rename the cluster (locked as `kind` for now).
- **Applying `--atomic` or `--rollback-on-failure`:** Helm flags, not relevant to Phase 2.
- **Putting kubeconfig in git:** `.gitignore` already covers `kubeconfig` and `.kube/` — no action
  needed, but verify during plan execution.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Registry-to-cluster networking | Custom DNS or iptables rules | Official `docker network connect kind` + `hosts.toml` pattern | containerd's `certs.d` config_path mode is the only supported pattern for kind v0.20+; custom DNS breaks |
| Containerd config injection | Modifying containerd.toml directly | `containerdConfigPatches` in kind cluster config YAML | Kind manages containerd config on nodes; direct edits are overwritten at cluster creation |
| Registry container | Custom image build | Official `registry:3` Docker Hub image | Docker-maintained, battle-tested, OCI-compliant; zero config for basic pull/push |
| Cluster teardown ordering | Process kill / force-remove | `kind delete cluster` then `docker stop/rm` | kind delete handles node network cleanup; force-removing containers leaves dangling networks |

**Key insight:** Every piece of the registry wiring pattern exists in the official kind local-registry
docs. Any deviation (skipping nodes, wrong TOML format, wrong network name) will silently fail at
image pull time with an opaque `ImagePullBackOff` error.

---

## Common Pitfalls

### Pitfall 1: kind Not on PATH

**What goes wrong:** `make cluster-up` fails immediately with `bash: kind: command not found`.
**Why it happens:** kind is not installed on this machine — confirmed by environment probe.
**How to avoid:** Plan must include a prerequisite-check task. The script should detect kind absence
and print a clear error with install instructions rather than a confusing bash error.
**Warning signs:** `command -v kind` returns nothing in Git Bash.
**Installation:** `winget install Kubernetes.kind` (WinGet v0.32.0 confirmed). Or download binary
from kind.sigs.k8s.io/dl/v0.32.0/kind-windows-amd64.exe and place in PATH.

```bash
# Add at top of cluster-setup.sh
command -v kind >/dev/null 2>&1 || {
  echo "ERROR: kind is not installed."
  echo "Install with: winget install Kubernetes.kind"
  echo "Or download from: https://kind.sigs.k8s.io/dl/v0.32.0/kind-windows-amd64.exe"
  exit 1
}
```

### Pitfall 2: MSYS Path Conversion Eating Docker Port Specs

**What goes wrong:** In Git Bash, `docker run -p "127.0.0.1:5001:5000"` can be mangled by MSYS2's
POSIX-to-Windows path converter, turning `127.0.0.1` into a Windows-style path prefix.
**Why it happens:** Git Bash converts any string matching POSIX path patterns to Windows paths before
passing to native executables.
**How to avoid:** The existing Makefile already has `export MSYS_NO_PATHCONV=1` which propagates to
child processes. Scripts called via `bash scripts/…` from make inherit this. For standalone script
use, add `export MSYS_NO_PATHCONV=1` at the top of each script.
**Warning signs:** `docker: invalid reference format` or unexpected IP addresses in `docker ps`.

### Pitfall 3: /dev/stdin Path Conversion (hosts.toml injection)

**What goes wrong:** `docker exec -i "${node}" cp /dev/stdin "${REGISTRY_DIR}/hosts.toml"` — Git
Bash may attempt to convert `/dev/stdin` to a Windows path.
**Why it happens:** Same MSYS2 path conversion as Pitfall 2, but for `/dev/` paths.
**How to avoid:** `MSYS_NO_PATHCONV=1` suppresses this. Confirmed in community documentation as
the standard fix. The full Makefile `export` covers this when run via `make`.
**Warning signs:** `cp: /dev/stdin: No such file or directory` inside the node container.

### Pitfall 4: HTTP vs HTTPS — "server gave HTTP response to HTTPS client"

**What goes wrong:** Pod gets `ImagePullBackOff` with event message "server gave HTTP response to
HTTPS client" when pulling from `localhost:5001`.
**Why it happens:** The `hosts.toml` entry is missing or incorrect, so containerd defaults to HTTPS
and gets an HTTP response from the unauthenticated registry.
**How to avoid:** The `hosts.toml` content must be exactly:
```toml
[host."http://kind-registry:5000"]
```
Note: the key is `http://kind-registry:5000` (inner container name and port), NOT
`http://localhost:5001` (host-side address).
**Warning signs:** `ImagePullBackOff` immediately after push; `kubectl describe pod` shows TLS error.

### Pitfall 5: Registry Not Connected to kind Network

**What goes wrong:** Pods get `ErrImagePull` because `kind-registry:5000` is not resolvable inside
the cluster.
**Why it happens:** The registry container was created on the `bridge` network, not the `kind`
network. Pods inside the cluster cannot route to `bridge` network containers.
**How to avoid:** Step 4 of the setup script (`docker network connect kind kind-registry`) is
mandatory. The idempotency check (`{{json .NetworkSettings.Networks.kind}}` == `null`) prevents
duplicate connect attempts.
**Warning signs:** `kubectl describe pod` shows DNS resolution failure for `kind-registry`.

### Pitfall 6: "Node already exists" Error on Re-run

**What goes wrong:** `kind create cluster` errors with "node(s) already exist for a cluster with
the name 'kind'" if the cluster is already running.
**Why it happens:** `kind create cluster` is not idempotent by default.
**How to avoid:** Guard cluster creation:
```bash
if ! kind get clusters 2>/dev/null | grep -q '^kind$'; then
  kind create cluster --config infra/kind/kind-config.yaml
fi
```
**Warning signs:** Non-zero exit code from `kind create cluster` in a re-run scenario.

### Pitfall 7: kubeconfig Context Not Set After Cluster Creation

**What goes wrong:** `kubectl` commands after `kind create cluster` fail because kubeconfig was not
updated or the context is wrong.
**Why it happens:** `kind create cluster` does update `~/.kube/config` automatically, but on Windows
the path resolution can differ between Git Bash and CMD contexts.
**How to avoid:** Add explicit context-set after cluster creation:
```bash
kind export kubeconfig --name kind
```
or use `--kubeconfig` flags. In practice, `kind create cluster` sets the context automatically; if
not, `kubectl config use-context kind-kind` (the generated context name).
**Warning signs:** `kubectl get nodes` returns "connection refused" immediately after cluster up.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| kind | CLUS-01, CLUS-02 | **NO** | — | No fallback — must install before plan executes |
| Docker (daemon) | CLUS-01, CLUS-02, registry | Yes | 29.5.3 | — |
| kubectl | ConfigMap apply, verification | Yes | 1.34.1 (Docker Desktop) | — |
| Helm | Phase 2 | N/A | 4.2.1 installed | Not needed until Phase 3 |
| make | Makefile targets | Yes | Chocolatey-installed | — |
| bash (Git Bash) | Script runtime | Yes | Git Bash present | WSL2 as alternative |
| registry:3 image | CLUS-01 | Not pulled yet | latest | Pulled automatically by `docker run` |
| alpine:3.20 image | Verification step | Not pulled yet | 3.20 | Pulled automatically by `docker pull` |

**Missing dependencies with no fallback:**
- **kind** — Plan MUST include a prerequisite-check + installation guidance task (human action:
  `winget install Kubernetes.kind`) before any cluster-related tasks execute.

**Missing dependencies with fallback:**
- None identified beyond kind.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---|---|---|---|
| `registry:2` | `registry:3` | ~2023 | registry:3 is the recommended image; registry:2 still works but deprecated |
| inline containerd config in kind config | `config_path = "/etc/containerd/certs.d"` + separate `hosts.toml` per registry | kind v0.20+ (containerd 1.5+) | Cleaner; supports multiple registries; is the only supported path in kind v0.32.0 |
| Single global `[plugins.registry.mirrors]` patch | Per-registry `hosts.toml` files | containerd 2.x | Decoupled; easier to add mirrors without touching global config |
| HAProxy for multi-control-plane LB | Envoy (`envoyproxy/envoy:v1.36.2`) | kind v0.32.0 | Only relevant for HA clusters; single-node (Phase 2) is unaffected |
| kubeadm v1beta3 patch format | kubeadm v1beta4 | kind v0.32.0 / K8s 1.36 | Only relevant if `kubeadmConfigPatches` are used; Phase 2 does not use them |

**Deprecated:**
- `registry:2`: Still runs but kind docs explicitly reference `registry:3` — do not use
- `REGISTRY_MIRRORS` containerd config style: Replaced by `config_path`/`hosts.toml` — do not use

---

## Security Domain

**security_enforcement:** not set in config.json → treated as enabled.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---|---|---|
| V2 Authentication | No | Registry is unauthenticated (local only; bound to 127.0.0.1) |
| V3 Session Management | No | No sessions; CLI-driven |
| V4 Access Control | Partially | Registry bound to 127.0.0.1 only (not exposed to LAN) |
| V5 Input Validation | No | No user input in cluster scripts; values are hardcoded constants |
| V6 Cryptography | No | HTTP between node and registry is intentional (loopback via kind network) |

### Known Threat Patterns for kind/Registry Stack

| Pattern | STRIDE | Standard Mitigation |
|---|---|---|
| Kubeconfig credential exposure | Information Disclosure | `.gitignore` already covers `kubeconfig` and `.kube/` — do not commit |
| Registry exposed to LAN | Elevation of Privilege | Bind with `127.0.0.1:5001:5000` (official script does this) — never `0.0.0.0` |
| Malicious image in local registry | Tampering | Only a risk if a 3rd party pushes to localhost:5001; acceptable for local dev |
| kind node container escape | Elevation of Privilege | Running kind locally as a dev tool; Docker Desktop's VM boundary provides isolation |

**Security verdict for Phase 2:** The official kind local-registry pattern is safe for local
development. The only actionable control is confirming the `-p "127.0.0.1:5001:5000"` binding in
the `docker run` command — never change it to `0.0.0.0`.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | kind v0.32.0 available via `winget install Kubernetes.kind` (v0.32.0 confirmed in WinGet manifest listing but not installed locally) | Environment Availability | If WinGet installs v0.31.0 instead, the cluster will default to K8s 1.35 — still works for Phase 2 |
| A2 | `winget` is executable from Git Bash (it's a Windows native binary, should be on PATH) | Environment Availability | If winget is not on Git Bash PATH, user must run install from PowerShell/cmd manually |
| A3 | Docker Desktop on this machine has the kind bridge networking requirements satisfied (no WSL2 cgroup issues) | Common Pitfalls | If WSL2 cgroup v1 deprecation causes container startup issues, user must follow wsl-cgroupsv2 community fix |
| A4 | `alpine:3.20` Docker Hub image is usable for the verification step | Architecture Patterns | Alpine is official Docker library image; extremely unlikely to be unavailable |

---

## Open Questions (RESOLVED)

1. **Cluster name: "kind" (default) vs "k8s-launchpad"?**
   - RESOLVED: use default `kind` (per recommendation below; plans implement this)
   - What we know: Default name is `kind`; no name is specified in CLAUDE.md; using default avoids
     passing `--name` to every subsequent kind command
   - What's unclear: Whether the project wants a named cluster for multi-cluster environments
   - Recommendation: Use default `kind` for Phase 2; PRD-3 can introduce named clusters if needed.
     The planner can decide without blocking research.

2. **Verification step: inline in cluster-setup.sh or separate Makefile target?**
   - RESOLVED: inline as the final blocking step of cluster-setup.sh (plans implement this)
   - What we know: STATE.md research flag says "verify registry wiring with a test image pull from
     within the cluster before proceeding to Phase 3"
   - What's unclear: Whether verification should be mandatory (blocking cluster-up) or optional
   - Recommendation: Inline in cluster-setup.sh as the final step so `make cluster-up` is
     self-verifying; a failed verification exits non-zero and prevents Phase 3.

3. **kind installation automation vs manual prerequisite**
   - RESOLVED: prerequisite-check gate in cluster-setup.sh with install instructions; no auto-install (plans implement this)
   - What we know: kind is not installed; winget is available; Makefile cannot reliably run winget
     in headless CI context; kind install is a one-time developer action
   - Recommendation: Add prerequisite-check at top of cluster-setup.sh that exits with a clear
     error and install instructions; document in README (Phase 4). Do NOT auto-install from make.

---

## Sources

### Primary (HIGH confidence)
- [kind.sigs.k8s.io/docs/user/local-registry/](https://kind.sigs.k8s.io/docs/user/local-registry/) — canonical five-step setup script, hosts.toml format, registry:3 image name, port 5001 mapping
- [kind.sigs.k8s.io/docs/user/quick-start/](https://kind.sigs.k8s.io/docs/user/quick-start/) — kind installation methods on Windows (WinGet, Chocolatey, binary download)
- [github.com/kubernetes-sigs/kind/releases](https://github.com/kubernetes-sigs/kind/releases) — kind v0.32.0 release date (June 2026), default node image kindest/node:v1.36.1
- [github.com/microsoft/winget-pkgs/tree/master/manifests/k/Kubernetes/kind](https://github.com/microsoft/winget-pkgs/tree/master/manifests/k/Kubernetes/kind) — WinGet manifest confirms v0.32.0 available
- `docker version` and `kubectl version --client` — verified installed tools on this machine

### Secondary (MEDIUM confidence)
- [github.com/tilt-dev/kind-local/blob/master/teardown-kind-with-registry.sh](https://github.com/tilt-dev/kind-local/blob/master/teardown-kind-with-registry.sh) — cluster-down pattern
- [github.com/kubernetes-sigs/kind/issues/3918](https://github.com/kubernetes-sigs/kind/issues/3918) — HTTP/HTTPS mismatch pitfall documentation
- [Docker and Git Bash / MSYS2 on Windows path conversion](https://gist.github.com/borekb/cb1536a3685ca6fc0ad9a028e6a959e3) — MSYS_NO_PATHCONV pattern

### Tertiary (LOW confidence — training data)
- WSL2 cgroup v2 deprecation warning (kind v0.32.0 release notes mention cgroup v1 deprecation)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified via official kind docs and live tool probes
- Architecture: HIGH — derived directly from official kind local-registry script
- Pitfalls: HIGH — pitfalls 1 and 2 verified by live environment; pitfalls 3–7 verified via official docs/issues
- Environment: HIGH — verified via direct tool probes on this machine

**Research date:** 2026-07-05
**Valid until:** 2026-08-05 (kind releases infrequently; registry:3 and the five-step pattern are stable)
