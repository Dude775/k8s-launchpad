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
# NOTE: `--wait` is deliberately NOT used here. On this dev environment (Windows +
# Docker Desktop + kind), Helm's --wait implementation opens a long-lived watch
# connection to the API server through Docker Desktop's port-forward proxy, which
# hangs indefinitely (confirmed live: 0 forward progress, ~0s CPU growth over 20+
# minutes, two independent hangs reproduced) — the proxy does not reliably deliver
# watch/chunked-transfer responses. Plain polling GETs (used in Step 3 below) do
# not hit this issue. See docs/known-limitations.md.
echo "==> Step 2: Installing/upgrading trimmed kube-prometheus-stack..."
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --version 87.16.1 \
  --namespace observability --create-namespace \
  -f infra/observability/values-trimmed.yaml \
  --timeout 300s

# ── Step 3: Readiness self-check (D-06) ──────────────────────────────────────
# The chart also creates a short-lived admission-webhook patch Job whose pod
# reaches Succeeded (not Ready) — exclude Succeeded-phase pods so the check
# doesn't trip on it. Uses polling `kubectl get` (not `kubectl wait`/watch) —
# see the Step 2 note above on why watch-based waits hang in this environment.
echo "==> Step 3: Verifying observability pods are Running/Ready..."
READY_DEADLINE=$(( $(date +%s) + 180 ))
while true; do
  NOT_READY=$(kubectl ${KCTX} get pods -n "${NAMESPACE}" \
    --field-selector=status.phase!=Succeeded \
    -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.phase}{" "}{range .status.containerStatuses[*]}{.ready}{","}{end}{"\n"}{end}' 2>/dev/null | \
    grep -v -E ' Running (true,)+$' || true)
  POD_COUNT=$(kubectl ${KCTX} get pods -n "${NAMESPACE}" --field-selector=status.phase!=Succeeded --no-headers 2>/dev/null | wc -l)
  if [ "$POD_COUNT" -gt 0 ] && [ -z "$NOT_READY" ]; then
    echo "    All ${POD_COUNT} observability pod(s) Running/Ready."
    break
  fi
  if [ "$(date +%s)" -ge "$READY_DEADLINE" ]; then
    echo "ERROR: observability pods failed to become Ready within 180s — describing not-ready pods:"
    kubectl ${KCTX} get pods -n "${NAMESPACE}" -o wide
    kubectl ${KCTX} get pods -n "${NAMESPACE}" --field-selector=status.phase!=Running,status.phase!=Succeeded -o name | \
      xargs -r -n1 kubectl ${KCTX} describe -n "${NAMESPACE}"
    exit 1
  fi
  sleep 5
done

# ── Step 4: ServiceMonitor CRD existence guard (D-02) ────────────────────────
echo "==> Step 4: Verifying ServiceMonitor CRD is installed..."
if ! kubectl ${KCTX} get crd servicemonitors.monitoring.coreos.com >/dev/null 2>&1; then
  echo "ERROR: CRD servicemonitors.monitoring.coreos.com not found."
  echo "  ACTION: the observability stack install (Steps 0-3 above) must complete"
  echo "  successfully before ServiceMonitors can be applied — re-run this script"
  echo "  (bash scripts/observability-up.sh) from a clean state, or check"
  echo "  'kubectl ${KCTX} get pods -n observability' for a stuck install."
  exit 1
fi
echo "    CRD present — continuing."

# ── Step 5: Apply ServiceMonitors (D-01, D-07) ───────────────────────────────
echo "==> Step 5: Applying ServiceMonitor manifests..."
kubectl ${KCTX} apply -f infra/observability/servicemonitor-field-guide-api.yaml
kubectl ${KCTX} apply -f infra/observability/servicemonitor-launchpad.yaml

# ── Step 6: Per-app presence check (D-03) ────────────────────────────────────
echo "==> Step 6: Checking which v1.1 apps are deployed..."
VERIFY_JOBS=""
for job in field-guide-api launchpad; do
  if kubectl ${KCTX} -n default get svc "$job" >/dev/null 2>&1; then
    VERIFY_JOBS="${VERIFY_JOBS} ${job}"
  else
    echo "    WARNING: Service '${job}' not found in namespace 'default' — apps not"
    echo "    deployed yet. ServiceMonitor applied anyway; skipping its up==1 check."
    echo "    Targets will appear after 'make up-all' (or the app-specific deploy target)."
  fi
done

# ── Step 7: Self-verify scraping — up == 1 (D-10) ────────────────────────────
echo "==> Step 7: Verifying Prometheus is scraping the applied targets..."
if [ -z "$VERIFY_JOBS" ]; then
  echo "    No deployed apps to verify against — skipping scrape self-check entirely."
else
  if command -v pkill >/dev/null 2>&1; then
    # Pattern anchored on `port-forward.*svc/<name>` so it matches regardless of
    # flag position (the actual command line includes `--context=kind-kind`
    # between `kubectl` and `port-forward`).
    pkill -f "port-forward.*svc/kube-prometheus-stack-prometheus" 2>/dev/null || true
  fi
  kubectl ${KCTX} port-forward -n "${NAMESPACE}" svc/kube-prometheus-stack-prometheus 9090:9090 &>/dev/null &
  PF_PID=$!
  trap "kill ${PF_PID} 2>/dev/null || true" EXIT
  sleep 3

  DEADLINE=$(( $(date +%s) + 150 ))
  for job in $VERIFY_JOBS; do
    echo "    Waiting for up{job=\"${job}\"} == 1..."
    while true; do
      # `|| true`: a transient curl failure (connection refused while the
      # port-forward warms up / drops) must NOT abort the script under errexit —
      # the deadline check below owns failure handling (mirrors Step 3's guards).
      # `--max-time 10`: bounds each poll so a half-open connection through the
      # Docker Desktop proxy (see Step 2 note) can't hang past the 150s deadline.
      RESPONSE=$(curl -s --max-time 10 -G "http://localhost:9090/api/v1/query" \
        --data-urlencode "query=up{job=\"${job}\"}" || true)
      if echo "$RESPONSE" | grep -qE '"value":\[[0-9.]+,"1"\]'; then
        echo "      PASS  up{job=\"${job}\"} == 1"
        break
      fi
      if [ "$(date +%s)" -ge "$DEADLINE" ]; then
        echo "ERROR: up{job=\"${job}\"} did not reach 1 within 150s."
        echo "  Last response: ${RESPONSE}"
        echo "  ACTION: check 'kubectl ${KCTX} -n ${NAMESPACE} port-forward svc/kube-prometheus-stack-prometheus 9090:9090'"
        echo "  and open http://localhost:9090/targets — look for job=\"${job}\" and its error reason."
        exit 1
      fi
      sleep 5
    done
  done
fi

# ── Step 8: Additive-only re-verification (D-06) ─────────────────────────────
echo "==> Step 8: Re-verifying v1.1 apps are unaffected..."
make smoke
make smoke-launchpad

echo "==> observability-up complete."
echo "    Prometheus: kubectl port-forward -n ${NAMESPACE} svc/kube-prometheus-stack-prometheus 9090:9090"
echo "    Grafana:    kubectl port-forward -n ${NAMESPACE} svc/kube-prometheus-stack-grafana 3000:80"
