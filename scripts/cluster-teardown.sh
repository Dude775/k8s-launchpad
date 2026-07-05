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

# ── Delete kind cluster ───────────────────────────────────────────────────────
# kind delete cluster is natively idempotent — no error if cluster is already absent
echo "==> Deleting kind cluster..."
kind delete cluster
echo "    Cluster deleted (or was already absent)."

# ── Remove registry container ─────────────────────────────────────────────────
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
