---
phase: 03
status: secured
threats_total: 12
threats_closed: 12
threats_open: 0
audited: 2026-07-07
---

# SECURITY AUDIT — Phase 03: Containerization + Helm Deployment

**Audited:** 2026-07-07
**Phase:** 03 — Containerization + Helm Deployment
**Plans audited:** 03-01 through 03-04 (plus 03-REVIEW-FIX.md post-execution fixes)
**ASVS Level:** Default
**Block on:** Default (open threats block)
**Threats Closed:** 12/12
**Blockers:** 0

---

## Threat Verification

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-03-01 | Elevation of Privilege | mitigate | CLOSED | Dockerfile:27-28 — `groupadd -r -g 10001 app && useradd -r -u 10001 -g app app` + `USER 10001`; deployment.yaml:37-41 — `runAsNonRoot: true`, `runAsUser: 10001` at pod level; deployment.yaml:80-82 — `allowPrivilegeEscalation: false` at container level |
| T-03-02 | Tampering / supply chain | mitigate | CLOSED | .dockerignore:6 — `.venv/` excluded; Dockerfile:21-23 — explicit `COPY app/ ./app/` + `COPY wsgi.py .` (no broad `COPY . .`); both layers present for defense-in-depth |
| T-03-03 | Information Disclosure | mitigate | CLOSED | Dockerfile — `FLASK_DEBUG` ENV absent (grep count 0); configmap.yaml:14 — `FLASK_DEBUG` sourced from `.Values.config.flaskDebug`; values.yaml:36 — `flaskDebug: ""` (empty string = disabled) |
| T-03-04 | Information Disclosure | mitigate | CLOSED | values.yaml:52-53 — password `fieldguide-dev-password` with inline comment "local kind only; never a real credential — override with --set mongodb.auth.password=<real> for anything real" |
| T-03-05 | Information Disclosure | mitigate | CLOSED | secret.yaml:24 — `MONGO_URI` rendered via `stringData` only; configmap.yaml data section — no `MONGO_URI` key (comment at line 3 explains its intentional absence, not a data entry); deployment.yaml:49-53 — `MONGO_URI` injected via `secretKeyRef` (no literal value); NOTES.txt — no MONGO_URI, no authSource, no password value (grep count 0) |
| T-03-06 | Elevation of Privilege | mitigate | CLOSED | mongodb/service.yaml:14-19 — `type: ClusterIP`, port 27017; no `NodePort` or `hostPort` in spec (the word "NodePort" appears only in a comment at line 5 explaining its exclusion) |
| T-03-07 | Elevation of Privilege | mitigate | CLOSED | deployment.yaml:37-41 — pod-level `securityContext: runAsNonRoot: true, runAsUser: 10001`; deployment.yaml:80-82 — container-level `securityContext: allowPrivilegeEscalation: false` |
| T-03-08 | Tampering | mitigate | CLOSED | Makefile:46-49 — `helm upgrade --install $(RELEASE) $(CHART) --set ... --wait --timeout 180s`; `--atomic` absent from entire Makefile (grep count 0) |
| T-03-09 | Information Disclosure | mitigate | CLOSED | Makefile all recipes — no credential echoing; `deploy` target passes only `image.repository` and `image.tag` via `--set`; no password forwarded or printed by any recipe |
| T-03-10 | Information Disclosure | accept | CLOSED | Accepted risk — see Accepted Risks Log below |
| T-03-11 | Denial of Service | mitigate | CLOSED | Process evidence: 03-04-SUMMARY.md line 57 — "All commands run inline as single foreground calls from the executor worktree root (02-02 protocol — no concurrent docker/kind/kubectl commands)" |
| T-03-SC | Tampering | accept | CLOSED | Accepted risk — see Accepted Risks Log below |

---

## Accepted Risks Log

### T-03-10 — Information Disclosure: verification commands

