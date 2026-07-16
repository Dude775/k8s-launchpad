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
# NOTE: Helm's context flag is `--kube-context`, NOT `--context` (that is a kubectl-only
# flag). Using the shared `${KCTX}` (`--context=kind-kind`) here — as originally written —
# is an unrecognized Helm flag that makes every `helm status`/`helm uninstall` call error
# out silently under `&>/dev/null`, so the `if` always took the "not found" branch and
# `helm uninstall` never actually ran. Fixed to build a Helm-specific context flag.
HELM_KCTX='--kube-context=kind-kind'
if helm status kube-prometheus-stack -n observability ${HELM_KCTX} &>/dev/null; then
  helm uninstall kube-prometheus-stack -n observability ${HELM_KCTX}
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
