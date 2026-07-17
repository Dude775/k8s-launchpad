# Phase 12: ServiceMonitor Scraping - Context

**Gathered:** 2026-07-16
**Status:** Ready for planning

<domain>
## Phase Boundary

Prometheus actively discovers and scrapes the existing `/metrics` endpoints of field-guide-api and launchpad via standalone `ServiceMonitor` manifests in `infra/observability/`, with zero changes to either app's Helm chart. Verified live: the Prometheus Targets page and a PromQL query both show `up == 1` for the `field-guide-api` and `launchpad` jobs — not just object creation succeeding. Requirement: OBS-03.

Out of this phase: Grafana dashboards (Phase 13), Makefile targets (Phase 14 — this phase extends the Phase 11 scripts the targets will wrap), any launchpad code or UI work (Phases 15-16).

**Hard constraint (milestone-wide):** ADDITIVE ONLY — nothing from v1.1 is deleted, rewritten, or behavior-changed; existing smoke tests pass unchanged. The Phase 11 scripts (`observability-up.sh` / `observability-down.sh`) are v2.0 code and MAY be extended.

</domain>

<decisions>
## Implementation Decisions

### Apply Mechanism & Lifecycle
- **D-01:** ServiceMonitors are applied by extending `scripts/observability-up.sh` — a new step after the stack is Running/Ready runs `kubectl apply -f` on the manifests. One lifecycle, one command; exactly what Phase 14's `make observability-up` success criterion expects. No separate apply script.
- **D-02:** Before applying, the script guards on CRD existence (`kubectl get crd servicemonitors.monitoring.coreos.com`) and aborts with an actionable message ("run scripts/observability-up.sh first" / stack-not-installed hint) if absent — matching the Phase 11 preflight style (11/D-10) and the project's actionable-error convention.
- **D-03:** If the v1.1 apps aren't deployed (no `field-guide-api` / `launchpad` Services), apply the ServiceMonitors anyway, print a warning ("apps not deployed — targets will appear after make up-all"), and skip the `up == 1` verification for the missing app(s). A ServiceMonitor with no matching Service is valid and harmless; install order stays flexible.
- **D-04:** `observability-down.sh` gets NO explicit ServiceMonitor delete step. Because the ServiceMonitors live in the `observability` namespace (D-06), the existing namespace deletion (11/D-02) sweeps them as a side effect — accepted. `observability-up.sh` re-applies them on every install, so the lifecycle is self-healing.

### Job Naming & Manifest Layout
- **D-05:** Job names use the Service-name defaults — `up{job="field-guide-api"}` and `up{job="launchpad"}` — no jobLabel overrides, no relabeling. The Services are named after the Helm releases, which already match the ROADMAP success criteria and the queries Phases 13/15 will write.
- **D-06:** The ServiceMonitor objects live in the `observability` namespace (with the stack), using `spec.namespaceSelector` to target the `default` namespace where both app Services run. Phase 11 already set `serviceMonitorSelectorNilUsesHelmValues: false`, so no `release:` label is needed (pitfall 2 pre-solved).
- **D-07:** One manifest file per app: `infra/observability/servicemonitor-field-guide-api.yaml` and `infra/observability/servicemonitor-launchpad.yaml`. Mirrors the repo's one-concern-per-file style; Phase 13 adds `dashboards/` alongside.

### Scrape Tuning
- **D-08:** Explicit `interval: 15s` on both ServiceMonitor endpoints. Snappiest for the Mission Control demo; Phase 13 PromQL rate windows must be ≥ 4x the interval, so 1m windows become available. Cost negligible for two small Flask targets on 24h emptyDir retention.
- **D-09:** All other scrape parameters stay default: `path` defaults to `/metrics`, endpoints target the Services' named `http` port, `scrapeTimeout` default 10s. Not pinned in YAML unless a default is actually overridden.

### Verification
- **D-10:** `observability-up.sh` self-verifies scraping: after applying the ServiceMonitors, it polls the Prometheus HTTP API (`/api/v1/query?query=up{job=...}`) until both jobs return 1, aborting with an actionable message on timeout. Extends the 11/D-06 self-verification pattern — scrape health is proven on every install (skipped per-app when apps are absent, per D-03).
- **D-11:** In addition to the automated check, one plan task ends with a human checkpoint: operator opens the Prometheus Targets page via port-forward and confirms both scrape jobs show UP.
- **D-12:** The phase's certified end state is torn down — run the full up → verify `up == 1` → down lifecycle, matching Phase 11's convention. This also proves ServiceMonitor re-apply on reinstall works. Phase 13 starts from a clean slate with one `observability-up`.

