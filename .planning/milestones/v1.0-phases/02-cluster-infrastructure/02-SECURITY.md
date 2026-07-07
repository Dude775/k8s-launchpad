---
phase: 02
slug: cluster-infrastructure
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-05
---

# Phase 02 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| host → local registry | Images pushed from developer host to `localhost:5001` (unauthenticated) | Container images (local dev only) |
| cluster pod → registry | Pods pull images over the `kind` docker network via `kind-registry:5000` (HTTP) | Container images |
| host filesystem → git | Cluster credentials (`~/.kube/config`) must never enter the repo | kubeconfig credentials |
| developer → host tooling | One-time `winget install Kubernetes.kind` introduces the kind binary | Executable provenance |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-02-01 | Elevation of Privilege | `registry:3` port binding | mitigate | `docker run -p "127.0.0.1:5001:5000"` (cluster-setup.sh:53); zero `0.0.0.0` occurrences; live-verified 2026-07-05 (twice): `docker port kind-registry` → `127.0.0.1:5001` only | closed |
| T-02-02 | Information Disclosure | kubeconfig credentials | mitigate | kind writes to `~/.kube/config` (system path); `.gitignore:36-39` covers `kubeconfig`, `*.kubeconfig`, `.kube/`; live-verified: `git status` clean of kube artifacts after cluster-up | closed |
| T-02-03 | Information Disclosure | HTTP node→registry traffic | accept | Intentional: loopback-scoped `kind` docker network, `hosts.toml` uses `http://kind-registry:5000` by design; no external exposure | closed |
| T-02-04 | Tampering | image content in local registry | accept | Local single-user dev registry; only the developer pushes | closed |
| T-02-05 | Spoofing | kind binary provenance | mitigate | kind v0.32.0 installed via official channel only (winget `Kubernetes.kind` / kind.sigs.k8s.io download per 02-02-PLAN user_setup); `kind version` confirms v0.32.0 | closed |
| T-02-SC | Tampering | runtime images (`registry:3`, `kindest/node:v1.36.1`, `alpine:3.20`) | mitigate | All official images (Docker library / kind project defaults) per 02-RESEARCH Package Legitimacy Audit; no package-manager installs in this phase | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

Hardening note (beyond register): code review CR-01 fix (`3a561a9`) pinned all kubectl calls to `--context=kind-kind`, eliminating the cross-cluster mutation hazard on idempotent re-runs; smoke-tested live 2026-07-05.

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-02-01 | T-02-03 | HTTP registry traffic is loopback-scoped inside the kind docker network; TLS adds complexity with zero exposure reduction for local dev | Plan 02-01 threat model (developer-approved plan) | 2026-07-05 |
| AR-02-02 | T-02-04 | Single-user local dev registry; only the developer pushes; no shared or production use in PRD-1 | Plan 02-01 threat model (developer-approved plan) | 2026-07-05 |

*Accepted risks do not resurface in future audit runs.*

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-05 | 6 | 6 | 0 | gsd secure-phase (short-circuit: plan-time register, all mitigations live-verified) |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-07-05
