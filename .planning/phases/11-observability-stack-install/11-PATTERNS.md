# Phase 11: Observability Stack Install - Pattern Map

**Mapped:** 2026-07-16
**Files analyzed:** 4 (2 new scripts, 1 new values file, 1 modified doc)
**Analogs found:** 4 / 4

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|------------------|----------------|
| `scripts/observability-up.sh` | utility (infra orchestration script) | event-driven (imperative install + self-verify) | `scripts/cluster-setup.sh` | exact |
| `scripts/observability-down.sh` | utility (infra orchestration script) | event-driven (imperative teardown + self-verify) | `scripts/cluster-teardown.sh` | exact |
| `infra/observability/values-trimmed.yaml` | config (Helm values) | CRUD (declarative desired-state config, no code) | `charts/field-guide-api/values.yaml` | role-match (same "conservative resources + committed local-dev secret" convention, different chart) |
| `docs/known-limitations.md` (append) | doc (accepted-risk record) | transform (append new entries, no structural change) | `docs/known-limitations.md` (existing MongoDB dev-password + CRD-adjacent sections) | exact (same file, additive edit) |

No Makefile changes in this phase (explicitly deferred to Phase 14 per CONTEXT.md) — `Makefile` is read-only reference context only, not a file this phase modifies.

## Pattern Assignments

### `scripts/observability-up.sh` (utility, event-driven orchestration)

**Analog:** `scripts/cluster-setup.sh` (full file, 133 lines — read whole, well under 2,000-line threshold)

**Header/idempotency-guard pattern** (lines 1-20):
```bash
#!/usr/bin/env bash
# scripts/cluster-setup.sh
# Idempotent kind cluster + local registry setup with end-to-end wiring verification.
# Source: https://kind.sigs.k8s.io/docs/user/local-registry/
#
# Usage:  bash scripts/cluster-setup.sh
#         make cluster-up

set -o errexit
# NOTE: set -o pipefail is intentionally omitted — it conflicts with the
# "|| true" idempotency guards used throughout this script.

export MSYS_NO_PATHCONV=1   # suppress Git Bash POSIX-to-Windows path mangling

reg_name='kind-registry'
reg_port='5001'
# Pin every kubectl call to the kind cluster's context so an idempotent
# re-run (cluster already exists, no context switch) can never mutate
# whatever cluster the user's kubeconfig currently points at.
KCTX='--context=kind-kind'
```
Copy verbatim: `set -o errexit` (no `pipefail`), `export MSYS_NO_PATHCONV=1`, the `KCTX='--context=kind-kind'` pin on every kubectl/helm invocation, and the header comment block style (`# scripts/<name>.sh`, one-line purpose, `Usage:` block naming both the raw `bash` invocation and the `make` target it backs).

**Prerequisite gate pattern** (lines 22-40):
```bash
command -v kind >/dev/null 2>&1 || {
  echo "ERROR: kind is not installed or not on PATH."
  echo "Install with: winget install Kubernetes.kind"
  echo "Or download from: https://kind.sigs.k8s.io/dl/v0.32.0/kind-windows-amd64.exe"
  exit 1
}
for tool in docker kubectl; do
  command -v "$tool" >/dev/null 2>&1 || {
    echo "ERROR: $tool is not installed or not on PATH."
    exit 1
  }
done
docker info >/dev/null 2>&1 || {
  echo "ERROR: Docker daemon is not running."
  exit 1
}
```
For `observability-up.sh`, add `helm` to the tool loop (`for tool in docker kubectl helm`) — same fail-fast-before-any-mutation structure.

**Idempotent step pattern with "already exists — skipping" branch** (lines 42-61, registry step):
```bash
echo "==> Step 1: Ensuring local registry is running..."
if [ "$(docker inspect -f '{{.State.Running}}' "${reg_name}" 2>/dev/null || true)" != 'true' ]; then
  if docker inspect "${reg_name}" >/dev/null 2>&1; then
    docker start "${reg_name}"
    echo "    Existing registry container started."
  else
    docker run -d --restart=always ...
    echo "    Registry started."
  fi
else
  echo "    Registry already running — skipping."
fi
```
Map this shape onto `helm repo add` (idempotent by nature, guard with `|| true`) and `helm upgrade --install` (natively idempotent — no branch needed, `upgrade --install` IS the idempotency guard).

