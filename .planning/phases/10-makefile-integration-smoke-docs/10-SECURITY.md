---
phase: 10
slug: makefile-integration-smoke-docs
status: verified
threats_open: 0
asvs_level: 1
created: 2026-07-14
---

# Phase 10 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| developer shell → Makefile recipe | make expands variables and shell interpolations into shell commands run on the host | developer commands, LP_* variables |
| Makefile recipe → kubectl exec → Mongo pod | mongosh credentials appear on the exec command line (read from in-cluster secret at runtime since fix ffc104e) | MongoDB credentials (local-dev) |
| local port-forward (8081) → in-cluster Service | local HTTP smoke traffic reaches the dashboard pod | HTTP demo traffic |
| running dashboard → screenshot capture | rendered pages captured to PNGs committed to the repo | rendered UI state |
| terminal output → committed README | captured command output embedded in a public README | command output text |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-10-01 | Tampering | pkill -f pattern in smoke-launchpad | mitigate | Pattern scoped to `svc/$(LP_RELEASE)` (distinct from field-guide-api), no cross-kill possible; WR-03 fix (ed8653b) added `command -v pkill` availability gate without widening the pattern (Makefile:73-74,121-122) | closed |
| T-10-02 | Information Disclosure | mongosh credentials in verify-ttl | accept | Improved post-plan by WR-01 fix (ffc104e): hardcoded password removed, credentials read from in-cluster secret `$(LP_RELEASE)-mongodb` at runtime, referenced only via shell vars; PASS/FAIL echoes never leak raw getIndexes output; accepted-risk documented in docs/known-limitations.md | closed |
| T-10-03 | Denial of Service | up-all `--wait --timeout 180s` on deploy-launchpad | accept | Bounded 180s timeout present (Makefile:114); failure surfaces as non-zero exit, not a hang | closed |
| T-10-04 | Elevation of Privilege | Makefile targets wrap docker/helm/kubectl | accept | No new credentials or scopes beyond developer's existing kube/docker context | closed |
| T-10-05 | Information Disclosure | screenshots + captured terminal output in README/docs | mitigate | Local-dev demo state only; five PNGs human-reviewed for secrets at the 10-02 Task 1 checkpoint before approval; README /health output contains no credentials | closed |
| T-10-06 | Spoofing | markdown image embeds in README | accept | All five embeds use local relative docs/screenshots/*.png paths (README.md:121-137); no remote image sources | closed |
| T-10-SC | Tampering | package installs | mitigate | No new package-manager installs introduced in either plan (Makefile + docs edits only); pre-existing pip install in test targets untouched | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-10-01 | T-10-02 | MongoDB credentials appear on kubectl exec command lines / process listings during verify-ttl; local kind cluster only, local-dev credentials, documented in docs/known-limitations.md | David (via plan approval + secure-phase run) | 2026-07-14 |
| AR-10-02 | T-10-03 | deploy-launchpad can consume up to 180s before failing on an unhealthy rollout; bounded and surfaces non-zero exit | David (via plan approval + secure-phase run) | 2026-07-14 |
| AR-10-03 | T-10-04 | Makefile targets execute with the developer's full existing docker/kube privileges; no reduction attempted since targets wrap commands the developer already runs by hand | David (via plan approval + secure-phase run) | 2026-07-14 |
| AR-10-04 | T-10-06 | README image integrity relies on repo integrity (local relative paths); acceptable for a portfolio repo | David (via plan approval + secure-phase run) | 2026-07-14 |

*Accepted risks do not resurface in future audit runs.*

---

## Unregistered Flags (non-blocking, tracked)

- **IN-02 (10-REVIEW.md, open info finding):** `verify-ttl` pod selection uses `.items[0]` without `--field-selector=status.phase=Running` and misreports exec/auth failures as "no TTL index". Touches the T-10-02 trust boundary but is a diagnostic-accuracy gap, not a credential-exposure path. Not a blocker under `block_on: critical`.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-07-14 | 7 | 7 | 0 | gsd-security-auditor (sonnet) via /gsd-secure-phase |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter
