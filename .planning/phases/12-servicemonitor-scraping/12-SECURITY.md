---
phase: 12
slug: servicemonitor-scraping
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-20
---

# Phase 12 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| operator shell → Prometheus HTTP API | Install script queries /api/v1/query over a local port-forward (localhost-only, same pattern as make smoke) | PromQL queries + scrape-state responses (non-sensitive, local) |
| ServiceMonitor namespaceSelector → cluster namespaces | Declares which namespaces Prometheus searches for scrape targets | Scrape-target discovery scope |
| operator localhost → Prometheus HTTP/UI | port-forward to 9090 for self-verify and the Targets page; local-only, no ingress/TLS | Metrics + target metadata (local single-tenant) |
| teardown → cluster state | observability-down deletes a namespace and uninstalls a release on the local kind cluster | Cluster resource deletion (scoped to observability namespace) |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-12-01 | Information Disclosure | ServiceMonitor.spec.namespaceSelector | mitigate | `matchNames: ["default"]` pinned in both manifests (`infra/observability/servicemonitor-*.yaml:12-13`) — never wildcard, future namespaces not accidentally scraped. Post-review hardening: `matchExpressions` also excludes mongodb Services (WR-03) | closed |
| T-12-02 | Tampering | curl PromQL query string under Git Bash | mitigate | Job names are hardcoded constants (`for job in field-guide-api launchpad`, `scripts/observability-up.sh:146`); query sent via `curl -G --data-urlencode` (line 192) so the matcher is percent-encoded — no shell/PromQL injection surface | closed |
| T-12-03 | Denial of Service | up==1 poll loop | accept | Bounded per-job 150s deadline with 5s sleep, `--max-time 10` per curl (post-review WR-04/CR-01 hardening); no unbounded/watch wait. Local single-tenant kind cluster | closed |
| T-12-04 | Elevation of Privilege | port-forward exposes Prometheus on localhost:9090 | accept | Local single-tenant kind cluster, no ingress/TLS by project scope (docs/known-limitations.md); port-forward is operator-initiated, script kills it via EXIT trap | closed |
| T-12-05 | Denial of Service | teardown deletes the observability namespace | mitigate | `delete namespace --ignore-not-found` (`scripts/observability-down.sh:38`) + trailing `make smoke` / `make smoke-launchpad` (lines 45-46) prove v1.1 apps survive; D-04 keeps the down script unchanged so no ServiceMonitor-delete race | closed |
| T-12-SC | Tampering | npm/pip/cargo installs | accept | No package installs, no new container images in this phase — two static YAML manifests + bash edits only; Package Legitimacy Gate not applicable | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-12-01 | T-12-03 | Poll loop is bounded (per-job 150s deadline, 10s curl timeout); residual DoS exposure limited to the operator's own local shell on a single-tenant kind cluster | operator (plan 12-01 disposition) | 2026-07-20 |
| AR-12-02 | T-12-04 | Prometheus exposed only on operator-initiated localhost port-forward; no ingress/TLS is explicit project scope, documented in docs/known-limitations.md | operator (plan 12-02 disposition) | 2026-07-20 |
| AR-12-03 | T-12-SC | No supply-chain surface added this phase (no installs, no new images) | operator (plan dispositions) | 2026-07-20 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-20 | 6 | 6 | 0 | /gsd-secure-phase (plan-time register, short-circuit verification — all mitigate dispositions verified against implementation files) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-20
