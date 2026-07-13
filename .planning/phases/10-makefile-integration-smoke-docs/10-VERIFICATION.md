---
phase: 10-makefile-integration-smoke-docs
verified: 2026-07-14T02:50:00Z
status: human_needed
score: 16/16 must-haves verified
overrides_applied: 0
human_verification:
  - test: "REQUIREMENTS.md checkbox/traceability update for DEP-04, DEP-05, DOCS-01"
    expected: "Checkboxes marked [x] and traceability table rows changed from Pending to Complete now that Phase 10 is done and both SUMMARY.md files declare requirements-completed"
    why_human: "Not a codebase functionality gap — a bookkeeping/tracking artifact update that a human or a follow-up doc commit should apply; verifier cannot silently edit REQUIREMENTS.md on the phase's behalf"
---

# Phase 10: Makefile Integration + Smoke + Docs Verification Report

**Phase Goal:** `make up-all` brings both apps up end-to-end in a single command and the dashboard is demoable to a human reviewer via the browser
**Verified:** 2026-07-14T02:50:00Z
**Status:** human_needed (all automated must-haves verified; one tracking-doc item needs human/follow-up action — see below)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| D-01 | `make up-all` brings up the cluster and deploys both field-guide-api and launchpad without error | VERIFIED | `Makefile:140` `up-all: up build-launchpad load-launchpad deploy-launchpad`; live-verified this session — exit 0, epilogue printed |
| D-02 | `make deploy-launchpad` runs `helm upgrade --install` with `--wait --timeout 180s` | VERIFIED | `Makefile:57-60`; no `--atomic` present |
| D-05 | `make smoke-launchpad` returns 200 for `/`, `/health`, `/api/status` from localhost:8081 | VERIFIED | `Makefile:65-82`; live-verified this session, all PASS |
| D-06 | `make smoke-all` proves both apps with one command after up-all | VERIFIED | `Makefile:146` `smoke-all: smoke smoke-launchpad`; live-verified — both apps 200 across all endpoints |
| D-04 | `make help` lists all six launchpad targets with one-line descriptions grouped by section, field-guide targets still shown | VERIFIED (with cosmetic defect noted) | All six launchpad targets (`build-launchpad`, `load-launchpad`, `deploy-launchpad`, `port-forward-launchpad`, `smoke-launchpad`, `test-launchpad`) and all field-guide-api targets render with descriptions under `##@` headers (`Makefile:30`, `32`, `40`, `114`, `121`, `184`). Literal must-have wording is satisfied. Code review WR-05 flags that `##@ field-guide-api` appears twice (lines 32 and 121) and the cross-app aggregates (`up`, `up-all`, `smoke-all`, `check-tools`) are miscategorized under the second field-guide-api header rather than a distinct "Stack"/"Aggregate" section — a real cosmetic/organizational defect, not a functional failure of the must-have as worded |
| D-07 | `make verify-ttl` confirms the `expireAfterSeconds` TTL index exists on the launchpad events collection | VERIFIED | `Makefile:87-94`; live-verified this session — "PASS events.ts TTL index present". Note: the opt-in `TTL_DEEP=1` deep round-trip mode (CR-01, critical) is mathematically incapable of passing against the default 7-day TTL and is NOT part of this must-have's literal wording — see Anti-Patterns/Gaps below for the documentation-accuracy issue this creates in `docs/known-limitations.md` |
| D-08 | `make port-forward-launchpad` runs a foreground `kubectl port-forward svc/launchpad 8081:80` | VERIFIED | `Makefile:62-63` |
| D-09 | `up-all` ends with an echo epilogue pointing at `port-forward-launchpad`, `http://localhost:8081`, and `smoke-all` | VERIFIED | `Makefile:141-144`; live-verified this session — epilogue printed exactly as specified |
| D-03 | `make reset-local` undeploys BOTH releases before tearing down the cluster | VERIFIED | `Makefile:202-204`: `undeploy` then `undeploy-launchpad || true` then `cluster-down` |
| D-10 | README headline demo leads with `make up-all` then opening `http://localhost:8081` in a browser | VERIFIED | `README.md:8-28`, `78-96` |
| D-11 | README embeds real captured screenshots of the running dashboard from `docs/screenshots/` | VERIFIED | 5 real PNGs on disk (`dashboard.png`, `catalog.png`, `onboard-form.png`, `diagnostics.png`, `feed.png`, 28KB-137KB each — non-trivial sizes consistent with real screenshots, not stubs); all 5 embedded via markdown image syntax at `README.md:121,125,129,133,137`; human-reviewed live this session for absence of secrets |
| D-13 | README `/health` example shows real captured terminal output, not typed compact JSON | VERIFIED | `README.md:167-168` shows `{"status": "ok", "mongo": "up"}` — matches the live-verification context's captured curl output exactly |
| D-12 (troubleshooting) | `docs/troubleshooting.md` documents launchpad-specific port 8081 / NotReady / stale-forward failure modes | VERIFIED | `docs/troubleshooting.md:19-20` — two new rows for stale port-8081 forward and launchpad-mongodb NotReady, in the existing table shape |
| D-12 (known-limitations) | `docs/known-limitations.md` documents the committed launchpad-dev-password, the open WR-01 mongoUri issue, and live-only TTL verification | VERIFIED (with accuracy caveat) | `docs/known-limitations.md:31-47` (password), `49-67` (WR-01 mongoUri), `84-96` (TTL live-only). The TTL entry's claim "This closes the Phase 9 FEED-03 'verify live' flag" is not fully accurate — see Gaps below |
| — | `.planning/PROJECT.md` no longer claims the Phase 7 degraded-CSS gap is open | VERIFIED | `.planning/PROJECT.md:119` — explicitly records the gap as FIXED in Phase 7 commit `c977206`, WR-01 mention correctly repointed at the mongoUri issue |
| — | Existing Docker/Helm setup docs (Architecture, Prerequisites, Security Note) remain intact | VERIFIED | `README.md:30-42` (Architecture), `59-76` (Prerequisites), `197-214` (Security Note) all present and unmodified in substance |

