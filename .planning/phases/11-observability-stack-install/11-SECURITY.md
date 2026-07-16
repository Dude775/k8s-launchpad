---
phase: 11
slug: observability-stack-install
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-16
---

# Phase 11 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| operator shell → kind cluster | Local operator drives cluster mutations via helm/kubectl, including destructive teardown | kubeconfig-authenticated commands; no untrusted network input |
| Helm chart repo → cluster | Third-party chart content pulled from prometheus-community repo | kube-prometheus-stack chart 87.16.1 (pinned, legitimacy-audited) |
| operator browser → port-forwarded Grafana/Prometheus | localhost-only access; no external exposure | metrics/dashboards; anonymous Viewer role |
| observability namespace → app namespace | Shared kind node; resource contention is the only coupling | none (resource pressure only) |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-11-01 | Information Disclosure | committed `grafana.adminPassword` in values-trimmed.yaml | accept | Obviously-fake local-dev value `grafana-dev-password` (`infra/observability/values-trimmed.yaml:46`); documented with override command in `docs/known-limitations.md:72-82`; port-forward-only reachability | closed |
| T-11-02 | Denial of Service | unbounded component resources evicting v1.1 app pods on shared kind node | mitigate | Explicit requests/limits on all four kept-enabled components (`values-trimmed.yaml:37-72`); preflight capacity gate in `scripts/observability-up.sh:54-77`; post-install `make smoke`/`smoke-launchpad` re-check (`observability-up.sh:126-129`); live-verified in 11-04-SUMMARY (Burstable QoS) | closed |
| T-11-03 | Elevation of Privilege | Grafana/Prometheus exposed beyond localhost | mitigate | No Ingress/NodePort/LoadBalancer keys anywhere in `values-trimmed.yaml` (grep-verified zero matches); access via `kubectl port-forward` only (`observability-up.sh:132-133`) | closed |
| T-11-SC | Tampering | Helm chart supply chain (kube-prometheus-stack) | mitigate | Version pinned to 87.16.1 in `values-trimmed.yaml:13` and `observability-up.sh:94`; legitimacy audit Approved via live `helm repo`/`helm pull` round-trip (11-RESEARCH.md:165-180) | closed |
| T-11-04 | DoS / Tampering | teardown blast radius affecting v1.1 apps | mitigate | `scripts/observability-down.sh:20-32` scopes uninstall to release + `observability` namespace only; no CRD deletion; post-teardown smoke re-check (`observability-down.sh:44-46`); live-verified in 11-03-SUMMARY (namespace NotFound, 10 CRDs retained, both apps 0 restarts) | closed |
| T-11-05 | Information Disclosure | committed Grafana password value appearing in docs | accept | Explicit accepted-risk section in `docs/known-limitations.md:72-82` naming the fake value, mirroring the MongoDB committed-password convention | closed |
| T-11-06 | Info Disclosure / EoP | anonymous Grafana Viewer access (D-08) | accept | Scoped to `Viewer` role only (`values-trimmed.yaml:47-50`); documented in `docs/known-limitations.md:133-138`; human-verified live as Viewer-only over localhost port-forward (11-03-SUMMARY Task 2) | closed |
| T-11-01(P4) | Denial of Service | kube-state-metrics pod BestEffort → unbounded memory | mitigate | 32Mi request / 64Mi limit under correct top-level `kube-state-metrics:` subchart key (`values-trimmed.yaml:37-40`, commit 59044ce); live pod confirmed `qosClass=Burstable` (11-04-SUMMARY) | closed |
| T-11-02(P4) | Denial of Service | teardown skipped leaves stack installed (~516Mi) | accept | Torn-down end state restored (11-04-SUMMARY: namespace NotFound); ample headroom measured (~9.18 GiB vs ~516Mi) in `docs/known-limitations.md:97-115`; smoke gate catches any eviction | closed |
| T-11-SC(P4) | Tampering | helm/chart installs in plan 04 | accept | Values-only change verified via git diffs (59044ce, c8e2f17) — no Chart.yaml/chart-source changes, no new package installs; chart remains pinned 87.16.1 | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-11-01 | T-11-01, T-11-05 | Committed Grafana admin password is an obviously-fake local-dev value (`grafana-dev-password`), reachable via localhost port-forward only; mirrors the established MongoDB committed-password convention; never a real credential | David Rubin (plan-time disposition) | 2026-07-16 |
| AR-11-02 | T-11-06 | Anonymous Grafana access limited to Viewer role over localhost port-forward; intentional demo-friction tradeoff, live-verified as Viewer-only | David Rubin (plan-time disposition) | 2026-07-16 |
| AR-11-03 | T-11-02(P4) | If `observability-down` is skipped the stack persists consuming ~516Mi against ~9.18 GiB measured headroom; app-survival smoke gate would catch any eviction. Doc note: known-limitations.md covers the headroom measurement but lacks an explicit "if teardown skipped" sentence — low-severity, non-blocking | David Rubin (plan-time disposition) | 2026-07-16 |
| AR-11-04 | T-11-SC(P4) | No new package installs in the resources fix; chart pinned and previously vetted | David Rubin (plan-time disposition) | 2026-07-16 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-16 | 10 | 10 | 0 | gsd-security-auditor (State B — register built from 11-01..11-04 PLAN threat models; no SUMMARY threat flags found) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-16
