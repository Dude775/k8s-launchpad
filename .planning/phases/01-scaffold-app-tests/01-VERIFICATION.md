---
phase: 01-scaffold-app-tests
verified: 2026-07-05T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification: true
human_verification:
  - test: "Run `make test` end-to-end in Git Bash or WSL2 on a clean shell where the default `pip`/`python` is NOT a venv"
    expected: "Suite runs green (28 tests, 100% coverage) without requiring manual venv activation"
    why_human: "WR-05 (REVIEW): Makefile:10 runs bare `pip install` + `pytest` with no venv creation. On this host default python resolves to 3.7.4. If the target developer environment has a broken or mismatched python in PATH, `make test` fails silently or installs into the wrong site-packages. The post-merge gate confirmed tests pass under Python 3.12 with a pre-activated venv; `make test` as written has not been verified in a cold Git-Bash/WSL2 session on this machine."
  - test: "Issue or defer decision on CR-01 and CR-02 (confirmed 500-error paths in POST /entries)"
    expected: "Either: (a) issues are logged and accepted as out-of-scope for Phase 1 happy-path delivery, OR (b) they are backlogged as a gap to fix before Phase 3 containerization"
    why_human: "CR-01 (REVIEW): `POST /entries` with a non-dict JSON body (e.g. `[1,2]` or `\"string\"`) returns HTTP 500. CR-02: `tags` set to an integer raises TypeError → 500; `tags` set to a string silently corrupts stored data. Both were reproduced by the code reviewer by executing the code. The code's own security note (entries.py lines 18-22) documents the invariant 'malformed input → never 500, T-02-03', which these cases violate. A human must decide whether this constitutes a 'fully working' API for the Phase 1 gate or requires a fix before proceeding."
---

# Phase 1: Scaffold + App + Tests Verification Report

