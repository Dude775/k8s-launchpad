# Phase 02: Cluster Infrastructure - Pattern Map

**Mapped:** 2026-07-05
**Files analyzed:** 4 (3 new, 1 modified)
**Analogs found:** 1 / 4 (Makefile is the only existing file with patterns to copy; no bash scripts or YAML files exist yet in this codebase)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `scripts/cluster-setup.sh` | utility / lifecycle-script | event-driven (sequential orchestration) | `Makefile` (idempotency guard pattern) | partial — same project, different language |
| `scripts/cluster-teardown.sh` | utility / lifecycle-script | event-driven (sequential teardown) | `Makefile` (idempotency guard pattern) | partial — same project, different language |
| `infra/kind/kind-config.yaml` | config | declarative (static) | none | no analog — use RESEARCH.md pattern |
| `Makefile` | config / task-runner | request-response (target invocation) | `Makefile` itself (lines 1-19) | exact — add targets to existing file |

**No bash scripts or YAML files exist in the codebase yet.** The Makefile is the only file with transferable patterns. RESEARCH.md (Pattern 1–5) contains the canonical kind local-registry script verified against official docs — those excerpts are the authoritative source for all new files in this phase.

---

## Pattern Assignments

### `Makefile` (config / task-runner) — MODIFY

**Analog:** `E:\Genspark\k8s-launchpad\Makefile` (existing file, lines 1-19)

**Full existing content** (lines 1-19 — read once, extracted in full):
```makefile
SHELL := /bin/bash
export MSYS_NO_PATHCONV=1

# Interpreter used to CREATE the project venv — override per host:
#   make test PYTHON="py -3.12"    (Windows Git Bash)
#   make test PYTHON=python3.11    (WSL2 / native Linux)
PYTHON ?= python3

# ─── Targets ──────────────────────────────────────────────────────────────────
# Phase 1: test only (cluster-up, build, load, deploy added in Phase 4)
.PHONY: test

## test: create local venv (idempotent), install dev-deps, run pytest with coverage
test:
	cd apps/field-guide-api && \
	{ [ -d .venv ] || $(PYTHON) -m venv .venv; } && \
	VENV_PY=$$([ -x .venv/bin/python ] && echo .venv/bin/python || echo .venv/Scripts/python) && \
	"$$VENV_PY" -m pip install -q -r requirements-dev.txt && \
	"$$VENV_PY" -m pytest
```

**Pattern to copy — .PHONY and target structure** (from lines 11-14):
```makefile
.PHONY: test
## test: <description>
test:
	<recipe using bash>
```
New targets must follow the same `## target: description` comment style and be added to `.PHONY`.

**Pattern to copy — shell variable escaping** (from lines 16-18):
```makefile
VENV_PY=$$([ -x .venv/bin/python ] && ...
"$$VENV_PY" -m pip install ...
```
Use `$$` for shell variables inside recipe lines (single `$` is Makefile variable expansion). The `export MSYS_NO_PATHCONV=1` at line 2 propagates to all child processes including `bash scripts/*.sh` — no need to repeat in target recipes.

**New targets to add** (from RESEARCH.md Pattern 4):
```makefile
.PHONY: cluster-up cluster-down

## cluster-up: create kind cluster + local registry (idempotent)
cluster-up:
	bash scripts/cluster-setup.sh

## cluster-down: tear down kind cluster + registry (idempotent)
cluster-down:
	bash scripts/cluster-teardown.sh
```
Append after the existing `test` target. Update the `.PHONY` comment at line 11 from `test` to `test cluster-up cluster-down`.

---

### `scripts/cluster-setup.sh` (utility / lifecycle-script, event-driven)

**Analog:** No existing bash scripts in codebase. Canonical source: RESEARCH.md Pattern 1 + Pitfall mitigations — verified against official kind docs in the research session.

**Shebang and safety flags** (from RESEARCH.md Pattern 1, line 1-2):
```bash
#!/usr/bin/env bash
set -o errexit
```
`set -o errexit` causes the script to exit immediately on any command failure. Do NOT add `set -o pipefail` with `docker inspect ... || true` guard patterns — they conflict; the `|| true` pattern already handles the idempotency check safely.

