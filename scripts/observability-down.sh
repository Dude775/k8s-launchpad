#!/usr/bin/env bash
# scripts/observability-down.sh
# Idempotent teardown of the kube-prometheus-stack observability release.
# Safe to re-run — each step is guarded against "already gone" errors.
#
# Usage:  bash scripts/observability-down.sh
#         make observability-down

set -o errexit

export MSYS_NO_PATHCONV=1   # suppress Git Bash POSIX-to-Windows path mangling

KCTX='--context=kind-kind'

# ── Uninstall the Helm release ────────────────────────────────────────────────
# helm uninstall only — this deliberately does NOT delete the
# monitoring.coreos.com CRDs. Helm's crds/ directory mechanism never removes
# CRDs on uninstall by design, and Phase 12's ServiceMonitors depend on them
# staying installed. This is intentional per D-01 (see docs/known-limitations.md).
echo "==> Uninstalling Helm release kube-prometheus-stack (namespace: observability)..."
if helm status kube-prometheus-stack -n observability "${KCTX}" &>/dev/null; then
  helm uninstall kube-prometheus-stack -n observability "${KCTX}"
  echo "    Release uninstalled."
else
  echo "    Release not found — skipping."
fi

# ── Delete the observability namespace ────────────────────────────────────────
# Sweeps any leftover secrets/configmaps/ephemeral resources (D-02). CRDs are
# cluster-scoped and survive namespace deletion, so this does not touch them.
echo "==> Deleting namespace observability..."
kubectl "${KCTX}" delete namespace observability --ignore-not-found
echo "    Namespace deleted (or was already absent)."

# ── Re-verify the v1.1 apps are still healthy ─────────────────────────────────
# D-03: teardown must never touch field-guide-api or launchpad. errexit will
# halt and report if either smoke check fails — this should never happen.
echo "==> Re-checking v1.1 app health (make smoke, make smoke-launchpad)..."
make smoke
make smoke-launchpad

echo "==> observability-down complete."