### Claude's Discretion
- How the script reaches the Prometheus query API (port-forward vs in-cluster curl pod vs exec) and poll/timeout values for the `up == 1` wait.
- Exact wording of warnings/abort messages (follow the Phase 11 actionable-message style, name the fix).
- Whether `kubectl apply` targets the two files explicitly or a glob — as long as D-07's layout holds.
- Scrape-appearance patience: operator reconcile + first 15s scrape typically lands within ~30-60s; choose a poll timeout with sensible headroom.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### v2.0 Research (grounds every decision above)
- `.planning/research/ARCHITECTURE.md` — Pattern 1: out-of-chart ServiceMonitor targeting existing Services by label; example manifest; anti-pattern 1 (never put ServiceMonitors in app charts)
- `.planning/research/PITFALLS.md` — Pitfall 2: `release:` label / selector mismatch → silent zero-target discovery; verification = live `up{job=...}` query, not `kubectl get servicemonitor`
- `.planning/research/STACK.md` — CRD-existence smoke check (`kubectl get crds | grep monitoring.coreos.com`); serviceMonitorSelectorNilUsesHelmValues rationale
- `.planning/research/SUMMARY.md` — Phase 2 (ServiceMonitor Scraping) build-order summary

### Phase 11 artifacts this phase extends
- `.planning/phases/11-observability-stack-install/11-CONTEXT.md` — D-01 (CRDs retained on teardown), D-02 (namespace deleted on teardown), D-06 (install-time self-verification), D-10 (preflight abort style)
- `infra/observability/values-trimmed.yaml` — `serviceMonitorSelectorNilUsesHelmValues: false` already set (line ~73); the values this stack runs with
- `scripts/observability-up.sh` — the script D-01/D-02/D-10 extend; existing step structure and self-verify style to mirror
- `scripts/observability-down.sh` — teardown whose namespace sweep D-04 relies on; must NOT gain a ServiceMonitor delete step

### Scrape targets (read-only — MUST NOT be modified)
- `charts/field-guide-api/templates/service.yaml` — Service labels (`app.kubernetes.io/name` via helpers) and named `http` port the selector matches
- `charts/launchpad/templates/service.yaml` — same for launchpad
- `charts/field-guide-api/templates/_helpers.tpl` / `charts/launchpad/templates/_helpers.tpl` — the label helpers that lock selector stability

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/observability-up.sh`: already has a numbered-step structure ending in "Step 4: Re-verifying v1.1 apps" (runs `make smoke` + `make smoke-launchpad`) — the ServiceMonitor apply + `up == 1` verify slots in as new steps in the same style
- Both app Services already expose a named `http` port and standard `app.kubernetes.io/name` labels — research verified these are sufficient selectors, zero chart edits needed
- Apps deploy into the `default` namespace via `helm upgrade --install` with release names `field-guide-api` / `launchpad` (Makefile `RELEASE` / `LP_RELEASE`), so Service names = job names

### Established Patterns
- Self-verifying idempotent scripts with actionable abort messages (cluster-setup.sh, observability-up.sh preflight)
- Accepted-risk / lifecycle notes documented in `docs/known-limitations.md`
- POSIX/Git-Bash-safe scripting, LF endings, many small lowercase conventional commits
- Human-verify checkpoint task at the end of live-cluster phases (Phase 11 Task 2 precedent)

### Integration Points
- Phase 13 dashboards will query the series these ServiceMonitors produce; the 15s interval (D-08) allows ≥ 1m rate windows
- Phase 14 wraps the extended `observability-up.sh` in `make observability-up` — no logic re-implementation
- Phase 15's diagnostics self-check row (`up == 1` per target) queries the same series names locked here (D-05)

</code_context>

<specifics>
## Specific Ideas

- Warning and abort messages must be actionable for a Windows/Docker Desktop operator — name the exact command to run next, matching the Phase 11 preflight message style.
- The 15s interval exists specifically so demo dashboards and metric cards feel live within seconds of seeded traffic — don't quietly bump it up for thrift.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. (Pre-existing deferrals — Loki, Alertmanager, SLO panels — remain tracked in REQUIREMENTS.md Future Requirements.)

</deferred>

---

*Phase: 12-ServiceMonitor Scraping*
*Context gathered: 2026-07-16*
