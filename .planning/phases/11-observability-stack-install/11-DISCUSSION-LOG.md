# Phase 11: Observability Stack Install - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-16
**Phase:** 11-Observability Stack Install
**Areas discussed:** CRD teardown policy, Install mechanism, Grafana admin credentials, Resource sizing strategy

---

## CRD Teardown Policy

| Option | Description | Selected |
|--------|-------------|----------|
| Keep CRDs | helm uninstall only; CRDs stay. Faster re-install, zero risk to running apps, matches Helm's default. Documented in known-limitations.md | ✓ |
| Two-tier: keep + purge flag | Default keeps CRDs; opt-in flag (OBS_PURGE_CRDS=1) also deletes CRDs and namespace | |
| Always delete CRDs | Full pristine teardown; slower re-up, cascade-deletes ServiceMonitors | |

**User's choice:** Keep CRDs

| Option | Description | Selected |
|--------|-------------|----------|
| Delete namespace | helm uninstall then delete observability namespace — sweeps leftover PVCs/secrets; CRDs survive (cluster-scoped) | ✓ |
| Keep namespace | Only the Helm release removed; leftovers stay | |
| You decide | Claude picks during planning | |

**User's choice:** Delete namespace

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, built-in check | Teardown ends with health verification of both v1.1 apps — matches self-verifying script style | ✓ |
| No, manual smoke | Operator runs make smoke themselves | |
| You decide | Claude picks during planning | |

**User's choice:** Yes, built-in app-survival check

---

## Install Mechanism

| Option | Description | Selected |
|--------|-------------|----------|
| Wrapper script | scripts/observability-up.sh + observability-down.sh mirroring cluster-setup.sh: idempotent, self-verifying; Phase 14 wraps them | ✓ |
| Plain helm commands | Documented helm upgrade --install, no script layer | |
| You decide | Claude picks during planning | |

**User's choice:** Wrapper scripts

| Option | Description | Selected |
|--------|-------------|----------|
| Helm repo + pin | helm repo add prometheus-community + --version 87.16.1 | ✓ |
| Vendored chart tarball | Commit the .tgz into infra/observability/vendor/ | |
| You decide | Claude picks during planning | |

**User's choice:** Helm repo + version pin

| Option | Description | Selected |
|--------|-------------|----------|
| Full self-verify | Wait for observability pods Ready, then re-check v1.1 app pods healthy on every install | ✓ |
| Pods Ready only | Only wait for the stack itself; v1.1 verification manual | |
| You decide | Claude picks during planning | |

**User's choice:** Full self-verify

---

## Grafana Admin Credentials

| Option | Description | Selected |
|--------|-------------|----------|
| Explicit value in values file | Known local-dev password in values-trimmed.yaml, documented per the v1.1 mongo-password accepted-risk precedent | ✓ |
| Chart default (prom-operator) | Change nothing; document the upstream default | |
| .env-driven | Password from .env via --set at install | |

**User's choice:** Explicit value in values file

| Option | Description | Selected |
|--------|-------------|----------|
| Anonymous viewer on | grafana.ini anonymous auth, Viewer role — Phase 15 deep links open without a login wall; admin login retained | ✓ |
| Login required | Standard auth flow; demo viewer logs in once | |
| You decide | Claude picks during planning | |

**User's choice:** Anonymous viewer on

---

## Resource Sizing Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Conservative first, tune live | Research-derived conservative requests/limits from first install, then kubectl top + tune in-phase | ✓ |
| Measure first, then cap | Unbounded first install, set limits from observed usage | |
| You decide | Claude picks during planning | |

**User's choice:** Conservative first, tune live

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, warn-and-abort | Preflight: sum stack requests vs node allocatable minus running workloads; abort with actionable message if it won't fit | ✓ |
| Warn only | Same check, proceeds after warning | |
| No preflight | Rely on conservative limits + post-install check | |

**User's choice:** Yes, warn-and-abort preflight

| Option | Description | Selected |
|--------|-------------|----------|
| emptyDir + short retention | No PVC; retention ~24h — enough for Phase 13 rolling windows; lightest footprint | ✓ |
| Small PVC (2-5Gi) | Metrics survive restarts via hostPath; more disk pressure, PVC to sweep | |
| You decide | Claude picks during planning, coordinating with Phase 13 windows | |

**User's choice:** emptyDir + ~24h retention

---

## Claude's Discretion

- Exact per-component request/limit numbers in values-trimmed.yaml (live-tuned)
- Helm --wait/timeout strategy vs script-level kubectl wait loops
- values file layout within infra/observability/
- Double-run idempotency details for both scripts
- Scrape interval default (coordinate with Phase 13 rate-window sizing)

## Deferred Ideas

None — discussion stayed within phase scope.
