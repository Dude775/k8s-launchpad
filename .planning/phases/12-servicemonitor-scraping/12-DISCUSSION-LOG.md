# Phase 12: ServiceMonitor Scraping - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-16
**Phase:** 12-ServiceMonitor Scraping
**Areas discussed:** Apply mechanism & lifecycle, Job naming & manifest layout, Scrape tuning, Verification approach

---

## Apply Mechanism & Lifecycle

### How should the ServiceMonitor manifests get applied?

| Option | Description | Selected |
|--------|-------------|----------|
| Extend observability-up.sh | Add apply step after stack Ready; one lifecycle, one command; matches Phase 14 expectation | ✓ |
| Separate apply script | New scripts/servicemonitors-apply.sh; Phase 14 chains them | |
| Documented kubectl apply only | Manifests + docs note; no wiring until Phase 14 | |

**User's choice:** Extend observability-up.sh (Recommended)

### Teardown behavior for ServiceMonitor objects

| Option | Description | Selected |
|--------|-------------|----------|
| Leave them in place | Inert without operator; survive per D-01 CRD retention; rediscovered on next up | ✓ |
| Delete them on down | kubectl delete -f in observability-down.sh; symmetric but adds a failure mode | |

**User's choice:** Leave them in place (Recommended)
**Notes:** Later reconciled with the namespace choice — see "Reconcile" below.

### Missing-CRD case

| Option | Description | Selected |
|--------|-------------|----------|
| Guard + actionable abort | Check servicemonitors.monitoring.coreos.com before apply; abort naming the fix | ✓ |
| No guard — let kubectl fail | Raw 'no matches for kind ServiceMonitor' error | |
| You decide | Claude's discretion | |

**User's choice:** Guard + actionable abort (Recommended)

### Apps not deployed when observability-up.sh runs

| Option | Description | Selected |
|--------|-------------|----------|
| Apply anyway + warn | ServiceMonitor without matching Service is valid; warn, skip up==1 for missing apps | ✓ |
| Abort — require apps first | Preflight failure enforcing up-all before observability-up | |
| You decide | Claude's discretion | |

**User's choice:** Apply anyway + warn (Recommended)

---

## Job Naming & Manifest Layout

### Job names in Prometheus

| Option | Description | Selected |
|--------|-------------|----------|
| Use Service-name defaults | up{job="field-guide-api"} / up{job="launchpad"} out of the box; zero relabeling | ✓ |
| Pin explicit jobLabel/relabeling | Hard-code job names against Service renames | |

**User's choice:** Use Service-name defaults (Recommended)

### Namespace for the ServiceMonitor objects

| Option | Description | Selected |
|--------|-------------|----------|
| observability namespace | Lives with the stack; needs namespaceSelector → default | ✓ |
| default namespace | Beside the Services; survives namespace teardown | |

**User's choice:** observability namespace (Recommended)

### Reconcile: namespace sweep vs "leave them in place"

| Option | Description | Selected |
|--------|-------------|----------|
| Accept the sweep | 'Leave in place' = no explicit delete step; namespace deletion removes them; re-applied on every up | ✓ |
| Move them to default instead | Genuinely survive teardown untouched | |

**User's choice:** Accept the sweep (Recommended)
**Notes:** Conflict surfaced during discussion — observability-down.sh deletes the observability namespace (Phase 11 D-02), which sweeps ServiceMonitors living there.

### Manifest file layout

| Option | Description | Selected |
|--------|-------------|----------|
| One file per app | servicemonitor-field-guide-api.yaml + servicemonitor-launchpad.yaml | ✓ |
| Single combined file | One servicemonitors.yaml with --- separator | |
| Subdirectory servicemonitors/ | Dedicated folder, applied as directory | |

**User's choice:** One file per app (Recommended)

---

## Scrape Tuning

### Scrape interval

| Option | Description | Selected |
|--------|-------------|----------|
| 15s explicit | Snappiest demo; Phase 13 gets 1m rate windows; negligible cost for two targets | ✓ |
| 30s — inherit stack default | Lighter, one less knob; windows ≥ 2m | |
| 60s conservative | Lightest; windows ≥ 4m; demo loses real-time feel | |

**User's choice:** 15s explicit (Recommended)

### Other scrape parameters

| Option | Description | Selected |
|--------|-------------|----------|
| Defaults + discretion | path /metrics default, named http port, scrapeTimeout 10s default | ✓ |
| Pin everything explicitly | Self-documenting YAML even where values equal defaults | |

**User's choice:** Defaults + discretion (Recommended)

---

## Verification Approach

### How to perform the up == 1 verification

| Option | Description | Selected |
|--------|-------------|----------|
| Self-verifying script step | observability-up.sh polls Prometheus query API until both jobs return 1; actionable abort on timeout | ✓ |
| Separate verify script | Standalone scripts/verify-scraping.sh runnable anytime | |
| Manual documented check | Port-forward + PromQL by hand | |

**User's choice:** Self-verifying script step (Recommended)

### Human checkpoint on the Targets page

| Option | Description | Selected |
|--------|-------------|----------|
| Automated + human checkpoint | One task ends with operator confirming both jobs UP on Targets page | ✓ |
| Automated only | Scripted check covers the criterion; fully autonomous phase | |

**User's choice:** Automated + human checkpoint (Recommended)

### End state after the phase

| Option | Description | Selected |
|--------|-------------|----------|
| Torn down again | Full up → verify → down lifecycle; matches Phase 11 convention; proves re-apply on reinstall | ✓ |
| Leave stack running | Ready for Phase 13 immediately, but breaks the convention and occupies ~516Mi between phases | |

**User's choice:** Torn down again (Recommended)

---

## Claude's Discretion

- Mechanism for reaching the Prometheus query API from the script (port-forward vs in-cluster curl vs exec) and poll/timeout values
- Exact wording of warnings/abort messages (Phase 11 actionable-message style)
- kubectl apply on explicit files vs glob (as long as one-file-per-app layout holds)
- Poll timeout headroom for first-scrape appearance (~30-60s typical)

## Deferred Ideas

None — discussion stayed within phase scope.
