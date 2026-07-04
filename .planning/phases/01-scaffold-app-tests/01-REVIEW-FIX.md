---
phase: 01-scaffold-app-tests
fixed_at: 2026-07-05T02:03:00Z
review_path: .planning/phases/01-scaffold-app-tests/01-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 7
skipped: 0
status: all_fixed
---

# Phase 01: Code Review Fix Report

**Fixed at:** 2026-07-05T02:03:00Z
**Source review:** .planning/phases/01-scaffold-app-tests/01-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 7 (fix_scope: critical_warning — CR-01, CR-02, WR-01..WR-05; IN-01..IN-04 out of scope)
- Fixed: 7
- Skipped: 0

Every fix was verified by running the full pytest suite in an isolated Python 3.12 venv before committing. Final state: **32 tests pass, 100% coverage** (`--cov-fail-under=95` gate satisfied). `make test PYTHON="py -3.12"` was executed end to end to validate the new Makefile venv flow.

## Fixed Issues

### CR-01: Non-object JSON body causes unhandled 500 in POST /entries

**Files modified:** `apps/field-guide-api/app/routes/entries.py`, `apps/field-guide-api/tests/test_entries.py`
**Commit:** 737fba2
**Applied fix:** Replaced `request.get_json(silent=True) or {}` with an `isinstance(data, dict)` guard returning 400 (`"request body must be a JSON object"`). Non-object bodies (arrays, strings) and non-JSON bodies now return 400, never 500. Added the never-500 body invariant to the module security notes. Regression tests: array body, string body, and non-JSON body all assert 400 with an error key.

### CR-02: Unvalidated `tags` type — 500 on non-iterable, silent corruption on string

**Files modified:** `apps/field-guide-api/app/routes/entries.py`, `apps/field-guide-api/tests/test_entries.py`
**Commit:** 4847d43
**Applied fix:** Added `isinstance(tags, list) and all(isinstance(t, str) ...)` validation returning 400 (`"tags must be a list of strings"`) before the insert; the stored document now uses the validated list verbatim (no blind `list()` coercion). Regression tests: `tags: 5` → 400, `tags: "abc"` → 400 (no char-splitting), `tags: ["ok", 1]` → 400, valid `["k8s", "helm"]` stored unchanged with 201.

### WR-01: `FLASK_DEBUG=0` / `FLASK_DEBUG=false` enables debug mode

**Files modified:** `apps/field-guide-api/app/config.py`, `apps/field-guide-api/.env.example`, `apps/field-guide-api/tests/test_factory.py`
**Commit:** eaed2e1
**Applied fix:** Introduced `_env_flag()` helper in config.py that only treats `"1"/"true"/"yes"/"on"` (case-insensitive, stripped) as truthy — matching Flask CLI semantics — and switched `Config.DEBUG` to use it. Updated the `.env.example` comment to document the new semantics. Regression tests cover `0/false/no/off/empty` → False and `1/true/yes/on` → True.

### WR-02: Health ping has no timeout — Mongo outage blocks the sole gunicorn worker for up to 30s

**Files modified:** `apps/field-guide-api/app/__init__.py`, `apps/field-guide-api/tests/test_health.py`
**Commit:** e1e74c4
**Applied fix:** `create_app` now sets `app.config.setdefault("MONGO_SERVER_SELECTION_TIMEOUT_MS", 2000)` and passes `serverSelectionTimeoutMS` through `mongo.init_app(...)` to the MongoClient, bounding server selection to ~2s regardless of the supplied MONGO_URI. `/health` now returns 503 within ~2s during a Mongo outage instead of hanging 30s. Regression tests assert `mongo.cx.options.server_selection_timeout == 2.0` by default and honor a config override (0.5s).

### WR-03: `test_config_debug_defaults_false` is flaky when developer's local `.env` sets FLASK_DEBUG

**Files modified:** `apps/field-guide-api/tests/test_factory.py`
**Commit:** fdda278
**Applied fix:** Rewrote the test to use `monkeypatch.delenv("FLASK_DEBUG", raising=False)` (auto-restored) and to test the `_env_flag` parsing helper directly — no `importlib.reload`, so `load_dotenv()` never re-reads a developer's `.env` mid-test, and no divergent Config class is left behind. Removed the now-unused `import os`. Verified: factory tests pass with `FLASK_DEBUG=1` exported in the environment.

### WR-04: Local fixtures in test_routes.py shadow conftest's mocked-Mongo fixtures

**Files modified:** `apps/field-guide-api/tests/test_routes.py`
**Commit:** c78fbf2
**Applied fix:** Deleted the local unmocked `app`/`client` fixtures so the file uses conftest's mongomock-backed fixtures (future DB-touching tests can no longer hit a real `localhost:27017`). Removed the duplicated cases (four POST-400 tests, malformed-id 404, two /metrics tests — all covered in test_entries.py / test_metrics.py). Kept the unique tests: blueprint importability (entries/health) and DEBUG-false-under-TESTING. Suite count dropped from 39 to 32 with coverage still 100%.

### WR-05: `make test` installs packages into whatever `pip` resolves to — no venv

**Files modified:** `Makefile`
**Commit:** ae070b7
**Applied fix:** `make test` now idempotently creates `apps/field-guide-api/.venv` using an overridable `PYTHON ?= python3` variable (`make test PYTHON="py -3.12"` on Windows Git Bash, `PYTHON=python3.11` on WSL2), resolves the venv interpreter portably (`.venv/bin/python` or `.venv/Scripts/python`), and runs pip/pytest via `$VENV_PY -m ...` — no bare `pip`/`pytest` and no activation-script dependency. Header lines (`SHELL := /bin/bash`, `MSYS_NO_PATHCONV=1`) kept intact. `.venv/` was already gitignored. Verified end to end on this host: venv created, deps installed, 32 tests pass.

## Skipped Issues

None — all in-scope findings were fixed. (IN-01 through IN-04 are Info severity and outside the `critical_warning` fix scope.)

---

_Fixed: 2026-07-05T02:03:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