**Category:** Information Disclosure
**Component:** Live smoke-test commands (port-forward, curl, kubectl exec)
**Accepted by:** Phase 03 plan (03-04-PLAN.md threat model)
**Rationale:** Only the committed dev-default credential (`fieldguide-dev-password`) is in play during live verification. No real secret is entered or echoed. `kubectl port-forward` exposes the app on loopback (`localhost:8080`) only and is torn down immediately after smoke-testing. `kubectl exec` verification commands are read-only (id, cat /proc/1/cmdline, python3 urllib GET requests). The residual disclosure surface is bounded to the local developer machine and the committed dummy credential.
**Conditions that would re-open this risk:** Use of a real MongoDB password during verification, or a persistent port-forward left running in a shared environment.

---

### T-03-SC — Tampering: base image + mongo image provenance

**Category:** Tampering (supply chain)
**Component:** `python:3.11-slim` (Dockerfile) and `mongo:7` (Helm chart)
**Accepted by:** Phase 03 plan (03-01-PLAN.md and 03-04-PLAN.md threat models)
**Rationale:** Both images are Docker official library images maintained by Docker, Inc. and subject to the Docker Hub Official Image program (automated CVE scanning, no third-party publisher). This was verified in 03-RESEARCH.md Package Legitimacy Audit. No non-official base images or unvetted PyPI packages were introduced in Phase 03 (requirements.txt unchanged from Phase 01 audit). The optional `kind load docker-image mongo:7` pre-seed during verification (03-04-PLAN.md) further reduces pull-time supply-chain exposure by reusing an already-verified host image.
**Conditions that would re-open this risk:** Switching to a non-official or third-party image; pinning to a digest is recommended before production hardening (Phase 4+).

---

## Post-Execution Security Hardening (03-REVIEW-FIX.md)

Two security-relevant fixes were applied after initial execution and are verified in current code:

**WR-02 — URL-encoding of MongoDB credentials in MONGO_URI**
- **Commit:** b3f35ae
- **Risk addressed:** A raw `@`, `:`, or `/` in a password would shift the parsed URI hostname, causing `InvalidURI` crash-loop or silent authentication bypass.
- **Verification:** secret.yaml:24 — `{{ .Values.mongodb.auth.username | urlquery }}:{{ .Values.mongodb.auth.password | urlquery }}` confirmed present. Applies to both username and password fields.

**WR-07 — Dev-password guard rail in NOTES.txt**
- **Commit:** f82f42e
- **Risk addressed:** No visible signal to operators that the committed dev credential is in use.
- **Verification:** NOTES.txt:2-7 — conditional `!! WARNING` block renders on every install/upgrade when `mongodb.enabled=true` and the password equals `fieldguide-dev-password`. The password value is not echoed; the block prints only the remediation command (`--set mongodb.auth.password=<real-password>`). The warning disappears when an overriding password is supplied.

---

## Unregistered Flags

None. All threat flags in 03-01-SUMMARY.md `## Threat Flags` map to existing registered threats (T-03-01, T-03-02, T-03-03). Summaries 03-02, 03-03, and 03-04 declare no new attack surface beyond the registered threat model.

---

## Files Verified

| File | Threats Verified |
|------|-----------------|
| `apps/field-guide-api/Dockerfile` | T-03-01, T-03-02, T-03-03 |
| `apps/field-guide-api/.dockerignore` | T-03-02 |
| `Makefile` | T-03-08, T-03-09 |
| `charts/field-guide-api/values.yaml` | T-03-04 |
| `charts/field-guide-api/templates/deployment.yaml` | T-03-01, T-03-05, T-03-07 |
| `charts/field-guide-api/templates/secret.yaml` | T-03-05 (WR-02) |
| `charts/field-guide-api/templates/configmap.yaml` | T-03-03, T-03-05 |
| `charts/field-guide-api/templates/service.yaml` | T-03-06 (app service) |
| `charts/field-guide-api/templates/NOTES.txt` | T-03-05 (WR-07) |
| `charts/field-guide-api/templates/mongodb/deployment.yaml` | T-03-06 |
| `charts/field-guide-api/templates/mongodb/service.yaml` | T-03-06 |
| `charts/field-guide-api/templates/mongodb/secret.yaml` | T-03-05 |
| `.planning/phases/03-containerization-helm-deployment/03-04-SUMMARY.md` | T-03-11 (process evidence) |
