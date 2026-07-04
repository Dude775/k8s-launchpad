---
phase: 01-scaffold-app-tests
plan: "03"
subsystem: testing
tags: [pytest, mongomock, coverage, makefile]
dependency_graph:
  requires: ["01-02"]
  provides: ["TEST-01"]
  affects: ["Makefile", "apps/field-guide-api/tests/"]
tech_stack:
  added:
    - "pytest==9.1.1"
    - "pytest-flask==1.3.0"
    - "pytest-cov==5.0.0"
    - "mongomock==4.3.0"
  patterns:
    - "mongomock patching PyMongo singleton instance attributes (cx, db) via monkeypatch"
    - "health 503 branch via health_module.mongo monkeypatch"
    - "pytest --cov-fail-under=95 as coverage gate"
key_files:
  created:
    - apps/field-guide-api/requirements-dev.txt
    - apps/field-guide-api/pytest.ini
    - apps/field-guide-api/tests/conftest.py
    - apps/field-guide-api/tests/test_entries.py
    - apps/field-guide-api/tests/test_health.py
    - apps/field-guide-api/tests/test_metrics.py
    - Makefile
  modified: []
decisions:
  - "Flask-PyMongo 3.x stores cx/db as instance attrs on PyMongo singleton, not in app.extensions — monkeypatch targets the singleton directly"
  - "mongomock 4.3.0 used (plan specified 4.1.2) — 4.1.2 imports pkg_resources which was removed from setuptools>=83; 4.3.0 drops that dependency"
  - "Makefile test target runs pip install + pytest — ensures fresh environment reproducibility"
metrics:
  duration: "11 minutes"
  completed_date: "2026-07-04"
  tasks_completed: 2
  files_created: 7
---

# Phase 01 Plan 03: Test Suite with Mocked MongoDB Summary

pytest suite with mongomock covering all API endpoints (entries CRUD, health up/down, Prometheus metrics) — 28 tests, 100% coverage, 0.53s, no cluster or real database required.

## What Was Built

| Artifact | Purpose |
|----------|---------|
| `requirements-dev.txt` | Pinned test stack: pytest 9.1.1, pytest-flask 1.3.0, pytest-cov 5.0.0, mongomock 4.3.0 |
| `pytest.ini` | `testpaths=tests`, `--cov=app`, `--cov-fail-under=95` coverage gate, `pythonpath=.` |
| `tests/conftest.py` | `app` fixture (mocked MongoDB), `client` fixture, `mongo_down` fixture (503 simulation) |
| `tests/test_entries.py` | 11 tests: list empty, post create, list after post, get by id found/missing/malformed, post validation (400) |
| `tests/test_health.py` | 2 tests: 200 mongo up, 503 mongo down |
| `tests/test_metrics.py` | 1 test: 200 + Prometheus text markers |
| `Makefile` | Root-level with `SHELL := /bin/bash`, `export MSYS_NO_PATHCONV=1`, and `test:` target |

## Verification Results

```
28 passed in 0.53s
Total coverage: 100.00%
Required test coverage of 95% reached.
```

All lines in all six app modules covered. Suite runs without Docker, kind cluster, or MongoDB.

## Decisions Made

1. **Flask-PyMongo 3.x stores cx/db on singleton, not app.extensions.** The `PyMongo.init_app()` method sets `self.cx` and `self.db` directly on the shared PyMongo instance. Fixtures use `monkeypatch.setattr(mongo, "cx", mock_client)` to swap in mongomock; `monkeypatch` auto-restores after each test.

2. **mongomock 4.3.0 (plan specified 4.1.2).** mongomock 4.1.2 imports `pkg_resources` in its `__version__` module. Python 3.12's default setuptools (83+) no longer ships `pkg_resources` as a standalone module. mongomock 4.3.0 drops this dependency. Deviation documented below.

3. **mongo_down patches `health_module.mongo` directly.** The health route imports `mongo` by name at module load, so we replace `app.routes.health.mongo` with a fake class whose `cx.admin.command()` raises `ConnectionFailure`. Simpler and more reliable than trying to unset the real MongoClient from extensions.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Flask-PyMongo 3.x extension storage differs from plan assumption**
- **Found during:** Task 2 (test execution — suite hung on real MongoDB connection)
- **Issue:** Plan assumed `app.extensions["pymongo"]` holds a dict-like state object with `cx`/`db` keys. Flask-PyMongo 3.0.1 actually stores `cx` and `db` as direct instance attributes on the shared `PyMongo` singleton (confirmed by reading installed source).
- **Fix:** Updated `conftest.py` to use `monkeypatch.setattr(mongo, "cx", mock_client)` targeting the singleton instance attributes directly.
- **Files modified:** `apps/field-guide-api/tests/conftest.py`
- **Commit:** 4d35eb7

**2. [Rule 3 - Blocking] mongomock 4.1.2 incompatible with setuptools 83+ (pkg_resources removed)**
- **Found during:** Task 2 install/run
- **Issue:** `mongomock/__version__.py` does `import pkg_resources`; setuptools 83.x (default in Python 3.12 fresh venv) removed `pkg_resources` as a standalone module.
- **Fix:** Upgraded pin to `mongomock==4.3.0` which replaced `pkg_resources` with `importlib.metadata`. Verified with `grep -r pkg_resources` — no matches.
- **Files modified:** `apps/field-guide-api/requirements-dev.txt`
- **Commit:** 4d35eb7

## Known Stubs

None — all test fixtures produce real in-memory responses; no hardcoded empty returns.

## Threat Flags

None — test suite creates no new network endpoints, auth paths, or schema changes.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| `apps/field-guide-api/requirements-dev.txt` | FOUND |
| `apps/field-guide-api/pytest.ini` | FOUND |
| `apps/field-guide-api/tests/conftest.py` | FOUND |
| `apps/field-guide-api/tests/test_entries.py` | FOUND |
| `apps/field-guide-api/tests/test_health.py` | FOUND |
| `apps/field-guide-api/tests/test_metrics.py` | FOUND |
| `Makefile` | FOUND |
| commit `5f90e06` (Task 1) | FOUND |
| commit `4d35eb7` (Task 2) | FOUND |