**Score:** 16/16 truths verified (all literal must-have wording satisfied; 2 items carry noted quality caveats that do not invalidate the truth as worded — see Gaps/Anti-Patterns)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `Makefile` | filled launchpad targets, up-all, smoke-all, undeploy-launchpad, verify-ttl, grouped help, extended clean-venv/reset-local | VERIFIED | All present; `up-all:` string confirmed; all task-1 acceptance-criteria greps pass against current file |
| `README.md` | browser-demo headline + embedded screenshots + real captured outputs | VERIFIED | Confirmed above |
| `docs/screenshots/` | real PNG screenshots of the running dashboard | VERIFIED | 5 files, all non-trivial size, all referenced from README |
| `docs/troubleshooting.md` | launchpad port-forward / NotReady troubleshooting rows | VERIFIED | Confirmed above |
| `docs/known-limitations.md` | launchpad-dev-password + open WR-01 mongoUri + TTL live-only limitation entries | VERIFIED | Confirmed above |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `Makefile` `up-all` target | `up build-launchpad load-launchpad deploy-launchpad` prerequisites | make target prerequisite chain | WIRED | `Makefile:140` exact string match; live-verified this session (real cluster bring-up, exit 0) |
| `Makefile` `deploy-launchpad` target | `charts/launchpad` via `helm upgrade --install` | `LP_RELEASE` / `LP_CHART` variables | WIRED | `Makefile:57-60`; variables declared at `Makefile:16-19`, no hardcoded values |
| `Makefile` `verify-ttl` target | `launchpad-mongodb` pod events collection | `kubectl exec` + `mongosh getIndexes` | WIRED | `Makefile:89-94`; selector `app.kubernetes.io/name=launchpad-mongodb` cross-confirmed against `charts/launchpad/templates/_helpers.tpl` (per code review, "matches launchpad.mongodb.selectorLabels for the default release name"); live-verified PASS this session |
| `README.md` screenshot embeds | `docs/screenshots/*.png` files | markdown image syntax | WIRED | All 5 `![...](docs/screenshots/*.png)` references resolve to files that exist on disk |
| `README.md` headline quickstart | `make up-all` + `port-forward-launchpad` + `localhost:8081` | browser demo flow code fence | WIRED | `README.md:13-28`, `78-96` |