**Phase Goal:** The monorepo exists with clean git hygiene (.gitignore/.gitattributes as the first commit), a fully working Flask field-guide API that runs locally, and a pytest suite that passes without a cluster
**Verified:** 2026-07-05T00:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| SC-1 | `.gitignore` and `.gitattributes` are the first commit — no secrets can be accidentally committed and no shell script has CRLF endings | VERIFIED | Commit `a32203d` (Jul 4 18:01:43) contains only `.gitignore`/`.gitattributes`. First app code arrived in `43b4650`/`399f0e4` (wave 2). `git check-ignore` confirms `.env`, `.venv/`, `__pycache__/`, `kubeconfig`, `*.kubeconfig` are all ignored. `.gitattributes` has `* text=auto eol=lf` + `*.sh text eol=lf`. `.env.example` negation (`!.env.example`) tracked correctly. |
| SC-2 | `pytest` (without a running cluster) produces a green suite covering all API endpoints, with MongoDB mocked | VERIFIED | 28 tests, 100% coverage, 0.53s per SUMMARY-03. conftest.py monkeypatches `mongo.cx` and `mongo.db` with mongomock client. All 5 endpoint paths covered (list, get-by-id found/missing/malformed, post create/400, health up/down, metrics). Coverage gate `--cov-fail-under=95` enforced in pytest.ini. Post-merge gate independently confirmed. |
| SC-3 | The Flask app starts locally and serves GET /entries, GET /entries/:id, and POST /entries backed by MongoDB connection string from env | VERIFIED (with warnings) | All three endpoints in `entries.py`. `MONGO_URI` read exclusively from `os.environ` in `config.py:20-22`. No literal credentials. `.env.example` provides safe template. Happy-path contracts verified by test suite. WARNING: CR-01 (non-dict body → 500) and CR-02 (non-iterable tags → 500, string tags → data corruption) confirmed by code review — see Anti-Patterns section. |
| SC-4 | GET /health returns 200 when MongoDB is reachable and 503 when it is not; GET /metrics returns Prometheus-format text | VERIFIED | `health.py:30`: `mongo.cx.admin.command("ping")` in try/except returns 200 or 503. `PrometheusMetrics.for_app_factory().init_app(app)` auto-registers `/metrics`. `test_health_up` and `test_health_down` both pass. `test_metrics_endpoint` asserts `# HELP` or `# TYPE` present. |
| SC-5 | Directory layout matches target monorepo structure including placeholder dirs for PRD-2 (`infra/argocd/`) and PRD-4 (`infra/observability/`) seams | VERIFIED | All 7 `.gitkeep` files present: `apps/`, `charts/field-guide-api/`, `infra/kind/`, `infra/argocd/`, `infra/observability/`, `scripts/`, `docs/`. `README.md` documents both seam directories with their PRD labels. Committed in `7756c67`. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `.gitignore` | Ignore rules for secrets, venvs, caches, kubeconfig | VERIFIED | Contains `.env`, `.env.*`, `!.env.example`, `__pycache__/`, `*.pyc`, `.venv/`, `kubeconfig`, `*.kubeconfig` |
| `.gitattributes` | LF line-ending enforcement | VERIFIED | `* text=auto eol=lf`, `*.sh text eol=lf`, plus belt-and-suspenders for `.yaml`, `.yml`, `.py` |
| `infra/argocd/.gitkeep` | PRD-2 GitOps directory seam | VERIFIED | Exists; empty; tracked by git |
| `infra/observability/.gitkeep` | PRD-4 observability directory seam | VERIFIED | Exists; empty; tracked by git |
| `apps/field-guide-api/app/__init__.py` | `create_app` application factory | VERIFIED | Contains `def create_app`, deferred blueprint imports, `mongo.init_app(app)`, `metrics.init_app(app)` |
| `apps/field-guide-api/app/config.py` | Config reading MONGO_URI/FLASK_DEBUG from env | VERIFIED | `MONGO_URI = os.environ.get(...)`, `DEBUG = bool(os.environ.get("FLASK_DEBUG", ""))` — WARNING: WR-01 (see Anti-Patterns) |
| `apps/field-guide-api/app/extensions.py` | PyMongo() and PrometheusMetrics singletons | VERIFIED | `mongo = PyMongo()`, `metrics = PrometheusMetrics.for_app_factory()` |
| `apps/field-guide-api/app/routes/entries.py` | GET/POST entries CRUD blueprint | VERIFIED | Exports `entries_bp`, uses `mongo.db.entries`, ObjectId wrapped in try/except |
| `apps/field-guide-api/app/routes/health.py` | Health readiness endpoint | VERIFIED | Exports `health_bp`, calls `mongo.cx.admin.command("ping")` in try/except |
| `apps/field-guide-api/wsgi.py` | gunicorn entrypoint | VERIFIED | `from app import create_app; app = create_app()` |
| `apps/field-guide-api/requirements.txt` | Pinned runtime dependencies | VERIFIED | `Flask==3.1.3`, `Flask-PyMongo==3.0.1`, `pymongo==4.13.2`, `gunicorn==26.0.0`, `prometheus-flask-exporter==0.23.2`, `python-dotenv==1.2.2` |
| `apps/field-guide-api/.env.example` | Safe template (gitignored negation) | VERIFIED | Contains `MONGO_URI=mongodb://localhost:27017/fieldguide`, `FLASK_DEBUG=` (empty). Tracked in git (negation rule confirmed). |
| `apps/field-guide-api/requirements-dev.txt` | Pinned test dependencies | VERIFIED | `-r requirements.txt`, `pytest==9.1.1`, `pytest-flask==1.3.0`, `pytest-cov==5.0.0`, `mongomock==4.3.0` (deviation from 4.1.2 documented in SUMMARY-03) |
| `apps/field-guide-api/pytest.ini` | Coverage gate config | VERIFIED | `testpaths = tests`, `--cov=app --cov-report=term-missing --cov-fail-under=95`, `pythonpath = .` |
| `apps/field-guide-api/tests/conftest.py` | App + client + mongo_down fixtures | VERIFIED | `create_app({'TESTING': True})` called; `monkeypatch.setattr(mongo, "cx", mock_client)` and `mock.db` patched; `mongo_down` patches `health_module.mongo` to raise ConnectionFailure |
| `apps/field-guide-api/tests/test_entries.py` | Entries CRUD tests | VERIFIED | 11 tests: list empty, post 201, list after post, get-by-id 200/404/404-malformed, post 400 (3 cases), post no-persist |
| `apps/field-guide-api/tests/test_health.py` | Health up/down tests | VERIFIED | `test_health_up` (200 + mongo=up), `test_health_down` (503 + mongo=down) |
| `apps/field-guide-api/tests/test_metrics.py` | Metrics endpoint test | VERIFIED | Asserts 200 and `# HELP`/`# TYPE`/`python_info` in body |
| `Makefile` | make test target | VERIFIED (with warning) | `SHELL := /bin/bash`, `export MSYS_NO_PATHCONV=1`, `.PHONY: test`, `test:` target invokes `pip install + pytest`. WARNING: WR-05 bare pip, no venv (see Anti-Patterns) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/routes/entries.py` | `mongo.db.entries` | PyMongo collection access | WIRED | Lines 44, 57, 88: `mongo.db.entries.find()`, `.find_one()`, `.insert_one()` |
| `app/routes/health.py` | MongoDB ping | `mongo.cx.admin.command('ping')` | WIRED | Line 30: pattern `command("ping")` confirmed |
| `app/__init__.py` | `/metrics` | `PrometheusMetrics.for_app_factory()` + `init_app` | WIRED | `extensions.py:18`, `__init__.py:44`: `metrics.init_app(app)` auto-registers the route |
| `tests/conftest.py` | `app.extensions.mongo` | mongomock monkeypatch on `cx` and `db` | WIRED | `monkeypatch.setattr(mongo, "cx", mock_client)`, `monkeypatch.setattr(mongo, "db", mock_db)` |
| `Makefile test target` | `pytest` | `cd apps/field-guide-api && pip install -q -r requirements-dev.txt && pytest` | WIRED (warning) | Target exists and wires to pytest. Bare pip invocation may fail in environments where `pip` resolves to Python < 3.10 (WR-05) |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `app/routes/entries.py` — `list_entries` | `docs` list | `mongo.db.entries.find()` (PyMongo cursor) | Yes — in-memory via mongomock in tests; real MongoDB in production | FLOWING |
| `app/routes/entries.py` — `get_entry` | `doc` | `mongo.db.entries.find_one({"_id": oid})` | Yes | FLOWING |
| `app/routes/entries.py` — `create_entry` | `result.inserted_id` | `mongo.db.entries.insert_one(doc)` | Yes | FLOWING |
| `app/routes/health.py` — `health` | ping result | `mongo.cx.admin.command("ping")` | Yes — real command (success) or exception (down) | FLOWING |

### Behavioral Spot-Checks

Step 7b: SKIPPED — app is not runnable without a MongoDB instance, and the environment notes confirm the post-merge gate already ran `pytest` (28 tests pass, 100% coverage) using Python 3.12 with an activated venv. No additional spot-checks provide marginal value beyond the documented test run.

### Probe Execution

No `scripts/*/tests/probe-*.sh` probes defined for this phase. No PLAN/SUMMARY probe declarations found. SKIPPED.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| SCAF-01 | 01-01-PLAN.md | Monorepo layout with all target directories | SATISFIED | 7 `.gitkeep` files in `apps/`, `charts/field-guide-api/`, `infra/kind/`, `infra/argocd/`, `infra/observability/`, `scripts/`, `docs/` |
| SCAF-02 | 01-01-PLAN.md | `.gitignore` covers `.env`, `__pycache__`, `.venv`, `*.pyc`, kubeconfig — in place before first meaningful commit | SATISFIED | `.gitignore` in commit `a32203d`; `git check-ignore` verified for all listed patterns |
| SCAF-03 | 01-01-PLAN.md | `.gitattributes` enforces LF line endings | SATISFIED | `* text=auto eol=lf` and `*.sh text eol=lf` in `.gitattributes` in same commit `a32203d` |
| API-01 | 01-02-PLAN.md | GET list of field-guide entries via REST | SATISFIED | `GET /entries` → 200 + JSON array in `entries.py:41-45` |
| API-02 | 01-02-PLAN.md | GET single entry by id | SATISFIED | `GET /entries/<entry_id>` → 200 or 404 in `entries.py:48-61` |
| API-03 | 01-02-PLAN.md | POST new entry | SATISFIED | `POST /entries` → 201 or 400 in `entries.py:64-91` |
| API-04 | 01-02-PLAN.md | Entries persist in MongoDB; app reads connection string from env | SATISFIED | `MONGO_URI` env-only in `config.py:20-22`; PyMongo wired via `Flask-PyMongo` |
| API-05 | 01-02-PLAN.md | `/health` readiness reflects MongoDB connectivity | SATISFIED | `health.py:26-33`; 200/503 duality tested via mongomock + ConnectionFailure fixture |
| API-06 | 01-02-PLAN.md | `/metrics` Prometheus scrape seam | SATISFIED | `PrometheusMetrics.for_app_factory()` auto-registers endpoint; 200 + Prometheus text confirmed |
| TEST-01 | 01-03-PLAN.md | pytest suite passes via `make test` without a cluster | SATISFIED (with warning) | 28 tests, 100% coverage, mongomock, no cluster. `make test` target wired. WR-05 makes `make test` fragile in environments without a Python 3.10+ `pip` in PATH. |

No orphaned requirements: all 10 Phase 1 requirements are claimed by plans and evidenced in code. Remaining PRD-1 requirements (IMG-*, CLUS-*, HELM-*, MAKE-*, DOCS-*) are Phase 2–4 scope per REQUIREMENTS.md traceability table.

### Anti-Patterns Found

Anti-patterns from code review REVIEW.md (pre-existing at time of verification, reproduced by reviewer via code execution):

| File | Finding | Severity | Impact |
|------|---------|----------|--------|
| `app/routes/entries.py:71` | CR-01: `request.get_json(silent=True) or {}` followed by `data.get(...)` — non-dict JSON body (array, string) raises `AttributeError` → HTTP 500. Violated invariant: code comment lines 18-22 state "malformed input → never 500". **Confirmed by execution.** | WARNING | Violates code's own security invariant (T-02-03). Does not affect documented happy-path contracts tested by test suite. |
| `app/routes/entries.py:83` | CR-02: `list(data.get("tags", []))` — `tags=5` → `TypeError` → 500; `tags="abc"` → stored as `["a","b","c"]` (data corruption). **Confirmed by execution.** | WARNING | Edge-case 500 + silent data corruption. Schema doc (line 11) requires `[str]`. Not covered by test suite. |
| `app/config.py:26` | WR-01: `bool(os.environ.get("FLASK_DEBUG", ""))` treats any non-empty string as truthy. `FLASK_DEBUG=0` → `DEBUG=True` (inverted). Conventional operator idiom enables debug mode. | WARNING | Operator using `FLASK_DEBUG=0` gets opposite of intent. Security risk in containers. CLAUDE.md lists "debug mode in prod is a security risk". |
| `app/routes/health.py:30` | WR-02: No `serverSelectionTimeoutMS` configured. PyMongo default is 30000ms. During a MongoDB outage `/health` hangs ~30s before returning 503. With 1 gunicorn sync worker (CLAUDE.md) this blocks all requests. | WARNING | Readiness signal is operationally broken during the outage condition it is designed to detect. Relevant for Phase 3 Kubernetes readinessProbe. |
| `tests/test_factory.py:34` | WR-03: `os.environ.pop("FLASK_DEBUG", None)` mutates global env without restore; `importlib.reload` re-executes `load_dotenv()` from disk. Flaky when developer's `.env` sets `FLASK_DEBUG`. | WARNING | Test reliability. `.env.example` instructs `FLASK_DEBUG=1` for local debugging. |
| `tests/test_routes.py:18-34` | WR-04: File defines its own `app`/`client` fixtures without mongomock patching, shadowing conftest's mocked-DB fixtures. Current tests pass because none touch the DB, but any future DB-accessing test here will attempt a real `localhost:27017` connection (30s hang per WR-02). Also duplicates tests already in `test_entries.py` and `test_metrics.py`. | WARNING | Latent reliability trap for future test authors. Duplicated test coverage. |
| `Makefile:10` | WR-05: `pip install -q -r requirements-dev.txt && pytest` uses bare `pip`/`pytest` with no venv creation. On this host default `python` is 3.7.4 — Flask 3.1.3/gunicorn 26 require ≥3.10. `make test` will fail or pollute global site-packages on a cold Git-Bash/WSL2 session. | WARNING | Core developer experience target (`make test`) is not self-contained. Requires human verification (see below). |

No TBD, FIXME, or XXX debt markers found in any phase-modified file. No empty stub implementations found.

### Human Verification Required

#### 1. `make test` Portability in Target Environment

**Test:** Open a fresh Git Bash or WSL2 session with no pre-activated virtual environment. From the repo root, run `make test`.
**Expected:** The command completes in under 60 seconds, exits 0, and prints `28 passed` with `100%` or at minimum `Required test coverage of 95% reached.`
**Why human:** WR-05 (REVIEW): `Makefile:10` runs `cd apps/field-guide-api && pip install -q -r requirements-dev.txt && pytest` with no venv creation. If the shell's `pip` resolves to Python 3.7.4 (which is the default on this host), the install step will fail because Flask 3.1.3 and gunicorn 26 require Python ≥3.10. The post-merge gate verified the suite passes under Python 3.12 with a pre-activated venv — it did not verify `make test` in a cold session. A passing human run would confirm TEST-01 via the intended developer-facing command, or surface the need for the venv fix suggested in REVIEW WR-05.

#### 2. Decision on CR-01 and CR-02 (Confirmed 500-Error Edge Cases)

**Test:** Review REVIEW.md findings CR-01 and CR-02, then decide: are these acceptable as-is for Phase 1, or must they be fixed before Phase 3 containerization?
**Expected:** Either (a) a documented decision that non-standard inputs (non-dict body, non-list tags) are out of scope for Phase 1 and will be addressed before Phase 3, OR (b) a backlog item / fix is created.
**Why human:** The code reviewer confirmed via execution: `POST /entries` with `[1,2]` → HTTP 500; `tags=5` → HTTP 500; `tags="abc"` → 201 with corrupted `["a","b","c"]` data. The code's own security comment (entries.py:18-22) states "malformed input → never 500", and the plan's threat model (T-02-03) explicitly lists this as a mitigation. The test suite achieves 100% coverage of the lines exercised by specified test cases, so `--cov-fail-under=95` does not catch these paths. Automated verification cannot determine whether these are acceptable known gaps or must-fix defects — that is a product/engineering judgment call that gates whether "fully working" is satisfied for Phase 1.

---

## Gaps Summary

No BLOCKER gaps identified. All 5 ROADMAP success criteria are verified by direct codebase inspection. The 10 Phase 1 requirements (SCAF-01–03, API-01–06, TEST-01) are all satisfied by concrete code evidence.

Two items require human judgment before a clean pass can be recorded:
1. `make test` portability — the Makefile target exists and is correctly wired, but its reliability in a cold shell (no pre-activated venv) depends on the host PATH. This is a WARNING, not a blocker, because the test suite itself is demonstrably green.
2. CR-01/CR-02 — confirmed 500s on edge-case inputs violate the code's own invariant. Whether this constitutes a "fully working" API for Phase 1 purposes is a human call. The documented endpoint contracts (valid inputs) all work correctly.

The code review findings (REVIEW.md: 2 Critical, 5 Warning, 4 Info) are noted and factored into this verification. None introduce a hard BLOCKER against the ROADMAP success criteria as written.

---

_Verified: 2026-07-05T00:00:00Z_
_Verifier: Claude (gsd-verifier)_

## Post-Fix Resolution (2026-07-05)

Both human_verification items were resolved by `/gsd:code-review 01 --fix` (commits 737fba2..ae070b7):

1. **`make test` portability** — WR-05 fixed: Makefile now creates/reuses a `.venv` with an overridable `PYTHON ?=` variable. Verified on this host: `make test PYTHON="py -3.12"` → 32 passed, 100% coverage, exit 0.
2. **CR-01 / CR-02** — Fixed, not deferred: non-object JSON bodies and invalid `tags` now return 400 with regression tests covering both paths. The "never 500" invariant (T-02-03) holds.

Status upgraded human_needed → passed. Suite after fixes: 32 tests, 100% coverage (gate 95%).
