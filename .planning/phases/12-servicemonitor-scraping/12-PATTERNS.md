# Phase 12: ServiceMonitor Scraping - Pattern Map

**Mapped:** 2026-07-18
**Files analyzed:** 3 (2 new, 1 modified)
**Analogs found:** 3 / 3

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|-----------------|---------------|
| `infra/observability/servicemonitor-field-guide-api.yaml` | config (K8s CRD manifest) | event-driven (declarative scrape-target registration, reconciled by Prometheus Operator) | `charts/field-guide-api/templates/service.yaml` (for label/port values it must match) + `infra/observability/values-trimmed.yaml` (for repo's flat-YAML manifest style) | role-match (no existing standalone ServiceMonitor in repo; Service.yaml is the label/port source of truth) |
| `infra/observability/servicemonitor-launchpad.yaml` | config (K8s CRD manifest) | event-driven | `charts/launchpad/templates/service.yaml` (labels/port) + `servicemonitor-field-guide-api.yaml` (sibling file, same phase — near-identical twin) | role-match |
| `scripts/observability-up.sh` (MODIFIED — new Steps 4-7, renumber old Step 4 → Step 8) | utility (bash install/verify script) | request-response (kubectl/curl calls) + event-driven (poll-until-condition) | itself, `scripts/observability-up.sh` Steps 0-3 (existing numbered-step + actionable-abort convention) + `Makefile` `smoke`/`smoke-launchpad` targets (background port-forward + trap + curl-loop idiom) | exact (same file, extending its own established pattern) |

**Explicitly NOT modified:** `scripts/observability-down.sh` — per D-04, teardown gets no new step; the existing `kubectl delete namespace observability` (line 38) already sweeps the ServiceMonitors as a side effect since they live in the `observability` namespace. Do not touch this file in this phase.

## Pattern Assignments

### `infra/observability/servicemonitor-field-guide-api.yaml` (config, event-driven)

**Analog:** `charts/field-guide-api/templates/service.yaml` (label/port source of truth) + `infra/observability/values-trimmed.yaml` (repo's standalone-YAML style precedent)

**Service labels/port this manifest's selector MUST match** (`charts/field-guide-api/templates/service.yaml` lines 5-19):
```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "field-guide-api.fullname" . }}
  labels:
    {{- include "field-guide-api.labels" . | nindent 4 }}
spec:
  ports:
    - port: {{ .Values.service.port }}
      targetPort: {{ .Values.service.targetPort }}
      protocol: TCP
      name: http
  selector:
    {{- include "field-guide-api.selectorLabels" . | nindent 4 }}
```

**selectorLabels helper** (`charts/field-guide-api/templates/_helpers.tpl` lines 69-72):
```
{{- define "field-guide-api.selectorLabels" -}}
app.kubernetes.io/name: {{ include "field-guide-api.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
```
`field-guide-api.name` resolves to the bare chart name `field-guide-api` (confirmed via `Chart.yaml`/`.name` helper, per RESEARCH.md). The Service's `name:` port is literally `http`.

**Full manifest to write (verified against in-repo labels — from RESEARCH.md Pattern 1, cross-checked against the Service/`_helpers.tpl` reads above):**
```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: field-guide-api
  namespace: observability
spec:
  namespaceSelector:
    matchNames: ["default"]
  selector:
    matchLabels:
      app.kubernetes.io/name: field-guide-api
  endpoints:
    - port: http        # matches charts/field-guide-api/templates/service.yaml's `name: http`
      interval: 15s      # D-08 — explicit; all other params left at chart default (D-09)
```

**Note:** No `app.kubernetes.io/instance` in the selector — only `name`, per D-06/RESEARCH.md rationale (the MongoDB sub-Service uses a distinct `app.kubernetes.io/name: field-guide-api-mongodb`, so matching on `name` alone cannot collide). No `release:` label — `values-trimmed.yaml` already sets `serviceMonitorSelectorNilUsesHelmValues: false`.

---

### `infra/observability/servicemonitor-launchpad.yaml` (config, event-driven)

**Analog:** `charts/launchpad/templates/service.yaml` (identical structure to field-guide-api's, lines 5-19) — same `name: http` port, same `selectorLabels` helper pattern with `launchpad.name` resolving to `launchpad`.

**Full manifest to write:**
```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: launchpad
  namespace: observability
spec:
  namespaceSelector:
    matchNames: ["default"]
  selector:
    matchLabels:
      app.kubernetes.io/name: launchpad
  endpoints:
    - port: http
      interval: 15s
```

This is a near-exact twin of the field-guide-api manifest — only `metadata.name` and `selector.matchLabels.app.kubernetes.io/name` differ (`launchpad` vs `field-guide-api`). Keep the two files structurally identical for maintainability (D-07's "one concern per file" does not imply divergent structure).

---

### `scripts/observability-up.sh` (utility, request-response + event-driven poll)

**Analog:** itself — extend the existing numbered-step convention already present in the file (Steps 0-4), plus reuse the Makefile's proven port-forward+trap+curl idiom for the new polling step.

**File header / shared-variable pattern already established** (lines 1-22, unchanged, for context — new steps use these same variables `KCTX`, `NAMESPACE`):
```bash
set -o errexit
export MSYS_NO_PATHCONV=1   # suppress Git Bash POSIX-to-Windows path mangling
KCTX='--context=kind-kind'
NAMESPACE='observability'
```

**Actionable-abort / preflight-guard style to copy for the new CRD guard (D-02)** — modeled on the existing Step 0 preflight pattern (lines 24-30, 70-77):
```bash
for tool in docker kubectl helm; do
  command -v "$tool" >/dev/null 2>&1 || {
    echo "ERROR: $tool is not installed or not on PATH."
    exit 1
  }
done
...
if [ "$HEADROOM_KI" -lt "$TRIMMED_STACK_REQ_KI" ]; then
  echo "ERROR: insufficient memory headroom for the observability stack."
  echo "  ACTION: raise Docker Desktop's memory allocation ... and retry."
  exit 1
fi
```
New Step 4 (CRD guard, D-02) should follow this exact `ERROR:` / `  ACTION:` two-line shape — see RESEARCH.md Pattern 2 for the ready-to-use code block (already drafted, verified against this style):
```bash
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
```

**Polling-loop pattern to copy for Step 3 style (bounded deadline, no `kubectl wait`)** — this is the file's own established idiom (lines 104-124), reuse for the new Step 7 up==1 poll:
```bash
READY_DEADLINE=$(( $(date +%s) + 180 ))
while true; do
  ...
  if [ "$POD_COUNT" -gt 0 ] && [ -z "$NOT_READY" ]; then
    echo "    All ${POD_COUNT} observability pod(s) Running/Ready."
    break
  fi
  if [ "$(date +%s)" -ge "$READY_DEADLINE" ]; then
    echo "ERROR: observability pods failed to become Ready within 180s..."
    exit 1
  fi
  sleep 5
done
```

**Background port-forward + trap + curl-loop idiom** — copy from `Makefile` `smoke` target (lines 71-92, exact text):
```makefile
smoke: ## background port-forward, curl /health + /entries + /metrics, PASS/FAIL, cleanup
	@echo "==> Starting smoke test..."; \
	if command -v pkill >/dev/null 2>&1; then \
	  pkill -f "kubectl port-forward svc/$(RELEASE)" 2>/dev/null || true; \
	else \
	  echo "  note: pkill not found (stock Git Bash) — skipping stale port-forward cleanup; if 8080 is busy see docs/troubleshooting.md"; \
	fi; \
	kubectl port-forward svc/$(RELEASE) 8080:80 &>/dev/null & \
	PF_PID=$$!; \
	trap "kill $$PF_PID 2>/dev/null || true" EXIT; \
	sleep 3; \
	STATUS=0; \
	for endpoint in health entries metrics; do \
	  CODE=$$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/$$endpoint); \
	  if [ "$$CODE" = "200" ]; then \
	    echo "  PASS  /$$endpoint → $$CODE"; \
	  else \
	    echo "  FAIL  /$$endpoint → $$CODE"; \
	    STATUS=1; \
	  fi; \
	done; \
	if [ $$STATUS -eq 0 ]; then echo "==> smoke PASSED"; else echo "==> smoke FAILED"; exit 1; fi
```
Structure to transplant into bash (not Makefile `$$`-escaping, plain `$` in a `.sh` file): `pkill` guard → background port-forward → capture `PF_PID=$!` → `trap "kill $PF_PID ..." EXIT` → `sleep 3` → loop with PASS/FAIL per item → non-zero exit on failure.

**Full new Steps 4-7 (D-01/D-02/D-03/D-10) — ready-to-use, already drafted and verified against this file's exact variable names in RESEARCH.md Architecture Patterns / Pattern 3:**
```bash
# ── Step 4: CRD existence guard (D-02) ──────────────────────────────────────
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

# ── Step 5: Apply ServiceMonitors (D-01, D-07) ──────────────────────────────
echo "==> Step 5: Applying ServiceMonitor manifests..."
kubectl ${KCTX} apply -f infra/observability/servicemonitor-field-guide-api.yaml
kubectl ${KCTX} apply -f infra/observability/servicemonitor-launchpad.yaml

# ── Step 6: Per-app presence check (D-03) ───────────────────────────────────
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

# ── Step 7: Self-verify scraping — up == 1 (D-10) ───────────────────────────
echo "==> Step 7: Verifying Prometheus is scraping the applied targets..."
if [ -z "$VERIFY_JOBS" ]; then
  echo "    No deployed apps to verify against — skipping scrape self-check entirely."
else
  if command -v pkill >/dev/null 2>&1; then
    pkill -f "kubectl port-forward -n ${NAMESPACE} svc/kube-prometheus-stack-prometheus" 2>/dev/null || true
  fi
  kubectl ${KCTX} port-forward -n "${NAMESPACE}" svc/kube-prometheus-stack-prometheus 9090:9090 &>/dev/null &
  PF_PID=$!
  trap "kill ${PF_PID} 2>/dev/null || true" EXIT
  sleep 3

  DEADLINE=$(( $(date +%s) + 150 ))
  for job in $VERIFY_JOBS; do
    echo "    Waiting for up{job=\"${job}\"} == 1..."
    while true; do
      RESPONSE=$(curl -s -G "http://localhost:9090/api/v1/query" --data-urlencode "query=up{job=\"${job}\"}")
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
```

**Renumbering:** existing Step 4 ("Additive-only re-verification", lines 126-129: `make smoke` / `make smoke-launchpad`) becomes **Step 8**. Only its comment header and `echo` label change (`Step 4:` → `Step 8:`); its body (`make smoke; make smoke-launchpad`) is untouched — this is the file's own "re-verify v1.1 apps unaffected" pattern, reused verbatim, not re-derived.

**Error handling pattern used throughout this file** (consistent across all steps — apply to new steps too): `echo "ERROR: <what failed>."` followed by one or more `echo "  ACTION: <exact command or check to run next>."` lines, then `exit 1`. Never a bare `exit 1` without an ACTION line. `set -o errexit` is already active at the top of the file — no explicit `trap ERR` needed beyond the one already in place for the port-forward PID cleanup.

---

## Shared Patterns

### Numbered-step + actionable-abort convention
**Source:** `scripts/observability-up.sh` (whole file, Steps 0-4) and `scripts/cluster-setup.sh` (same convention, per CONTEXT.md code_context)
**Apply to:** All new steps (4-7) inserted into `observability-up.sh`
```bash
echo "==> Step N: <what this step does>..."
# ... work ...
echo "    <success detail>."
# on failure:
echo "ERROR: <what failed>."
echo "  ACTION: <exact next command/check>."
exit 1
```

### Background port-forward + PID trap + poll-until-condition
**Source:** `Makefile` lines 71-92 (`smoke`) and 119-140 (`smoke-launchpad`); also `scripts/observability-up.sh` lines 104-124 (Step 3's bounded poll loop, no port-forward but same deadline idiom)
**Apply to:** New Step 7 in `observability-up.sh` (Prometheus `up==1` self-verify)
```bash
kubectl port-forward svc/$(RELEASE) 8080:80 &>/dev/null &
PF_PID=$!
trap "kill $PF_PID 2>/dev/null || true" EXIT
sleep 3
# then poll with a bounded deadline, not `kubectl wait`
```

### `MSYS_NO_PATHCONV=1` + no `kubectl wait`/watch-based waits
**Source:** `scripts/observability-up.sh` line 15 (export) and lines 85-91 (documented rationale: Helm `--wait` hangs on this Windows/Docker-Desktop/kind host via long-lived watch connections through the proxy)
**Apply to:** All new steps — never introduce `kubectl wait`; always use a `while true; ... sleep N; done` bounded-deadline loop instead, exactly as Step 3 and Step 7 both do.

### Label-selector source of truth
**Source:** `charts/field-guide-api/templates/_helpers.tpl` lines 69-72 and `charts/launchpad/templates/_helpers.tpl` (identical shape) — `selectorLabels` helper stamps `app.kubernetes.io/name: <chart-name>` distinctly per chart, with the mongodb sub-Service using a deliberately different `<chart-name>-mongodb` name to avoid selector collision.
**Apply to:** Both new ServiceMonitor manifests — match on `app.kubernetes.io/name` only, no `app.kubernetes.io/instance`, no `release:` label (already covered by `serviceMonitorSelectorNilUsesHelmValues: false` in `infra/observability/values-trimmed.yaml`).

## No Analog Found

None — every file in this phase has a strong, directly-applicable analog already in the repo (see table above). This phase is composition of existing idioms, not new-pattern introduction, per RESEARCH.md's explicit framing ("treat any solution that introduces a genuinely new pattern... as over-engineering").

## Metadata

**Analog search scope:** `scripts/`, `Makefile`, `charts/field-guide-api/templates/`, `charts/launchpad/templates/`, `infra/observability/`
**Files scanned:** `scripts/observability-up.sh`, `scripts/observability-down.sh`, `Makefile` (smoke/smoke-launchpad targets), `charts/field-guide-api/templates/service.yaml`, `charts/field-guide-api/templates/_helpers.tpl`, `charts/launchpad/templates/service.yaml`, `infra/observability/values-trimmed.yaml`
**Pattern extraction date:** 2026-07-18
