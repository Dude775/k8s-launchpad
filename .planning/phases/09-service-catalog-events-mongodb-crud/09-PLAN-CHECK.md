# Phase 9 Plan Check — Service Catalog + Events / MongoDB CRUD

**Verified:** 2026-07-12
**Plans checked:** 09-01, 09-02, 09-03
**Overall verdict:** PASS WITH CONCERNS (1 BLOCKER, 5 WARNINGS)

---

## Per-Plan Verdict

| Plan | Verdict | Notes |
|------|---------|-------|
| 09-01 | PASS WITH CONCERNS | Structurally complete, requirement coverage correct. Minor scope warning (10 files). |
| 09-02 | PASS WITH CONCERNS | Structurally complete. Two small wiring ambiguities (WARNING). Scope warning (12 files, 3 tasks). |
| 09-03 | FAIL (1 BLOCKER) | Task 2's automated verify command cannot pass under its own success condition -- self-contradicting shell logic. |

---

## Success Criteria Coverage (ROADMAP.md Phase 9, 6 criteria)

| # | Success Criterion | Delivering Plan(s) | Status |
|---|---|---|---|
| 1 | GET /catalog lists services; POST /catalog/new valid input persists + fires service_registered + redirects | 09-01 (helpers), 09-02 Task 1 | COVERED |
| 2 | Invalid onboard submit re-renders with field errors, CSRF intact, no write | 09-01 (forms.py, CSRF), 09-02 Task 1 (D-06 re-render) | COVERED |
| 3 | GET /catalog/<id> shows full registration + related events | 09-02 Task 1 (catalog_detail) | COVERED |
| 4 | Deregister (after confirm) removes doc + fires service_deregistered | 09-02 Task 1 (catalog_delete_confirm/catalog_delete) | COVERED |
| 5 | events TTL index on ts; make test-launchpad passes (mongomock-backed); TTL-expiry-live-only documented | 09-01 Task 2 (ensure_indexes, conftest.py TTL comment) | COVERED |
| 6 | Chart embeds mongo:7 manifests in charts/launchpad/templates/mongodb/, db name launchpad; field-guide-api chart untouched | 09-03 Task 1/2 | COVERED (but verify command for the untouched check is broken -- see BLOCKER-1) |

## Requirement ID Coverage (frontmatter requirements: fields)

| ID | Plan(s) declaring it | Status |
|---|---|---|
| CAT-01 | 09-02 | Covered |
| CAT-02 | 09-01, 09-02 | Covered |
| CAT-03 | 09-01, 09-02 | Covered |
| CAT-04 | 09-02 | Covered |
| CAT-05 | 09-02 | Covered |
| FEED-01 | 09-02 | Covered |
| FEED-02 | 09-01, 09-02 | Covered |
| FEED-03 | 09-01 | Covered |
| DEP-03 | 09-03 | Covered |

All 9 requirement IDs are present in at least one plan's requirements frontmatter. No gaps.

## D-NN Decision Coverage (lexical, must_haves.truths)

All D-01 through D-12 appear across the three plans' must_haves.truths:
- 09-01: D-01, D-02, D-03, D-04, D-10, D-12
- 09-02: D-01, D-02, D-06, D-07, D-08, D-09, D-11
- 09-03: D-05, D-08

No locked decision is undelivered or silently reduced. No scope-reduction language (v1, static for now, future enhancement, stub, placeholder) found anywhere in task actions -- every artifact described is fully wired, not a shadow version.

---

## Issues

### BLOCKER-1: 09-03 Task 2 automated verify command cannot pass under its own success condition

- **Dimension:** task_completeness / verification_derivation
- **Plan:** 09-03
- **Task:** 2
- **Location:** line 137

```
<automated>helm lint charts/launchpad/ && helm template charts/launchpad/ | grep -v '^#' | grep -E 'SECRET_KEY|EVENTS_TTL_SECONDS' && git status --short charts/field-guide-api/ | grep -c . </automated>
```

