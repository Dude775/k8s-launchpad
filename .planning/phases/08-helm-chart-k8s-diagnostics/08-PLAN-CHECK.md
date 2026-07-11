# Phase 8 Plan Check - Helm Chart + K8s Diagnostics

**Checked:** 2026-07-11
**Checker:** gsd-plan-checker (pre-execution, goal-backward)
**Plans:** 08-01-PLAN.md (DEP-01, DEP-02) / 08-02-PLAN.md (DIAG-01, DIAG-02)

## Verdicts

| Plan | Verdict | Blockers | Warnings | Info |
|------|---------|----------|----------|------|
| 08-01 | FAIL | 2 | 1 | 1 |
| 08-02 | FAIL | 1 | 1 | 2 |

**Bottom line:** 08-01 is physically truncated (the file ends at line 140, mid-Task-1 verify block; the Task 2 that must create deployment.yaml and rbac.yaml does not exist in the file). 08-02 is well-grounded and thorough but contains a self-defeating import/monkeypatch combination that makes its own test gate unpassable as written. Neither blocker is expensive to fix.

---

## Success Criterion Coverage (goal-backward)

| SC | What must be TRUE | Delivering task(s) | Status |
|----|-------------------|--------------------|--------|
| SC 1 | helm lint clean; launchpad.* helper prefix, no selector collision | 08-01 Task 1 (_helpers.tpl prefix swap); final lint gate stated to run "after Task 2", and Task 2 is ABSENT from the file | PARTIAL - helpers covered; lint gate missing |
| SC 2 | make build-launchpad load-launchpad deploy-launchpad completes; pod reaches Running | NONE. Makefile not in 08-01 files_modified; the three targets are echo-stubs today; no deploy/checkpoint task exists | UNCOVERED (Blocker 2) |
| SC 3 | /diagnostics lists pods/deployments in-cluster; muted "outside cluster" panel locally, never 500 | 08-02 Tasks 1-3 (outside-cluster/403/unreachable/success branches, fragment + full page) | COVERED at unit level, but tests broken as written (Blocker 3); in-cluster live half has no verification step in either plan |
| SC 4 | serviceAccountName: launchpad; namespace Role (get/list/watch pods+deployments), not ClusterRole | Claimed in 08-01 must_haves + frontmatter (rbac.yaml, deployment.yaml) - no task in the file creates them | UNCOVERED as written (Blocker 1) |
| SC 5 | All K8s calls pass _request_timeout=5 | 08-02 Task 1 (constant + call sites) + Task 3 (source-grep gate) + Task 1 automated AST check | COVERED |

## Requirement Coverage

| Requirement | Plan | Status |
|-------------|------|--------|
| DEP-01 (chart, lint-clean, no selector collision) | 08-01 | PARTIAL - 8 of 10 files tasked; deployment.yaml + final lint gate missing (truncation) |
| DEP-02 (SA + Role + RoleBinding, wired serviceAccountName) | 08-01 | MISSING - rbac.yaml appears in frontmatter/must_haves only; zero tasks deliver it |
| DIAG-01 (cluster-independent platform checks) | 08-02 | COVERED - Task 2 reuses /partials/status-cards in the two-section page |
| DIAG-02 (read-only K8s state, graceful degrade, distinct 403) | 08-02 | COVERED in design - Task 1 branches a/b/c match the carried research flag exactly; test delivery blocked by Blocker 3 |

---

## Numbered Issues

