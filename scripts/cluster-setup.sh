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

# ── Prerequisite gate ────────────────────────────────────────────────────────
command -v kind >/dev/null 2>&1 || {
  echo "ERROR: kind is not installed or not on PATH."
  echo "Install with: winget install Kubernetes.kind"
  echo "Or download from: https://kind.sigs.k8s.io/dl/v0.32.0/kind-windows-amd64.exe"
  exit 1
}
# docker and kubectl are equally hard dependencies — fail fast before any
# work happens rather than dying mid-run with a half-created cluster.
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

# ── Step 1: Registry ─────────────────────────────────────────────────────────
echo "==> Step 1: Ensuring local registry is running..."
if [ "$(docker inspect -f '{{.State.Running}}' "${reg_name}" 2>/dev/null || true)" != 'true' ]; then
  if docker inspect "${reg_name}" >/dev/null 2>&1; then
    # Container exists but is stopped — `docker run` would fail on the name
    # conflict and errexit would abort the whole setup. Start it instead.
    docker start "${reg_name}"
    echo "    Existing registry container started."
  else
    docker run \
      -d --restart=always \
      -p "127.0.0.1:${reg_port}:5000" \
      --network bridge \
      --name "${reg_name}" \
      registry:3
    echo "    Registry started."
  fi
else
  echo "    Registry already running — skipping."
fi

# ── Step 2: Cluster ──────────────────────────────────────────────────────────
echo "==> Step 2: Ensuring kind cluster exists..."
if ! kind get clusters 2>/dev/null | grep -q '^kind$'; then
  kind create cluster --config infra/kind/kind-config.yaml
  echo "    Cluster created."
else
  echo "    Cluster already exists — skipping."
fi

# ── Step 3: Patch each node's containerd hosts.toml ─────────────────────────
echo "==> Step 3: Wiring containerd hosts.toml on each node..."
REGISTRY_DIR="/etc/containerd/certs.d/localhost:${reg_port}"
for node in $(kind get nodes); do
  docker exec "${node}" mkdir -p "${REGISTRY_DIR}"
  cat <<EOF | docker exec -i "${node}" cp /dev/stdin "${REGISTRY_DIR}/hosts.toml"
[host."http://${reg_name}:5000"]
EOF
  echo "    Patched node: ${node}"
done

# ── Step 4: Connect registry to kind network ─────────────────────────────────
echo "==> Step 4: Connecting registry to kind Docker network..."
if [ "$(docker inspect -f='{{json .NetworkSettings.Networks.kind}}' "${reg_name}")" = 'null' ]; then
  docker network connect "kind" "${reg_name}"
  echo "    Registry connected to kind network."
else
  echo "    Registry already on kind network — skipping."
fi

# ── Step 5: Discovery ConfigMap (KEP-1755) ───────────────────────────────────
echo "==> Step 5: Applying local-registry-hosting ConfigMap..."
cat <<EOF | kubectl ${KCTX} apply -f -
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

# ── Step 6: Registry wiring verification ─────────────────────────────────────
echo "==> Step 6: Verifying registry wiring (push from host → pull from pod)..."
docker pull alpine:3.20 --quiet
docker tag alpine:3.20 localhost:${reg_port}/verify:v1
docker push localhost:${reg_port}/verify:v1

kubectl ${KCTX} delete pod registry-verify --ignore-not-found

kubectl ${KCTX} run registry-verify \
  --image=localhost:${reg_port}/verify:v1 \
  --restart=Never \
  --image-pull-policy=Always \
  -- echo "registry-ok"

# One-shot pods never become Ready/Completed conditions — wait on phase instead.
kubectl ${KCTX} wait --for=jsonpath='{.status.phase}'=Succeeded pod/registry-verify --timeout=60s
kubectl ${KCTX} delete pod registry-verify --ignore-not-found

echo "==> Registry wiring verified OK"
echo "==> cluster-setup complete — cluster is ready."