### Behavioral Spot-Checks (Live, Human-Approved Checkpoint Evidence)

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `make up-all` completes end-to-end | `make up-all` | Exit 0, epilogue printed referencing port-forward-launchpad, localhost:8081, smoke-all | PASS |
| Both apps smoke-test clean | `make smoke-all` | field-guide-api `/health` `/entries` `/metrics` all 200; launchpad `/` `/health` `/api/status` all 200 | PASS |
| launchpad smoke alone | `make smoke-launchpad` | PASS | PASS |
| field-guide-api health | `curl -s http://localhost:8080/health` | `{"status": "ok", "mongo": "up"}` | PASS |
| TTL index presence (default mode, matches D-07 wording) | `make verify-ttl` | "PASS events.ts TTL index present" | PASS |
| Test suites | `field-guide-api` (32 tests) / `launchpad` (128 tests) | Both pass, 100% coverage | PASS |

Note: `TTL_DEEP=1` deep-mode round-trip was NOT part of the live-verification context provided and, per code review CR-01, cannot pass against the default 7-day TTL deployment. This is outside the literal D-07 must-have (index existence) but is discussed under Gaps because a shipped doc (`known-limitations.md`) makes a claim about it that the code does not support.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DEP-04 | 10-01-PLAN.md | Namespaced launchpad Makefile targets using LP_ variables, distinct port | SATISFIED | All 6 launchpad targets present, LP_* vars used throughout, port 8081 distinct from field-guide-api's 8080 |
| DEP-05 | 10-01-PLAN.md | `make up-all` end-to-end bring-up; `make smoke-launchpad` verifies dashboard reachable | SATISFIED | Live-verified this session |
| DOCS-01 | 10-02-PLAN.md | README documents browser demo flow as headline, screenshots, existing docs preserved | SATISFIED | Confirmed above |

No orphaned requirements — REQUIREMENTS.md's traceability table maps exactly DEP-04, DEP-05, DOCS-01 to Phase 10, and both PLAN frontmatters declare exactly these IDs.

**Tracking-doc discrepancy (not a functionality gap):** `.planning/REQUIREMENTS.md` still shows `[ ]` (unchecked) for DEP-04, DEP-05, DOCS-01 and lists them as "Pending" in the traceability table (lines 54-55, 59, 129-131), even though both SUMMARY.md files declare `requirements-completed: [DEP-04, DEP-05]` / `[DOCS-01]` and the phase is functionally complete per all evidence above. This should be corrected as a follow-up doc update but does not block the phase goal, which is about the codebase behavior, not the requirements-tracking file.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `Makefile` | 91, 97, 102 | Mongo root password (`launchpad-dev-password`) hardcoded 3x in `verify-ttl` | WARNING (CR WR-01) | Breaks documented password-override path; not a phase-10 must-have failure, but a real robustness gap already tracked in 10-REVIEW.md |
| `Makefile` | 32, 121 | Duplicate `##@ field-guide-api` section header; cross-app aggregates miscategorized | WARNING (CR WR-05) | `make help` output order doesn't match README's claimed "Cluster / field-guide-api / launchpad / Housekeeping" grouping; does not break D-04's literal wording (all targets still shown with descriptions) |
| `Makefile` | 95-112 | `TTL_DEEP=1` deep mode inserts probe with `ts: new Date()` against a 604800s (7-day) TTL and only polls 90s | CRITICAL (CR CR-01) | Deep mode can never pass on a correctly-functioning deployment; leaves a stray probe doc visible in the activity feed for 7 days if ever run. Outside D-07's literal scope (index-existence only) but undermines the "closes Phase 9 FEED-03" claim in `docs/known-limitations.md:96` |
| `Makefile` | 138, 140, 146 | No `.NOTPARALLEL:` guard; `up`, `up-all`, `smoke-all` rely on serial prerequisite evaluation | WARNING (CR WR-04) | Breaks under `make -j`; does not affect the phase goal's literal single-command (`make up-all`, no `-j`) invocation, which was live-verified to work |
| `Makefile` | 153 | `check-tools` prints raw error text for `helm --version` / `kubectl --version` (unsupported flag) | WARNING (CR WR-02) | Cosmetic/UX defect in an out-of-scope target for this phase's must-haves |
| `Makefile` | 67, 167 | `pkill` unavailable in Git Bash — stale-forward guard silently no-ops on primary supported shell | WARNING (CR WR-03) | Does not block `make up-all`/`smoke-all`/`smoke-launchpad` succeeding on a clean run (as live-verified); relevant only to repeat/stale-state scenarios |
| `docs/known-limitations.md` | 96 | Claims TTL_DEEP=1 "closes the Phase 9 FEED-03 'verify live' flag" | WARNING (documentation accuracy, follows from CR-01) | The deep round-trip this sentence describes cannot succeed against the default deployment; the flag is closed only in the weaker sense that the default index-check passed live, not via a working live-expiry round-trip as the prose implies |