### BLOCKER 1 - 08-01-PLAN.md is truncated / structurally invalid
- **Plan/location:** 08-01-PLAN.md, EOF at line 140 (file ends inside Task 1's automated grep chain - no closing verify/task/tasks tags)
- **Dimension:** task_completeness / requirement_coverage
- **Evidence:** Task 1's own action says "deployment.yaml is created in Task 2 - leave it out of this task" and "the final lint gate runs after Task 2". No Task 2 exists in the file. Frontmatter files_modified lists templates/deployment.yaml and templates/rbac.yaml; must_haves assert the SA/Role/RoleBinding truths, serviceAccountName: launchpad, POD_NAMESPACE Downward API injection, and the unweakened /health readinessProbe (D-08) - none has a delivering task. Also missing entirely: Task 1 acceptance_criteria/done, the verification, success_criteria, and output sections.
- **Consequence:** DEP-02, SC 1 (lint gate), SC 4, and the deployment half of DEP-01 will not be delivered; the executor has no SUMMARY output instruction.
- **Fix:** Regenerate/complete 08-01: add Task 2 (deployment.yaml adapted from the analog - SA + POD_NAMESPACE Downward API env + MONGO_URI secretKeyRef + FIELD_GUIDE_BASE_URL/APP_VERSION/FLASK_DEBUG configMapKeyRefs + unweakened /health readinessProbe per D-08; rbac.yaml per RESEARCH "RBAC Manifests" with literal SA name launchpad), a helm lint + helm template collision-grep gate, closing sections, and the SUMMARY output block.

### BLOCKER 2 - SC 2 has no delivering task anywhere in the phase (unresolved research question)
- **Plan/location:** 08-01 (files_modified omits Makefile); 08-RESEARCH.md "Open Questions" Q1 (~line 517, NOT marked RESOLVED); 08-CONTEXT.md Deferred section
- **Dimension:** requirement_coverage / research_resolution (Dim 11) / scope_reduction (Dim 7b)
- **Evidence:** ROADMAP SC 2 requires make build-launchpad load-launchpad deploy-launchpad to complete and the pod to reach Running. Those Makefile targets are echo-stubs today, and the Makefile's own comments (lines 48-55) say "available in Phase 8". CONTEXT.md's Deferred section pushes the targets to Phase 10, contradicting the ROADMAP. RESEARCH.md left exactly this boundary as unresolved Open Question 1 ("Flag for the planner to confirm the DoD boundary") and the plan neither implements the targets nor records a decision. 08-01's objective claims "the launchpad pod reaches Running in a live kind cluster (SC 2)" with nothing that makes it true.
- **Fix (pick one, record in plan):** (a) Un-stub the three Makefile targets in 08-01 (mirror the field-guide-api build/load/deploy targets with LP_* vars) and add a checkpoint/manual verify that the pod reaches Running (NotReady is acceptable per D-08); or (b) escalate to amend ROADMAP SC 2 if the user truly intends Phase 10 delivery. Option (a) matches the locked ROADMAP contract; silently leaving SC 2 to Phase 10 is scope reduction. Mark RESEARCH Open Question 1 RESOLVED either way.

### BLOCKER 3 - 08-02's prescribed import defeats its own prescribed test fixtures
- **Plan/location:** 08-02 Task 1 action ("Imports: ... from app.k8s import get_k8s_clients"), Task 2 automated verify, Task 3 action ("reuse k8s_disabled / k8s_enabled ... do NOT write new client mocks")
- **Dimension:** key_links_planned / task_completeness
- **Evidence:** conftest.py k8s_disabled/k8s_enabled monkeypatch app.k8s.get_k8s_clients (module attribute, conftest.py lines 55-77). If cluster_state.py does `from app.k8s import get_k8s_clients`, the function reference is bound into app.cluster_state's namespace at first import (which happens during create_app() via routes/partials.py, before any fixture patch). Patching app.k8s afterwards never reaches that binding. Result as written: Branch 2/3/4 tests (k8s_enabled + return_value/side_effect) call the REAL get_k8s_clients() and deterministically fail in CI (real function returns (None, None), so tests see {"available": False} instead of pods/errors); on this dev machine (kind kubeconfig present) even the outside-cluster tests would load a real kubeconfig, violating the plan's own "zero real cluster needed" claim. Task 2's inline verify (`import app.k8s as k; k.get_k8s_clients=lambda:(None,None)` after create_app) has the identical defect. The analog the plan cites (status.py) avoids this by calling through the module (`import requests` then `requests.get(...)`), so the plan deviates from its own analog. Note: RESEARCH.md Pattern 1 (line 168) is the source of the bad import - the fix must propagate from there.
- **Fix:** In Task 1, change the import to `from app import k8s` (or `import app.k8s as k8s`) and call `k8s.get_k8s_clients()` - the conftest fixtures then work unmodified, matching k8s.py's docstring ("callers ... invoke it per-request"). Update Task 2's inline verify the same way, and update the key_link pattern accordingly. (Alternative: patch app.cluster_state.get_k8s_clients in tests - but that contradicts "reuse fixtures, do NOT write new mocks".)

### WARNING 4 - No in-cluster verification of SC 3's first half anywhere in the phase
- **Plan/location:** phase-level (08-01 verification section missing; 08-02 verification is unit-only)
- **Dimension:** verification_derivation
- **Evidence:** SC 3 requires /diagnostics to list real pods/deployments "when accessed inside the cluster". 08-02 proves the code paths with mocks; 08-01 (truncated) contains no deploy + port-forward + curl /diagnostics checkpoint. The SA-identity -> RBAC -> live-200 wiring is exactly the carried failure-mode concern and is only observable post-deploy.
- **Fix:** When completing 08-01, add a manual/checkpoint verify: helm install into kind, wait for pod Running, kubectl port-forward, assert the cluster-state fragment shows the launchpad pod row (and note that a wrong-SA 403 must render the "access denied" panel, not the muted panel).

### WARNING 5 - 08-01 Task 1 automated verify is fragile/redundant
- **Plan/location:** 08-01 Task 1 verify (line 141)
- **Dimension:** task_completeness
- **Evidence:** `grep -Lq 'field-guide-api' templates/_helpers.tpl && ! grep -q 'field-guide-api' ...` - the -Lq clause duplicates the `! grep -q` clause; it also only inspects _helpers.tpl for the analog string while Task 1 writes 8 files (a leftover field-guide-api include in service.yaml/configmap.yaml/secret.yaml/NOTES.txt would pass). The truncation also leaves the tag unclosed.
- **Fix:** Use `! grep -rq 'field-guide-api' charts/launchpad/` plus the positive asserts; close the task properly.

### INFO 6 - 08-01 scope: 10 files in one plan
Above the 5-8 file target, but all are small mirrored templates of a proven chart; acceptable. Keep the intended 2-task split (8 static mirrors, then deployment + rbac + lint gate).

### INFO 7 - 08-02 must_haves.artifacts omits two files it modifies
cluster_state_full_page.html and the test_partials.py edits appear in files_modified and acceptance criteria but not in must_haves.artifacts. Harmless; verifier coverage comes from the truths.

### INFO 8 - diagnostics.html content has no automated gate
08-02 Task 2's acceptance criteria assert the two url_for targets and the 10s visibility-guarded trigger, but the automated verify only exercises the partial route. Consider one grep over diagnostics.html for partials.status_cards, partials.cluster_state, and "every 10s".

---

## Grounding Spot-Checks (verified against the repo)

| Claim | Result |
|-------|--------|
| charts/field-guide-api/.helmignore exists (dotfile) | OK |
| Analog _helpers.tpl has the two mongodb helpers to delete; deployment.yaml has /health readinessProbe (timeoutSeconds 3) + tcpSocket liveness; secret.yaml has the mongodb.enabled conditional to replace | OK |
| config.py env names exactly MONGO_URI, FIELD_GUIDE_BASE_URL, APP_VERSION, FLASK_DEBUG; no MONGO_DBNAME (correctly excluded by 08-01 Task 1) | OK |
| serverSelectionTimeoutMS default 2000 in app/__init__.py (lines 48-51) matches 08-01 secret placeholder rationale | OK |
| app/k8s.py get_k8s_clients() returns (None, None) outside a cluster, in-cluster-first order | OK |
| partials.py status_cards HX-Request branch matches the byte-for-byte mirror claim | OK |
| conftest fixtures k8s_disabled / k8s_enabled / client / mongo_down exist as described | OK (but see Blocker 3 - patch target vs import style) |
| test_status.py::test_status_no_requests_get_call_missing_timeout exists (grep-gate analog) | OK |
| index.html visibility-guarded "every 15s" trigger string matches verbatim (10s swap is the only delta) | OK |
| kubernetes==36.0.2 pinned in apps/launchpad/requirements.txt; pytest.ini --cov-fail-under=100 | OK |
| urllib3 MaxRetryError subclasses HTTPError; ApiException is NOT an HTTPError subclass (except-order in 08-02 Task 1 is correct) | OK |
| Makefile build-launchpad/load-launchpad/deploy-launchpad are echo-stubs marked "available in Phase 8" | OK (drives Blocker 2) |

## Dimension Summary

| Dimension | 08-01 | 08-02 |
|-----------|-------|-------|
| 1 Requirement coverage | FAIL (DEP-02 untasked) | PASS |
| 2 Task completeness | FAIL (truncation) | PASS |
| 3 Dependency correctness | PASS | PASS |
| 4 Key links planned | PARTIAL (SA/secret links declared, delivering tasks missing) | FAIL (import key_link defeats fixtures - Blocker 3) |
| 5 Scope sanity | INFO (10 files, 2 intended tasks) | PASS (3 tasks / 7 files) |
| 6 Verification derivation | FAIL (verification section absent) | PASS (truths user-observable, grep gates strong) |
| 7 Context compliance (D-01..D-08, deferred) | PASS on visible text (D-08 honored in must_haves; mongodb/ correctly excluded) | PASS (D-01..D-05 all implemented; no deferred scope) |
| 7b Scope reduction | Blocker 2 is a latent scope reduction of SC 2 (silent deferral to Phase 10) | none |
| 7c Architectural tier compliance | PASS (RBAC/deploy in chart tier per Responsibility Map) | PASS (query in backend, render server-side, poll in browser) |
| 8 Nyquist | SKIPPED (nyquist_validation: false in config.json) | SKIPPED |
| 9 Cross-plan data contracts | PASS - POD_NAMESPACE name identical in both plans (D-05); no conflicting transforms | PASS |
| 10 CLAUDE.md compliance | PASS (no secrets, no --atomic, Helm 3 chart) | PASS (tests exceed 95% target) |
| 11 Research resolution | FAIL - RESEARCH.md Open Questions Q1 (SC 2 boundary) not marked RESOLVED (feeds Blocker 2) | same phase-level finding |
| 12 Pattern compliance | PASS (PATTERNS chart-file sections referenced per-file) | PASS (all analogs cited; pages.py correctly left unchanged per PATTERNS) |

## Cross-Plan Wave / Dependency Assessment

Both plans declare wave: 1, depends_on: []. **Correct.** No file overlap (charts/ vs apps/launchpad/). 08-02's tests are fully mocked and need nothing 08-01 produces at execution time. The two runtime contracts that span the plans are consistent by construction: (1) POD_NAMESPACE - 08-01 injects via Downward API, 08-02 reads it with a "default" fallback (both cite D-05); (2) SA identity - 08-01's literal launchpad SA is what load_incluster_config() assumes, and 08-02's 403 branch is precisely the guard for a mis-wired SA. The only integration neither plan can prove alone is the live in-cluster render (Warning 4).

## Recommendation

Return to planner (revision loop 1 of 3):
1. Regenerate 08-01 in full (Blocker 1) - the visible Task 1 is high quality; only the back half of the file is missing.
2. Resolve the SC 2 / Makefile boundary explicitly (Blocker 2) - implement the three targets in 08-01 per the ROADMAP + Makefile comments, or escalate to amend SC 2. Mark RESEARCH Open Question 1 RESOLVED either way.
3. In 08-02, switch cluster_state.py to module-attribute access of get_k8s_clients and fix Task 2's inline verify (Blocker 3) - a one-line-per-site change that makes the existing fixtures work as intended.

---

## Re-check (iteration 1)

**Checked:** 2026-07-11 (post-revision)
**Checker:** gsd-plan-checker (re-verification from scratch + prior-issue resolution audit)

### Verdicts

| Plan | Verdict | Blockers | Warnings | Info |
|------|---------|----------|----------|------|
| 08-01 | PASS | 0 | 0 | 1 |
| 08-02 | PASS with warning | 0 | 1 | 0 |

**Bottom line:** All 3 blockers and both warnings from iteration 0 are resolved. Both plans are structurally complete (single closing tags verified at byte level - the earlier truncation is gone), every SC and requirement has a delivering task, and the D-09 manual-deploy decision is implemented exactly as recorded in CONTEXT.md. One residual WARNING: 08-PATTERNS.md (section cluster_state.py, lines 61 and 84) still shows the `from app.k8s import get_k8s_clients` / bare `get_k8s_clients()` idiom that BLOCKER 3 banned - RESEARCH.md Pattern 1 was corrected but PATTERNS.md was not. The plan itself is triple-guarded against this (action prohibition + interfaces block + automated negative assertion), so execution cannot ship the bad import, but a required-reading artifact now contradicts the plan on the exact prior-blocker issue.

### Prior-Issue Resolution

| # | Prior issue | Status | Evidence |
|---|-------------|--------|----------|
| BLOCKER 1 | 08-01 truncated at line 140; no Task 2 | **RESOLVED** | File is 276 lines, ends with a single closing output tag (verified raw tail bytes). Task 2 creates deployment.yaml + rbac.yaml with the helm lint + template collision gate; Task 3 checkpoint added; threat_model, verification, success_criteria, output sections all present; Task 1 has acceptance_criteria + done. |
| BLOCKER 2 | SC #2 had no delivering task; RESEARCH Q1 unresolved | **RESOLVED** | CONTEXT.md D-09 records the user decision (manual loop in Phase 8; make targets stay Phase 10 / DEP-04). ROADMAP SC #2 amended to match (verified, ROADMAP.md line 82). 08-01 Task 3 is checkpoint:human-verify with gate="blocking", plan autonomous: false, full docker build + kind load/registry push + helm install steps; resume-signal requires pod STATUS Running. NotReady accepted per D-08, explicitly documented ("Do NOT weaken the readinessProbe"). RESEARCH Open Question 1 marked [RESOLVED 2026-07-11, user decision]. |
| BLOCKER 3 | 08-02 from-import defeats conftest monkeypatch | **RESOLVED in plan** | 08-02 uses `from app import k8s` + `k8s.get_k8s_clients()` throughout (interfaces block, Task 1 action, key_link pattern). All remaining from-import strings are negative-assertion contexts only (Task 1 verify asserts absence; acceptance criteria "does NOT contain"; verification regression guard). Task 2's inline verify patches the module attribute, which now works. Confirmed against conftest.py: fixtures monkeypatch.setattr the app.k8s module attribute (lines 55-77) - module-attribute access is correct. RESEARCH Pattern 1 corrected. BUT see WARNING R1: 08-PATTERNS.md was not corrected. |
| WARNING 4 | No in-cluster verification of SC 3's live half | **RESOLVED** | 08-01 Task 3 step 5: port-forward + curl /diagnostics, asserts the launchpad pod row renders, and explicitly requires a 403 to render the DISTINCT access-denied panel, never the muted outside-cluster panel. See INFO R2 on ordering. |
| WARNING 5 | Fragile -Lq grep in 08-01 Task 1 verify | **RESOLVED** | Now `cd charts/launchpad && ! grep -rq 'field-guide-api' .` (whole chart dir, all 8 files); acceptance criterion states the recursive grep must return nothing. |
| INFO 6 | 08-01 scope: 10 files | UNCHANGED (accepted) | Still 10 files across 2 auto tasks + 1 checkpoint; all small mirrored templates of a proven chart. |
| INFO 7 | cluster_state_full_page.html missing from 08-02 | **RESOLVED** | Present in files_modified (line 11) and in Task 2 action + acceptance criteria. |
| INFO 8 | diagnostics.html had no automated gate | **RESOLVED** | Task 2 verify greps diagnostics.html for partials.status_cards, partials.cluster_state, and "every 10s". |
| Dim 11 | RESEARCH Open Question 1 not resolved | **RESOLVED** | Q1 carries inline [RESOLVED 2026-07-11, user decision]; Q2 carries inline "Resolved above - low risk". |

### Fresh Verification (from scratch)

**Requirement coverage:** DEP-01, DEP-02 -> 08-01 frontmatter + Tasks 1-3; DIAG-01, DIAG-02 -> 08-02 frontmatter + Tasks 1-3. All 4 roadmap IDs covered; DEP-03 (Phase 9) and DEP-04 (Phase 10) correctly excluded. PASS.

**SC coverage against the AMENDED roadmap:**

| SC | Delivering task(s) | Status |
|----|--------------------|--------|
| 1 (lint clean, no selector collision) | 08-01 T1 (_helpers prefix swap + chart-wide grep) + T2 (helm lint + template collision grep) | COVERED |
| 2 (manual loop -> pod Running) | 08-01 T3 blocking human-verify checkpoint (D-09) | COVERED |
| 3 (diagnostics in-cluster / muted panel locally, never 500) | 08-02 T1-T3 (four branches, mocked) + 08-01 T3 step 5 (live in-cluster) | COVERED |
| 4 (serviceAccountName launchpad; namespace Role get/list/watch, no ClusterRole) | 08-01 T2 (+ rendered-output asserts incl. negative ClusterRole grep) | COVERED |
| 5 (_request_timeout=5) | 08-02 T1 (constant + call sites + source assertion) + T3 (source-grep gate test) | COVERED |

**Task completeness:** all auto tasks have files/read_first/action/verify/acceptance_criteria/done; the checkpoint has action/what-built/how-to-verify/resume-signal; autonomous: false on 08-01 matches the checkpoint, autonomous: true on 08-02 matches zero checkpoints. PASS.

**Dependencies/waves:** both wave 1, depends_on []; no file overlap (charts/ vs apps/launchpad/). PASS (see INFO R2).

**Grounding spot-checks (re-verified):** conftest k8s_disabled/k8s_enabled patch the app.k8s module attribute (lines 55-77) - the module-import fix is sound; make test-launchpad is a real working target (deploy targets remain stubs - consistent with D-09); charts/field-guide-api/.helmignore exists; status_full_page.html / index.html / diagnostics.html stub / partials/status_cards.html all exist; charts/launchpad/ does not yet exist (greenfield as planned); ROADMAP SC #2 text amended to the manual loop; nyquist_validation=false in config.json.

**Dimensions:** 1 PASS | 2 PASS | 3 PASS | 4 PASS (key_links all have delivering actions incl. secretKeyRef + SA-name wiring) | 5 PASS-info | 6 PASS (truths user-observable) | 7 PASS (D-01..D-09 all implemented; deferred ideas excluded) | 7b PASS (no scope-reduction language; D-09 is a recorded user decision with ROADMAP amendment, not silent reduction) | 7c PASS | 8 SKIPPED (nyquist_validation false) | 9 PASS (POD_NAMESPACE + SA name + panel copy consistent across plans) | 10 PASS (Helm 3 chart, no --atomic, no real secrets, Git Bash-safe commands, 100% >= 95% coverage target) | 11 PASS | 12 WARNING (see R1 - the plan deviates from PATTERNS.md WITH justification, but PATTERNS.md itself is stale).

### Remaining Issues

**WARNING R1 - 08-PATTERNS.md still prescribes the BLOCKER-3 from-import**
- Location: 08-PATTERNS.md section "apps/launchpad/app/cluster_state.py", line 61 (`from app.k8s import get_k8s_clients`) and line 84 (`core_v1, apps_v1 = get_k8s_clients()`)
- Dimension: pattern_compliance (12) / documentation consistency
- Evidence: RESEARCH.md Pattern 1 was corrected to `from app import k8s`; PATTERNS.md was not. 08-02 Task 1 read_first directs the executor to this exact PATTERNS section, which now contradicts the plan on the precise issue BLOCKER 3 was about.
- Why not a blocker: the plan carries three independent guards - the action prohibition, the interfaces-block rationale, and Task 1's automated negative assertion (from-import string must be absent) - so the wrong import cannot pass verification. Execution can proceed.
- Fix: update PATTERNS.md line 61 to `from app import k8s` (with the monkeypatch rationale comment) and line 84 to `core_v1, apps_v1 = k8s.get_k8s_clients()`. Two-line edit; no plan change needed.

**INFO R2 - 08-01 Task 3 optional step 5 is order-sensitive relative to 08-02**
- The optional in-cluster diagnostics check (pod row in Cluster State) only renders if the image built in step 1 contains 08-02's code. Both plans are wave 1 with no dependency, so if the checkpoint runs before 08-02 merges, /diagnostics is still the Phase-7 stub and step 5 shows neither panel nor tables. The blocking criterion (pod STATUS Running) is unaffected. Suggestion: run step 5 after 08-02 completes (rebuild + reinstall), or note this in the checkpoint text. No plan change required.

**INFO R3 - Makefile stub comments now stale vs D-09**
- Makefile lines 39-55 still say build/load/deploy-launchpad are "available in Phase 8"; D-09 moved them to Phase 10 (DEP-04). Repo-doc drift only - neither plan touches the Makefile (correctly). Fix opportunistically in Phase 10.

### Recommendation

Plans are execution-ready. The single WARNING is a 2-line fix in 08-PATTERNS.md (a phase artifact, not a plan) - recommend applying it before /gsd:execute-phase 8 so the executor's required reading does not contradict the plan; no further re-check needed if that is the only change.