**Self-verification-over-trusting-exit-code pattern** (lines 106-131, registry push/pull round-trip):
```bash
echo "==> Step 6: Verifying registry wiring (push from host → pull from pod)..."
...
kubectl ${KCTX} run registry-verify --image=... --restart=Never --image-pull-policy=Always -- echo "registry-ok"

if ! kubectl ${KCTX} wait --for=jsonpath='{.status.phase}'=Succeeded pod/registry-verify --timeout=60s; then
  echo "ERROR: registry verification failed — pod status:"
  kubectl ${KCTX} describe pod registry-verify | sed -n '/Events:/,$p'
  kubectl ${KCTX} delete pod registry-verify --ignore-not-found
  exit 1
fi
kubectl ${KCTX} delete pod registry-verify --ignore-not-found

echo "==> Registry wiring verified OK"
echo "==> cluster-setup complete — cluster is ready."
```
For `observability-up.sh`, the analogous self-check is `kubectl wait --for=condition=Ready pod --all -n observability --timeout=Ns` followed by `make smoke && make smoke-launchpad` (per D-06) — same "don't trust the tool's own exit code alone" discipline, same on-failure `describe`/diagnostic-dump-then-exit-1 shape, same final `echo "==> <script-name> complete."` sign-off line.

**Preflight capacity check** — new to this phase, no direct analog in `cluster-setup.sh`, but RESEARCH.md's Code Examples section already provides a live-verified sketch (lines 495-511 of `11-RESEARCH.md`):
```bash
ALLOCATABLE_KI=$(kubectl --context=kind-kind get nodes -o jsonpath='{.items[0].status.allocatable.memory}' | tr -d 'Ki')
EXISTING_REQ_KI=$(kubectl --context=kind-kind get pods -A -o jsonpath='{range .items[*].spec.containers[*]}{.resources.requests.memory}{"\n"}{end}' | ...)
TRIMMED_STACK_REQ_KI=<sum of the values-trimmed.yaml requests>
if [ $(( ALLOCATABLE_KI - EXISTING_REQ_KI )) -lt "$TRIMMED_STACK_REQ_KI" ]; then
  echo "ERROR: insufficient memory headroom for the observability stack."
  echo "  ACTION: raise Docker Desktop's memory allocation (Settings > Resources > Memory) to at least <N> GB and retry."
  exit 1
fi
```
Use `kubectl get nodes -o jsonpath` (the project's own established JSONPath convention, already used in `cluster-setup.sh`'s registry-verification step) — not a new `jq` dependency.