None of the above are `TBD`/`FIXME`/`XXX` unresolved debt markers requiring a blocker gate — all are already surfaced with fix proposals in the committed `10-REVIEW.md` (status: `issues_found`), which is the correct artifact for tracking them forward (e.g., a Phase 10 follow-up plan or backlog item), not a re-open of this phase's must-haves.

### Human Verification Required

### 1. REQUIREMENTS.md tracking update

**Test:** Update `.planning/REQUIREMENTS.md` checkboxes for DEP-04, DEP-05, DOCS-01 to `[x]` and change their traceability-table status from "Pending" to "Complete"
**Expected:** Requirements file accurately reflects the phase's actual completion state, matching both SUMMARY.md `requirements-completed` declarations
**Why human:** This is a project bookkeeping file, not application code; the verifier's job is to confirm the phase goal is met in the codebase (which it is) and flag that the tracking artifact is stale, not to silently rewrite planning documents

## Gaps Summary

All 16 derived must-have truths for Phase 10 (up-all bring-up, smoke-all, help grouping, verify-ttl, port-forward, epilogue, reset-local symmetry, README browser-demo headline, real screenshots, real /health output, troubleshooting/known-limitations entries, PROJECT.md correction, preserved existing docs) are VERIFIED against the actual codebase and cross-checked against the human-approved live-cluster checkpoint evidence provided for this session (real `make up-all`, `make smoke-all`, `make smoke-launchpad`, `curl /health`, `make verify-ttl`, both test suites, five real screenshots).

The phase goal — "`make up-all` brings both apps up end-to-end in a single command and the dashboard is demoable to a human reviewer via the browser" — is achieved. The Makefile wiring, README restructure, and docs updates are all real (not stubs), substantive, and cross-linked correctly.

Two items are surfaced as non-blocking:
1. **Human verification item** — REQUIREMENTS.md tracking checkboxes/traceability table were not updated to reflect completion; recommend a follow-up doc commit.
2. **Committed code-review findings** (`10-REVIEW.md`, status `issues_found`, 1 critical + 5 warnings + 4 info) remain open. The single critical finding (CR-01, `TTL_DEEP=1` mathematically cannot pass) does not invalidate must-have D-07 as literally scoped (default index-existence check, which passed live), but it does mean the "closes Phase 9 FEED-03" prose in `docs/known-limitations.md` overstates what was actually verified — the deep live-expiry round-trip has never succeeded and cannot succeed as currently implemented. This is exactly the kind of gap the review process exists to catch; it is appropriately tracked in the review artifact for a follow-up fix rather than blocking Phase 10 sign-off, since the phase's literal must-haves (D-01 through D-13) do not depend on the deep-mode path.

No overrides were needed — every must-have's literal wording is satisfied by the current codebase.

---

_Verified: 2026-07-14T02:50:00Z_
_Verifier: Claude (gsd-verifier)_