**MSYS path conversion guard** (from RESEARCH.md Pitfall 2 and Pitfall 3):
```bash
export MSYS_NO_PATHCONV=1
```
Add at top of script (after `set -o errexit`) so that standalone `bash scripts/cluster-setup.sh` invocations (outside of make) also suppress Git Bash path mangling for `docker run -p "127.0.0.1:5001:5000"` and `/dev/stdin` references.

**Prerequisites check** (from RESEARCH.md Pitfall 1):
```bash
command -v kind >/dev/null 2>&1 || {
  echo "ERROR: kind is not installed."
  echo "Install with: winget install Kubernetes.kind"
  echo "Or download from: https://kind.sigs.k8s.io/dl/v0.32.0/kind-windows-amd64.exe"
  exit 1
}
```
Place before any `kind` or `docker` calls.

**Step 1 — Registry (idempotency guard)** (from RESEARCH.md Pattern 1):
```bash
reg_name='kind-registry'
reg_port='5001'

if [ "$(docker inspect -f '{{.State.Running}}' "${reg_name}" 2>/dev/null || true)" != 'true' ]; then
  docker run \
    -d --restart=always -p "127.0.0.1:${reg_port}:5000" --network bridge --name "${reg_name}" \
    registry:3
fi
```
Binding to `127.0.0.1` (not `0.0.0.0`) is a security requirement — see RESEARCH.md Security Domain.

**Step 2 — Cluster creation (idempotency guard)** (from RESEARCH.md Pattern 1 + Pitfall 6):
```bash
if ! kind get clusters 2>/dev/null | grep -q '^kind$'; then
  kind create cluster --config infra/kind/kind-config.yaml
fi
```
The `grep -q '^kind$'` anchors match the exact cluster name `kind` to avoid false positives if another cluster named e.g. `re-kind` exists.

**Step 3 — hosts.toml injection per node** (from RESEARCH.md Pattern 1):
```bash
REGISTRY_DIR="/etc/containerd/certs.d/localhost:${reg_port}"
for node in $(kind get nodes); do
  docker exec "${node}" mkdir -p "${REGISTRY_DIR}"
  cat <<EOF | docker exec -i "${node}" cp /dev/stdin "${REGISTRY_DIR}/hosts.toml"
[host."http://${reg_name}:5000"]
EOF
done
```
The `hosts.toml` key must be `http://kind-registry:5000` (inner container name and port 5000), NOT `http://localhost:5001` (host-side). Getting this wrong causes silent `ImagePullBackOff` with TLS errors (RESEARCH.md Pitfall 4).

**Step 4 — Network connect (idempotency guard)** (from RESEARCH.md Pattern 1):
```bash
if [ "$(docker inspect -f='{{json .NetworkSettings.Networks.kind}}' "${reg_name}")" = 'null' ]; then
  docker network connect "kind" "${reg_name}"
fi
```

**Step 5 — Discovery ConfigMap** (from RESEARCH.md Pattern 1):
```bash
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

**Step 6 — Registry wiring verification** (from RESEARCH.md Pattern 5):
```bash
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
`--image-pull-policy=Always` forces a real pull from the registry (not Docker cache), making the verification meaningful.

---

### `scripts/cluster-teardown.sh` (utility / lifecycle-script, event-driven)

**Analog:** No existing bash scripts in codebase. Canonical source: RESEARCH.md Pattern 3 — adapted from tilt-dev/kind-local teardown script.

**Shebang, safety flags, and MSYS guard** (same as cluster-setup.sh):
```bash
#!/usr/bin/env bash
set -o errexit
export MSYS_NO_PATHCONV=1
```

**Cluster deletion (natively idempotent)** (from RESEARCH.md Pattern 3):
```bash
reg_name='kind-registry'

# kind delete is natively idempotent — no error if cluster is already absent
kind delete cluster
```

**Registry removal (guarded)** (from RESEARCH.md Pattern 3):
```bash
running="$(docker inspect -f '{{.State.Running}}' "${reg_name}" 2>/dev/null || true)"
if [ "${running}" == 'true' ]; then
  docker stop "${reg_name}"
fi
if docker inspect "${reg_name}" &>/dev/null; then
  docker rm "${reg_name}"
fi
```
Two separate guards: first stops if running, then removes if container exists (handles the case where it was stopped but not removed).

---

### `infra/kind/kind-config.yaml` (config, declarative)

**Analog:** None — no YAML files exist in the codebase. Canonical source: RESEARCH.md Pattern 2 — verified against official kind local-registry docs.

