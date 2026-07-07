---
phase: 01-scaffold-app-tests
audited: 2026-07-05
status: secured
asvs_level: 1
threats_total: 11
threats_closed: 11
threats_open: 0
---

# SECURITY.md — Phase 01: Scaffold, App, Tests

**Audit date:** 2026-07-05
**Phase:** 01-scaffold-app-tests (plans 01-01, 01-02, 01-03 + review-fix wave)
**ASVS Level:** 1
**Auditor:** gsd-security-auditor
**Result:** SECURED — 11/11 threats closed

---

## Threat Verification

| Threat ID | Category | Disposition | Status | Evidence |
|-----------|----------|-------------|--------|----------|
| T-01-01 | Information Disclosure | mitigate | CLOSED | `.gitignore` lines 2-4 (`.env`, `.env.*`, `!.env.example`), lines 7-8 (`__pycache__/`, `*.pyc`), line 18 (`.venv/`), lines 38-39 (`kubeconfig`, `*.kubeconfig`). Commit `a32203d` staged only `.gitignore` and `.gitattributes` — no app code present |
| T-01-02 | Tampering (CRLF) | mitigate | CLOSED | `.gitattributes` line 3: `* text=auto eol=lf`; line 6: `*.sh text eol=lf`. Additional belt-and-suspenders rules for `.yaml`, `.yml`, `.py` |
| T-01-03 | Information Disclosure (bulk staging) | mitigate | CLOSED | `git show --stat a32203d` confirms only 2 files staged (`.gitignore`, `.gitattributes`). No `git add -A` used before hygiene commit |
| T-02-01 | Information Disclosure (MongoDB URI) | mitigate | CLOSED | `app/config.py` line 30: `os.environ.get("MONGO_URI", ...)` — env-only read. Local default has no credentials. `.env.example` contains placeholder URI only, no passwords |
| T-02-02 | Elevation of Privilege (debug mode) | mitigate | CLOSED | `app/config.py` lines 17-24: `_env_flag()` helper, strict parsing — only `1/true/yes/on` enable debug; `0/false/empty` all disable. `Config.DEBUG = _env_flag("FLASK_DEBUG")` (line 37) defaults False. `wsgi.py` line 11: `app = create_app()` — no `app.run()`, no Flask dev server in production path |
| T-02-03 | Tampering / Injection (POST body, path param) | mitigate | CLOSED | `entries.py` line 73: `isinstance(data, dict)` guard — non-dict body → 400. Line 83: `isinstance(tags, list) and all(isinstance(t, str) for t in tags)` — invalid tags → 400. Lines 79-80: required-field validation → 400. Lines 52-56: `ObjectId()` wrapped in `try/except InvalidId` → 404 for malformed ids. Line 58: `find_one({"_id": oid})` and line 95: `insert_one(doc)` — dict-based queries, no string interpolation |
| T-02-04 | Denial of Service (unbounded GET /entries) | accept | CLOSED | Accepted risk — see Accepted Risks section below |
| T-02-SC | Tampering (supply chain — runtime deps) | mitigate | CLOSED | `requirements.txt`: all 6 packages pinned with exact `==` versions: `Flask==3.1.3`, `Flask-PyMongo==3.0.1`, `pymongo==4.13.2`, `gunicorn==26.0.0`, `prometheus-flask-exporter==0.23.2`, `python-dotenv==1.2.2` |
| T-03-01 | Tampering (supply chain — test deps) | mitigate | CLOSED | `requirements-dev.txt`: all 4 test packages pinned with exact `==` versions: `pytest==9.1.1`, `pytest-flask==1.3.0`, `pytest-cov==5.0.0`, `mongomock==4.3.0`. See deviation note below |
| T-03-02 | Information Disclosure (tests hitting real DB) | mitigate | CLOSED | `tests/conftest.py` lines 39-44: `mongomock.MongoClient()` patched via `monkeypatch.setattr(mongo, "cx", mock_client)` and `monkeypatch.setattr(mongo, "db", mock_db)`. No real MONGO_URI with credentials. `monkeypatch` auto-restores after each test, preventing state leakage |
| T-03-03 | Spoofing (false green suite) | mitigate | CLOSED | `tests/conftest.py` lines 58-79: `mongo_down` fixture monkeypatches `health_module.mongo` to raise `pymongo.errors.ConnectionFailure`. `test_health.py` line 24: `test_health_down(mongo_down)` asserts HTTP 503 — 503 branch exercised. `pytest.ini` line 3: `--cov-fail-under=95` enforces coverage gate as exit-code failure |

