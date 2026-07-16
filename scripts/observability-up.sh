#!/usr/bin/env bash
# scripts/observability-up.sh
# Idempotent, self-verifying install of a trimmed kube-prometheus-stack (chart 87.16.1,
# pinned) into the `observability` namespace — preflight capacity check, helm
# upgrade --install, pod-readiness wait, and a post-install re-check that the v1.1
# apps (field-guide-api, launchpad) were not disturbed.
#
# Usage:  bash scripts/observability-up.sh
#         make observability-up

set -o errexit
# NOTE: set -o pipefail is intentionally omitted — it conflicts with the
# "|| true" idempotency guards used throughout this script (mirrors cluster-setup.sh).

export MSYS_NO_PATHCONV=1   # suppress Git Bash POSIX-to-Windows path mangling

KCTX='--context=kind-kind'
NAMESPACE='observability'

# Trimmed stack's total memory requests (sum of infra/observability/values-trimmed.yaml):
#   prometheusOperator 100Mi + prometheus 256Mi + grafana 128Mi + kubeStateMetrics 32Mi = 516Mi
TRIMMED_STACK_REQ_KI=$((516 * 1024))

# ── Prerequisite gate ────────────────────────────────────────────────────────
for tool in docker kubectl helm; do
  command -v "$tool" >/dev/null 2>&1 || {
    echo "ERROR: $tool is not installed or not on PATH."
    exit 1
  }
done
docker info >/dev/null 2>&1 || {
  echo "ERROR: Docker daemon is not running."
  exit 1
}

# Convert a Kubernetes quantity (memory) string into whole Ki (kibibytes).
# Handles Ki/Mi/Gi (binary, the common case), K/M/G (decimal), and bare byte counts.
# Unknown/empty input contributes 0 — never aborts the sum on a single odd value.
to_ki() {
  local val="$1"
  [ -z "$val" ] && { echo 0; return; }
  case "$val" in
    *Ki) echo "${val%Ki}" ;;
    *Mi) echo $(( ${val%Mi} * 1024 )) ;;
    *Gi) echo $(( ${val%Gi} * 1024 * 1024 )) ;;
    *K)  echo $(( ${val%K} * 1000 / 1024 )) ;;
    *M)  echo $(( ${val%M} * 1000 * 1000 / 1024 )) ;;
    *G)  echo $(( ${val%G} * 1000 * 1000 * 1000 / 1024 )) ;;
    ''|*[!0-9]*) echo 0 ;;
    *)   echo $(( val / 1024 )) ;;
  esac
}

# ── Step 0: Preflight capacity check (D-10) ──────────────────────────────────
echo "==> Step 0: Preflight capacity check..."
ALLOCATABLE_RAW=$(kubectl ${KCTX} get nodes -o jsonpath='{.items[0].status.allocatable.memory}')
ALLOCATABLE_KI=$(to_ki "$ALLOCATABLE_RAW")

EXISTING_REQ_KI=0
while IFS= read -r mem; do
  [ -z "$mem" ] && continue
  EXISTING_REQ_KI=$(( EXISTING_REQ_KI + $(to_ki "$mem") ))
done <<EOF
$(kubectl ${KCTX} get pods -A -o jsonpath='{range .items[*]}{range .spec.containers[*]}{.resources.requests.memory}{"\n"}{end}{end}')
EOF

HEADROOM_KI=$(( ALLOCATABLE_KI - EXISTING_REQ_KI ))
echo "    Allocatable: ${ALLOCATABLE_KI}Ki | Already requested: ${EXISTING_REQ_KI}Ki | Headroom: ${HEADROOM_KI}Ki | Stack needs: ${TRIMMED_STACK_REQ_KI}Ki"

if [ "$HEADROOM_KI" -lt "$TRIMMED_STACK_REQ_KI" ]; then
  NEEDED_GI=$(( (ALLOCATABLE_KI + TRIMMED_STACK_REQ_KI - HEADROOM_KI) / 1024 / 1024 + 1 ))
  echo "ERROR: insufficient memory headroom for the observability stack."
  echo "  Allocatable: ${ALLOCATABLE_KI}Ki | Already requested: ${EXISTING_REQ_KI}Ki | Stack needs: ${TRIMMED_STACK_REQ_KI}Ki"
  echo "  ACTION: raise Docker Desktop's memory allocation (Settings > Resources > Memory) to at least ${NEEDED_GI} GB and retry."
  exit 1
fi
echo "    Headroom sufficient — continuing."

# ── Step 1: prometheus-community repo ────────────────────────────────────────
echo "==> Step 1: Ensuring prometheus-community repo is registered..."
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts >/dev/null 2>&1 || true
helm repo update prometheus-community

# ── Step 2: Install/upgrade trimmed kube-prometheus-stack ───────────────────
echo "==> Step 2: Installing/upgrading trimmed kube-prometheus-stack..."
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --version 87.16.1 \
  --namespace observability --create-namespace \
  -f infra/observability/values-trimmed.yaml \
  --wait --timeout 300s

# ── Step 3: Readiness self-check (D-06) ──────────────────────────────────────
# The chart also creates a short-lived admission-webhook patch Job whose pod
# reaches Succeeded (not Ready) — exclude Succeeded-phase pods so the wait
# doesn't trip on it.
echo "==> Step 3: Verifying observability pods are Running/Ready..."
if ! kubectl ${KCTX} wait --for=condition=Ready pod --all -n "${NAMESPACE}" \
     --field-selector=status.phase!=Succeeded --timeout=180s; then
  echo "ERROR: observability pods failed to become Ready — describing not-ready pods:"
  kubectl ${KCTX} get pods -n "${NAMESPACE}" --field-selector=status.phase!=Running,status.phase!=Succeeded -o name | \
    xargs -r -n1 kubectl ${KCTX} describe -n "${NAMESPACE}"
  exit 1
fi

# ── Step 4: Additive-only re-verification (D-06) ─────────────────────────────
echo "==> Step 4: Re-verifying v1.1 apps are unaffected..."
make smoke
make smoke-launchpad

echo "==> observability-up complete."
echo "    Prometheus: kubectl port-forward -n ${NAMESPACE} svc/kube-prometheus-stack-prometheus 9090:9090"
echo "    Grafana:    kubectl port-forward -n ${NAMESPACE} svc/kube-prometheus-stack-grafana 3000:80"