**Full file content** (from RESEARCH.md Pattern 2):
```yaml
# Source: https://kind.sigs.k8s.io/docs/user/local-registry/
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
containerdConfigPatches:
- |-
  [plugins."io.containerd.grpc.v1.cri".registry]
    config_path = "/etc/containerd/certs.d"
```

**No `name:` field** → uses default cluster name `kind`. Avoids needing `--name` in every subsequent kind/kubectl command.

**No `image:` field** → uses kind v0.32.0's default node image (`kindest/node:v1.36.1`). Acceptable for local dev; pin the image digest only if CI reproducibility is required.

**The `config_path` value is critical** — it enables the per-registry `hosts.toml` directory mode that Step 3 of cluster-setup.sh depends on. Without this patch, containerd ignores `hosts.toml` files entirely and the registry wiring silently fails.

---

## Shared Patterns

### MSYS Path Conversion Suppression
**Source:** `E:\Genspark\k8s-launchpad\Makefile` (line 2) and RESEARCH.md Pitfall 2/3
**Apply to:** `Makefile` (already present), `scripts/cluster-setup.sh` (add at top), `scripts/cluster-teardown.sh` (add at top)
```bash
export MSYS_NO_PATHCONV=1
```
The Makefile's `export` propagates to child processes when scripts are called via `bash scripts/...`. Adding it to the scripts themselves ensures standalone invocation also works.

### Idempotency Guard Pattern
**Source:** `E:\Genspark\k8s-launchpad\Makefile` (lines 15-16) — existing test target uses `{ [ -d .venv ] || ... }` pattern
**Apply to:** All steps in `scripts/cluster-setup.sh`, teardown checks in `scripts/cluster-teardown.sh`

The Makefile's idempotency pattern in bash:
```bash
{ [ -d .venv ] || $(PYTHON) -m venv .venv; }
```
The equivalent in the cluster scripts uses `docker inspect` return value checks and `kind get clusters | grep` to gate each operation.

### LF Line Endings
**Source:** `E:\Genspark\k8s-launchpad\.gitattributes` (lines 3, 6, 9)
```
* text=auto eol=lf
*.sh text eol=lf
*.yaml text eol=lf
```
All new files in this phase are covered by the existing `.gitattributes`. No changes needed. CRLF in shell scripts causes `bad interpreter: No such file or directory` under Git Bash and WSL2.

### .gitignore Coverage for Cluster Artifacts
**Source:** `E:\Genspark\k8s-launchpad\.gitignore` (lines 37-39)
```
kubeconfig
*.kubeconfig
.kube/
```
Already in place — `kind create cluster` writes to `~/.kube/config` (system location, not repo), so no repo pollution risk. No changes to `.gitignore` needed in Phase 2.

### .PHONY Target Declaration
**Source:** `E:\Genspark\k8s-launchpad\Makefile` (line 11)
**Apply to:** New `cluster-up` and `cluster-down` Makefile targets
```makefile
.PHONY: test cluster-up cluster-down
```
Every target that does not produce a file artifact must be declared `.PHONY` to prevent make from skipping it if a file with the same name exists.

### Target Recipe Comment Style
**Source:** `E:\Genspark\k8s-launchpad\Makefile` (line 13)
```makefile
## test: create local venv (idempotent), install dev-deps, run pytest with coverage
```
The `## target: description` style is the established convention. New targets must follow it.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `infra/kind/kind-config.yaml` | config | declarative | No YAML files exist in the codebase yet; Phase 1 produced only Python and Makefile artifacts |
| `scripts/cluster-setup.sh` | lifecycle-script | event-driven | No bash scripts exist in the codebase yet; Makefile provides structural guidance only |
| `scripts/cluster-teardown.sh` | lifecycle-script | event-driven | No bash scripts exist in the codebase yet; Makefile provides structural guidance only |

For all three files with no analog, use RESEARCH.md Patterns 1–5 as the authoritative source. They are copied verbatim from the official kind local-registry documentation, verified in the research session.

---

## Metadata

**Analog search scope:** Full repository (`E:\Genspark\k8s-launchpad\`) — all `*.sh`, `*.yaml`, `*.yml`, `Makefile` files
**Files scanned:** Makefile (19 lines), .gitattributes (24 lines), .gitignore (49 lines)
**Shell/YAML files found:** 0 (scripts/ and infra/kind/ contain only .gitkeep placeholders)
**Pattern extraction date:** 2026-07-05