**Helm install command** (from RESEARCH.md Pattern 1, mirrors `Makefile`'s `deploy`/`deploy-launchpad` `--wait --timeout` idiom at `Makefile:60-63`, `Makefile:111-114`):
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
helm repo update prometheus-community

helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --version 87.16.1 \
  --namespace observability --create-namespace \
  -f infra/observability/values-trimmed.yaml \
  --wait --timeout 300s
```
Note: `Makefile:60-63` (`deploy:`) uses `--wait --timeout 180s` with no `--atomic` — same flag discipline applies here, just a longer timeout (300s) because this is a first-time CRD install + 4-pod rollout, not a single-app upgrade.

---

### `scripts/observability-down.sh` (utility, event-driven orchestration)

**Analog:** `scripts/cluster-teardown.sh` (full file, 36 lines)

**Full idempotent-teardown pattern** (lines 1-35):
```bash
#!/usr/bin/env bash
# scripts/cluster-teardown.sh
# Idempotent kind cluster + local registry teardown.
# Safe to re-run — each step is guarded against "already gone" errors.
#
# Usage:  bash scripts/cluster-teardown.sh
#         make cluster-down

set -o errexit
export MSYS_NO_PATHCONV=1   # suppress Git Bash POSIX-to-Windows path mangling

reg_name='kind-registry'

echo "==> Deleting kind cluster..."
kind delete cluster
echo "    Cluster deleted (or was already absent)."

echo "==> Removing local registry container..."
running="$(docker inspect -f '{{.State.Running}}' "${reg_name}" 2>/dev/null || true)"
if [ "${running}" = 'true' ]; then
  docker stop "${reg_name}"
  echo "    Registry stopped."
fi
if docker inspect "${reg_name}" &>/dev/null; then
  docker rm "${reg_name}"
  echo "    Registry container removed."
else
  echo "    Registry container not found — skipping."
fi

echo "==> cluster-teardown complete."
```
Map directly onto:
1. `helm uninstall kube-prometheus-stack -n observability` — natively idempotent, same as `kind delete cluster`'s "no error if already absent" property (D-01: intentionally does NOT touch CRDs — this is the one place this script's behavior *diverges* from `cluster-teardown.sh`'s "remove everything" instinct; do not add CRD deletion logic).
2. `kubectl delete namespace observability --ignore-not-found` (D-02) — same "guarded against already-gone" idiom as the registry `docker inspect ... || true` checks, using kubectl's own `--ignore-not-found` flag instead of a manual existence check (simpler, equally safe).
3. Close with `make smoke && make smoke-launchpad` (D-03) instead of `cluster-teardown.sh`'s implicit "nothing left to verify" — this script has an explicit post-teardown health re-check that `cluster-teardown.sh` doesn't need (it's tearing down the pods being checked; here, the apps must still be running afterward).
4. Same closing sign-off line style: `echo "==> observability-down complete."`

**Double-safe teardown / double-run idempotency precedent (per Claude's Discretion note):** `cluster-teardown.sh`'s registry-removal block (lines 22-33) already demonstrates the two-step "stop only if running, then remove only if it still exists" pattern — apply this same two-condition guard shape to `helm uninstall` (naturally idempotent — Helm itself no-ops with a "release not found" message rather than erroring... verify this at implementation time and wrap in `|| true` if it exits non-zero) and to the namespace delete (`--ignore-not-found` already covers this).

---

### `infra/observability/values-trimmed.yaml` (config, CRUD/declarative)

**Analog:** `charts/field-guide-api/values.yaml` (full file, 61 lines) + `charts/field-guide-api/templates/mongodb/deployment.yaml` (for the resources-block placement precedent)

**Header/documentation-comment pattern** (lines 1-5 of `values.yaml`):
```yaml
# charts/field-guide-api/values.yaml
# Generic values schema — the PRD-3 templating seam (HELM-04).
# LOCAL DEV DEFAULTS ONLY — override sensitive values with --set or -f for anything real.
# Discipline mirror: apps/field-guide-api/.env.example
# Source: HELM-04 requirement schema + standard Helm conventions (RESEARCH.md Pattern 3)
```
Mirror this exact comment convention for `values-trimmed.yaml`: file path self-reference, one-line purpose, "LOCAL DEV DEFAULTS ONLY" banner, and a `Source:` line pointing at `11-RESEARCH.md`.

**Conservative explicit resources block pattern** (lines 21-27):
```yaml
resources:
  requests:
    cpu: 50m
    memory: 128Mi
  limits:
    cpu: 250m
    memory: 256Mi
```
This is the exact shape (requests/limits, cpu+memory, `m`/`Mi` units) to replicate for each of `prometheusOperator.resources`, `prometheus.prometheusSpec.resources`, `grafana.resources`, `kubeStateMetrics.resources` — RESEARCH.md's Pattern 2 (lines 305-367 of `11-RESEARCH.md`) already has the exact numbers pre-derived per component; this analog confirms the *shape* those numbers must take to match project convention.

**Committed local-dev password pattern** (lines 47-54, the direct analog for Grafana's `adminPassword`):
```yaml
mongodb:
  enabled: true
  image: mongo:7
  auth:
    username: root
    # local kind only; never a real credential — override with --set mongodb.auth.password=<real> for anything real.
    password: fieldguide-dev-password
    database: fieldguide
```
Apply the identical naming convention (`<component>-dev-password` — cf. `fieldguide-dev-password`, `launchpad-dev-password`) to Grafana: use something like `grafana-dev-password` as the literal `adminPassword` value, with the same one-line inline comment ("local kind only; never a real credential — override with ... for anything real") directly above it.

**Enable/disable comment-annotation pattern** (implicit throughout `values.yaml`, e.g. `metrics.enabled: true  # PRD-4 scrape seam ...`) — every override in `values-trimmed.yaml` that diverges from the chart's shipped default should carry an inline `# chart default: <value> — <reason>` comment, exactly as RESEARCH.md's Pattern 2 code block already does (this is also directly copy-pasteable from RESEARCH.md, which was live-verified against the real chart this session — prefer copying RESEARCH.md's block verbatim over re-deriving it).

---

### `docs/known-limitations.md` (doc, additive append)

**Analog:** the file's own existing "Committed Dev Password" and "No Prometheus / Grafana / Loki / Trivy (PRD-4)" sections (this phase updates/removes the latter and adds 2-3 new sibling sections)

**Section pattern** (lines 31-47, the committed-password precedent D-07 explicitly extends):
```markdown
### Committed Dev Password (`fieldguide-dev-password`, `launchpad-dev-password`)
The Helm chart ships with a committed local-dev MongoDB password. `helm install` prints a
warning at deploy time:

\`\`\`
!! WARNING: MongoDB is running with the COMMITTED local-dev password.
!! This is acceptable ONLY on a local kind cluster.
\`\`\`

This is intentional for frictionless local setup. ... Override it for anything beyond localhost:

\`\`\`bash
helm upgrade field-guide-api charts/field-guide-api --set mongodb.auth.password=<real-password>
\`\`\`
```
Add a new `### Committed Grafana Admin Password (grafana-dev-password)` section in exactly this shape: state the value name, note it's local-kind-only, show the override command (`helm upgrade kube-prometheus-stack ... --set grafana.adminPassword=<real-password> -n observability`).

**CRD-lifecycle section (new, no direct sibling yet but same voice/structure as any other numbered/named accepted-risk entry)** — write `### CRD Teardown Leaves monitoring.coreos.com CRDs Installed` following the same "What/Why/How to work around" implicit structure already used by e.g. "kind Cluster is Ephemeral" (lines 26-29) and "No RBAC or NetworkPolicies" (lines 75-78) — short paragraph, no need for the longer troubleshooting-style What-goes-wrong/Why/How-to-avoid/Warning-signs structure used in RESEARCH.md's Pitfalls (that structure belongs in RESEARCH.md, not this doc).

**Anonymous Grafana viewer access section (new)** — same short-paragraph convention, referencing D-08 and the Phase 15/16 "Open in Grafana" rationale, scoped explicitly to port-forward-only reachability (consistent with the existing "Port-Forward Only — No Ingress or TLS" section at lines 21-24, which this new section should cross-reference rather than duplicate).

**Section to update, not just append:** the existing "### No Prometheus / Grafana / Loki / Trivy (PRD-4)" section (lines 17-19) is now **stale** — this phase installs Prometheus + Grafana. Amend it to note Prometheus/Grafana/kube-state-metrics now exist (installed via `infra/observability/`, Phase 11), while Loki/Trivy/Alertmanager remain deferred (per the still-tracked Future Requirements in REQUIREMENTS.md) — do not leave the outdated blanket statement standing.

---

## Shared Patterns

### Idempotent script skeleton (applies to both new scripts)
**Source:** `scripts/cluster-setup.sh` (whole file) + `scripts/cluster-teardown.sh` (whole file)
**Apply to:** `scripts/observability-up.sh`, `scripts/observability-down.sh`
```bash
#!/usr/bin/env bash
# scripts/<name>.sh
# <one-line purpose>
#
# Usage:  bash scripts/<name>.sh
#         make <target>

set -o errexit
export MSYS_NO_PATHCONV=1   # suppress Git Bash POSIX-to-Windows path mangling
KCTX='--context=kind-kind'
```
Every mutating step: `echo "==> Step N: <description>..."` header, guarded idempotency check, `echo "    <result>."` confirmation. Every script ends with `echo "==> <script-basename-without-.sh> complete."`.

### Fail-fast prerequisite gate
**Source:** `scripts/cluster-setup.sh` lines 22-40
**Apply to:** `scripts/observability-up.sh` (add `helm` to the `for tool in docker kubectl` loop; `docker info` check stays relevant since kind runs on Docker)

### Self-verification over trusting exit codes
**Source:** `scripts/cluster-setup.sh` lines 106-131 (registry push/pull round-trip); `Makefile` `smoke`/`smoke-launchpad` targets (lines 71-92, 119-140) for the port-forward + curl + PASS/FAIL pattern these scripts must *invoke*, not reimplement
**Apply to:** both new scripts — `observability-up.sh` calls `kubectl wait --for=condition=Ready pod --all -n observability` then `make smoke && make smoke-launchpad`; `observability-down.sh` calls the same `make smoke && make smoke-launchpad` pair after teardown. Never re-implement the port-forward/curl logic inline — always shell out to the existing `make` targets (per D-06/D-03 and RESEARCH.md's "Don't Hand-Roll" table).

### Committed local-dev secret with inline warning comment
**Source:** `charts/field-guide-api/values.yaml` lines 50-53; reinforced by `docs/known-limitations.md` lines 31-47
**Apply to:** `infra/observability/values-trimmed.yaml`'s `grafana.adminPassword`, and the corresponding new `docs/known-limitations.md` section

### Conservative explicit resources.requests/limits block
**Source:** `charts/field-guide-api/values.yaml` lines 21-27 (chart-level default)
**Apply to:** every one of the four kept-enabled components in `values-trimmed.yaml` (`prometheusOperator`, `prometheus.prometheusSpec`, `grafana`, `kubeStateMetrics`) — exact numeric starting values already derived in `11-RESEARCH.md` Pattern 2, this analog only confirms the YAML shape/units convention to match

### `helm upgrade --install --wait --timeout` (no `--atomic`)
**Source:** `Makefile` lines 60-63 (`deploy:`) and 111-114 (`deploy-launchpad:`)
**Apply to:** the `helm upgrade --install kube-prometheus-stack ...` invocation inside `observability-up.sh` — same flag discipline (`--wait --timeout <N>s`, never `--atomic`), just a longer timeout (300s vs the apps' 180s) given the first-time CRD install + 4-pod rollout.

## No Analog Found

None — every file this phase creates/modifies has a strong, directly-applicable analog already in the codebase. The only genuinely novel logic (the D-10 preflight capacity check) has no existing script analog to copy verbatim, but RESEARCH.md's Code Examples section (lines 495-511 of `11-RESEARCH.md`) already provides a live-verified sketch to build from — flagged inline above rather than listed here as "no analog."

## Metadata

**Analog search scope:** `scripts/`, `charts/field-guide-api/`, `charts/launchpad/`, `Makefile`, `docs/known-limitations.md`, `infra/observability/`, `infra/kind/`
**Files scanned:** `scripts/cluster-setup.sh`, `scripts/cluster-teardown.sh`, `charts/field-guide-api/values.yaml`, `charts/field-guide-api/templates/mongodb/deployment.yaml`, `charts/launchpad/values.yaml` (glob-matched, not separately read — same shape as field-guide-api per RESEARCH.md's own cross-reference), `Makefile`, `docs/known-limitations.md`, `infra/kind/kind-config.yaml`
**Pattern extraction date:** 2026-07-16