The acceptance criterion (line 145) states: "git status --short charts/field-guide-api/ prints nothing (untouched)" is the PASS condition. But the verify command pipes that same (empty, on success) output through grep -c . . grep -c with zero matching lines exits with status 1 (no match found), which -- because of the && chain -- makes the ENTIRE verify command report failure exactly when the underlying invariant (field-guide-api untouched) correctly holds. Conversely, if field-guide-api WERE touched (the failure case), git status --short would print lines, grep -c . would find matches and exit 0, making the chained command report success. The check is inverted: it fails on success and succeeds on failure.

**Fix:** Replace the final clause. Either:
- git status --short charts/field-guide-api/ | grep -c . ; test $? -eq 1  (explicitly expect grep to find zero lines), or
- Simpler: drop the piped grep entirely and use [ -z "$(git status --short charts/field-guide-api/)" ] as the final chained clause, or
- Split into two separate automated assertions, or document that this final clause must exit 0 only when output is empty (! git status --short charts/field-guide-api/ | grep -q .).

This must be fixed before 09-03 executes, or the executor will either (a) hand-wave past a red CI signal because they know the invariant actually holds, defeating the purpose of an automated check, or (b) chase a phantom failure that isn't a real regression.

---

### WARNING-1: 09-02 Task 1 does not explicitly specify the service template variable for confirm_delete.html

- **Dimension:** key_links_planned / task_completeness
- **Plan:** 09-02
- **Task:** 1

Task 1's action says: "Add catalog_delete_confirm() GET /catalog/<name>/delete: get_service, abort(404) if None, render confirm_delete.html." -- it does not state render_template("confirm_delete.html", service=service). Task 3's template action, however, requires a service context variable directly (service.name, url_for('pages.catalog_delete', name=service.name)). This is inferable by analogy to catalog_detail()'s explicit "render detail.html with the service and events..." phrasing in the same action block, so it is not a blocking ambiguity, but it is a gap in an otherwise very precise plan and should be tightened.

**Fix:** Add service=service explicitly to the catalog_delete_confirm() action description in 09-02 Task 1, matching the precision already used for catalog_detail().

---

### WARNING-2: 09-02 delete-confirm CSRF mechanism left ambiguous between two options

- **Dimension:** key_links_planned
- **Plan:** 09-02
- **Task:** 1 (references Task 3)