---

## Accepted Risks

| Threat ID | Category | Risk | Justification | Review Milestone |
|-----------|----------|------|---------------|------------------|
| T-02-04 | Denial of Service | `GET /entries` performs a full MongoDB collection scan with no cursor limit or pagination | Single-user local development deployment; no external traffic; dataset size trivial (dogfood app). Pagination is documented as out-of-scope for PRD-1 in `.planning/phases/01-scaffold-app-tests/01-02-PLAN.md` (T-02-04 mitigation plan). No production users at risk. | Re-evaluate at PRD-3 (multi-user / external-access milestone) |

---

## Deviation Notes

### T-03-01: mongomock version deviation (4.1.2 → 4.3.0)

- **Plan specified:** `mongomock==4.1.2`
- **Implemented:** `mongomock==4.3.0`
- **Reason:** `mongomock 4.1.2` imports `pkg_resources` in its `__version__` module. Python 3.12 ships with `setuptools>=83`, which removed `pkg_resources` as a standalone module. `mongomock 4.3.0` replaces the dependency with `importlib.metadata`.
- **Package legitimacy:** `mongomock` is the canonical MongoDB test double maintained under PyPI package name `mongomock`. Version 4.3.0 is an official release. Verified by `grep -r pkg_resources` returning no matches after upgrade.
- **Pin is exact:** `mongomock==4.3.0` — no range or unpinned entry.
- **Documented in:** `.planning/phases/01-scaffold-app-tests/01-03-SUMMARY.md` (Deviations section, item 2).
- **Risk delta:** Negligible — minor patch upgrade within the same major version, same package, same purpose. Pin remains exact.

---

## Unregistered Threat Flags

None. All three SUMMARY files (`01-01-SUMMARY.md`, `01-02-SUMMARY.md`, `01-03-SUMMARY.md`) report no new security surface beyond what the phase threat model covers.

---

## Scope

This audit covers all threats declared in the phase 01 threat registers:

- **01-01-PLAN.md** — T-01-01, T-01-02, T-01-03 (git hygiene / monorepo scaffold)
- **01-02-PLAN.md** — T-02-01, T-02-02, T-02-03, T-02-04, T-02-SC (Flask API implementation)
- **01-03-PLAN.md** — T-03-01, T-03-02, T-03-03 (test suite)

Post-review fixes from `01-REVIEW-FIX.md` were incorporated and verified:

| Fix | Commit | Threat Reinforced |
|-----|--------|-------------------|
| CR-01: Non-dict JSON body → 400 | `737fba2` | T-02-03 |
| CR-02: Invalid `tags` type → 400 | `4847d43` | T-02-03 |
| WR-01: Strict `_env_flag()` parsing for FLASK_DEBUG | `eaed2e1` | T-02-02 |

**Files in scope:** `.gitignore`, `.gitattributes`, `apps/field-guide-api/app/__init__.py`, `apps/field-guide-api/app/config.py`, `apps/field-guide-api/app/extensions.py`, `apps/field-guide-api/app/routes/entries.py`, `apps/field-guide-api/app/routes/health.py`, `apps/field-guide-api/wsgi.py`, `apps/field-guide-api/requirements.txt`, `apps/field-guide-api/requirements-dev.txt`, `apps/field-guide-api/.env.example`, `apps/field-guide-api/tests/conftest.py`, `apps/field-guide-api/pytest.ini`, `Makefile`