Task 1's action states: "Use a bare FlaskForm (or ServiceForm-less minimal form / csrf_token()) so the delete POST carries a CSRF token -- see Task 3 template." Task 3 similarly hedges: "form.hidden_tag() or csrf_token()". Both options are individually valid Flask-WTF patterns (CSRFProtect validates the csrf_token field regardless of whether it's rendered via a bound FlaskForm.hidden_tag() or the bare Jinja global csrf_token()), so this will not break execution -- but leaving the choice unresolved across two tasks executed potentially at different times risks an inconsistency (e.g., Task 1 passes a form= context var that Task 3's template never uses, or vice versa).

**Fix:** Pick one mechanism explicitly (recommend the bare csrf_token() global, since no form object is otherwise needed on this route) and state it once, consistently, in both tasks.

---

### WARNING-3: Scope -- 09-02 is at the upper edge of the file-count budget

- **Dimension:** scope_sanity
- **Plan:** 09-02

3 tasks / 12 files modified. Task 3 alone creates/replaces 4 templates (catalog.html, onboard_form.html, detail.html, confirm_delete.html) governed by a dense, multi-contract UI-SPEC (Form Contract, Table Contract, Confirm-Page Contract, Copywriting Contract). This sits in the "10 files -> warning" band approaching the "15+ -> blocker" threshold, and Task 3's single action paragraph is unusually long (governs 4 distinct templates with 4 distinct contracts in one task). Execution is plausible but quality risk is elevated for Task 3 specifically.

**Fix (optional):** Consider splitting Task 3 into two tasks (catalog.html + onboard_form.html vs. detail.html + confirm_delete.html) if the executor shows signs of rushing the UI-SPEC compliance details. Not a blocker -- flagging for awareness only.

---

### WARNING-4: 09-01 and 09-03 file counts sit in the scope-warning band

- **Dimension:** scope_sanity
- **Plans:** 09-01 (10 files), 09-03 (9 files)

Both exceed the 5-8 "target" file count but stay well under the 15+ blocker threshold, and both have only 2 substantive code tasks (the third task in each is a lightweight human-verify checkpoint, not additional code-generation load). Acceptable as planned; noted for awareness only, no fix required.

---

### WARNING-5: RESEARCH.md Open Questions section lacks the (RESOLVED) marker convention

- **Dimension:** research_resolution
- **File:** 09-RESEARCH.md, line 625

"## Open Questions" (2 questions: URLField vs StringField+URL(), and whether to log index-creation failures) has no "(RESOLVED)" suffix on the heading, and neither question has an inline "RESOLVED:" marker -- despite each having a clear "Recommendation" that the plans do in fact follow (confirmed: 09-01 Task 3 implements URLField + URL(require_tld=True) + scheme-restriction exactly per the recommendation; 09-01 Task 2 keeps the silent-swallow except Exception: pass pattern per the recommendation). Substantively resolved; only the formal marker convention was skipped.

**Fix:** Cosmetic -- retitle the RESEARCH.md section to "## Open Questions (RESOLVED)" and add inline "RESOLVED:" prefixes to each question's recommendation line. Does not block execution since the plans already correctly follow the stated recommendations.

---

## Dimension-by-Dimension Summary

| Dimension | Result |
|---|---|
| 1. Requirement Coverage | PASS -- all 9 IDs covered |
| 2. Task Completeness | PASS WITH CONCERNS -- WARNING-1, WARNING-2 (minor wiring ambiguities, both resolvable by inference) |
| 3. Dependency Correctness | PASS -- 09-01 wave 1 (apps/**), 09-03 wave 1 (charts/**), zero file overlap confirmed pairwise; 09-02 wave 2 correctly depends_on 09-01 |
| 4. Key Links Planned | PASS WITH CONCERNS -- WARNING-1 (service var), WARNING-2 (CSRF mechanism choice) |
| 5. Scope Sanity | PASS WITH CONCERNS -- WARNING-3, WARNING-4 (all within blocker thresholds) |
| 6. Verification Derivation | PASS WITH CONCERNS -- BLOCKER-1 (09-03 Task 2 verify command inverted logic) |
| 7. Context Compliance | PASS -- all D-01..D-12 covered lexically; no deferred-idea scope creep (edit-registration feature correctly absent); Claude's Discretion areas (event schema, page size, sorting, badges) left appropriately open |
| 7b. Scope Reduction Detection | PASS -- no v1/stub/placeholder/future-enhancement language found; every artifact fully wired, not a shadow version |
| 7c. Architectural Tier Compliance | PASS -- RESEARCH.md's Architectural Responsibility Map correctly followed: form validation in API/Backend tier (not browser), persistence in Database tier via never-raise API helpers, TTL bounding at Database tier, zero-JS confirm entirely server-side per D-08 |
| 8. Nyquist Compliance | SKIPPED (nyquist_validation: false in config.json) |
| 9. Cross-Plan Data Contracts | PASS -- 09-01 defines contracts consumed verbatim by 09-02 (catalog.py/events.py/forms.py signatures match the interfaces block exactly); no conflicting transforms on shared data |
| 10. CLAUDE.md Compliance | PASS -- no Bitnami reference, mongo:7 official image only; no --atomic flag used in the manual helm upgrade command; Flask-WTF matches locked stack additions; commit convention not directly tested here (execution-time concern) |
| 11. Research Resolution | WARNING-5 -- Open Questions section present without formal (RESOLVED) marker, though substantively resolved via Recommendations that plans correctly follow |
| 12. Pattern Compliance | PASS -- every file in PATTERNS.md's File Classification table is addressed by the correct plan; No Analog Found files (forms.py, onboard_form.html, confirm_delete.html) correctly cite RESEARCH.md/UI-SPEC.md as authoritative instead of a nonexistent analog |

---

## Grounding Verification (files/functions checked against actual codebase)

Confirmed accurate against the real repository state:
- apps/launchpad/app/extensions.py -- current 2-singleton shape (mongo, metrics) matches plan's extend in place claim
- apps/launchpad/app/__init__.py -- numbered-step factory shape matches plan's insertion-point description
- apps/launchpad/app/config.py -- env-sourced Config class shape matches plan's add SECRET_KEY/EVENTS_TTL_SECONDS claim
- apps/launchpad/app/routes/pages.py -- stub routes for /catalog, /feed exist exactly as described, with the Phase 9 fills in real content docstring cited correctly
- apps/launchpad/app/routes/partials.py -- HX-Request fragment/full-page branch pattern confirmed exact match to what 09-02 Task 2 mirrors
- apps/launchpad/tests/conftest.py -- mongomock injection pattern + k8s_disabled-style module-attribute monkeypatch fixture confirmed present, matches the pattern 09-01 extends
- apps/launchpad/app/status.py, app/cluster_state.py -- never-raise shape and module-attribute import discipline confirmed present exactly as cited
- charts/launchpad/templates/_helpers.tpl -- confirmed the no mongodb helpers here comment exists at line 5, exactly as 09-03 says it must update
- charts/launchpad/templates/secret.yaml, configmap.yaml, deployment.yaml, values.yaml -- confirmed current single-MONGO_URI-only shape; plan's additive changes (SECRET_KEY, EVENTS_TTL_SECONDS, mongodb: block) are correctly scoped extensions, not conflicting rewrites
- charts/field-guide-api/templates/mongodb/ -- confirmed 4-file directory exists (deployment/pvc/secret/service.yaml) as the mirror source
- charts/field-guide-api/templates/_helpers.tpl -- confirmed field-guide-api.mongodb.fullname (line 42) and field-guide-api.mongodb.selectorLabels (line 84) exist as the exact analog 09-03 mirrors
- apps/launchpad/app/templates/diagnostics.html, catalog.html, feed.html -- confirmed current stub/polling shell content matches what plans describe as the current state to extend/replace
- apps/launchpad/requirements.txt -- confirmed current 8-package flat list; plan's single-line Flask-WTF==1.3.0 addition is correctly scoped

No fabricated file references or hallucinated function signatures found. All cited line-number ranges in read_first blocks correspond to real content in the files.

---

## Structural Integrity Check (Phase 8 lesson)

All three plan files verified complete -- no truncation:

| Plan | Lines | tasks tag | threat_model | verification | success_criteria | output |
|---|---|---|---|---|---|---|
| 09-01 | 260 | 3/3 balanced | 1/1 | 1/1 | 1/1 | 1/1 |
| 09-02 | 250 | 3/3 balanced | 1/1 | 1/1 | 1/1 | 1/1 |
| 09-03 | 222 | 3/3 balanced | 1/1 | 1/1 | 1/1 | 1/1 |

All files end with the proper closing output tag sequence. No mid-file cutoffs.

---

## Import Discipline Check (Phase 8 BLOCKER 3 class)

Confirmed correctly planned in both 09-01 and 09-02:
- 09-01's verification section explicitly requires: grep confirms no from app.events import / from app.catalog import direct-name imports were introduced anywhere routes will later patch
- 09-02 Task 1's action and acceptance criteria explicitly require from app import catalog, events (module-attribute) and explicitly forbid from app.catalog import/from app.events import
- 09-02 Task 2's action explicitly requires from app import events (module-attribute) for the /partials/feed route
- PATTERNS.md explicitly calls out that partials.py's EXISTING imports (from app.cluster_state import get_cluster_state) are safe because those tests monkeypatch deeper, while events/catalog must be imported as modules because tests monkeypatch them directly -- this distinction is correctly reasoned, not just cargo-culted

No import-discipline regression risk identified.

---

## Recommendation

1 BLOCKER must be fixed before 09-03 executes (the inverted verify command in Task 2 -- a broken automated check is worse than no check, since it will either be ignored by the executor or chased as a phantom failure). The 5 warnings do not block execution but should be addressed for plan quality, particularly WARNING-1 and WARNING-2 (09-02) since they involve a security-relevant code path (CSRF-protected delete confirmation).

Returning to planner with feedback for 09-03 Task 2's verify command fix as the required change.
