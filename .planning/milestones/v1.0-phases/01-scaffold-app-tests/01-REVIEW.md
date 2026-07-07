---
phase: 01-scaffold-app-tests
reviewed: 2026-07-04T22:37:00Z
depth: standard
files_reviewed: 22
files_reviewed_list:
  - apps/field-guide-api/app/__init__.py
  - apps/field-guide-api/app/config.py
  - apps/field-guide-api/app/extensions.py
  - apps/field-guide-api/app/routes/__init__.py
  - apps/field-guide-api/app/routes/entries.py
  - apps/field-guide-api/app/routes/health.py
  - apps/field-guide-api/wsgi.py
  - apps/field-guide-api/requirements.txt
  - apps/field-guide-api/requirements-dev.txt
  - apps/field-guide-api/.env.example
  - apps/field-guide-api/pytest.ini
  - apps/field-guide-api/tests/__init__.py
  - apps/field-guide-api/tests/conftest.py
  - apps/field-guide-api/tests/test_factory.py
  - apps/field-guide-api/tests/test_routes.py
  - apps/field-guide-api/tests/test_entries.py
  - apps/field-guide-api/tests/test_health.py
  - apps/field-guide-api/tests/test_metrics.py
  - Makefile
  - README.md
  - .gitignore
  - .gitattributes
findings:
  critical: 2
  warning: 5
  info: 4
  total: 11
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-07-04T22:37:00Z
**Depth:** standard
**Files Reviewed:** 22
**Status:** issues_found

## Summary

Reviewed the Flask field-guide API scaffold (app factory, config, extensions, entries CRUD blueprint, health endpoint, wsgi entrypoint), the pytest suite, root Makefile, and repo hygiene files. The test suite was executed in an isolated venv (Python 3.12): 28 tests pass at 100% coverage, and the shared `PrometheusMetrics` singleton tolerates repeated `init_app()` across test apps (no duplicate-registry errors — verified, not assumed).

However, adversarial probing of `POST /entries` with payloads outside the happy path **confirmed live 500-error paths and silent data corruption** that directly violate the module's own documented invariant ("malformed input → never 500", T-02-03). All Critical findings below were reproduced by executing the code, not inferred. Additional confirmed issues: `FLASK_DEBUG=0` enables debug mode, the health ping has no timeout (blocks the single gunicorn worker up to 30s during a Mongo outage), and two test-reliability traps.

No hardcoded secrets found. `.gitignore` / `.gitattributes` are correct for the Windows/Git Bash constraint. Dependency pins match the locked stack in CLAUDE.md.

## Critical Issues

### CR-01: Non-object JSON body causes unhandled 500 in POST /entries

**File:** `apps/field-guide-api/app/routes/entries.py:71-74`
**Issue:** `request.get_json(silent=True)` returns whatever valid JSON the client sends — including arrays, strings, and numbers. The code only guards against `None`/falsy (`or {}`), then calls `data.get(...)`. A body of `[1,2]` or `"just a string"` raises `AttributeError: 'list' object has no attribute 'get'` → HTTP 500. **Reproduced:** `POST /entries` with body `[1,2]` → 500; body `"just a string"` → 500. This directly contradicts the security note at lines 18-22 ("malformed id → 404, never 500; required-field check returns 400 before touching the DB") — the never-500 invariant only holds for the id path, not the body path.
**Fix:**
```python
data = request.get_json(silent=True)
if not isinstance(data, dict):
    return jsonify({"error": "request body must be a JSON object"}), 400
```

### CR-02: Unvalidated `tags` type — 500 on non-iterable, silent corruption on string

**File:** `apps/field-guide-api/app/routes/entries.py:83`
**Issue:** `list(data.get("tags", []))` performs blind coercion with two confirmed failure modes:
1. `"tags": 5` → `TypeError: 'int' object is not iterable` → HTTP 500 (**reproduced**).
2. `"tags": "abc"` → silently stored and returned as `["a", "b", "c"]` — HTTP 201 with corrupted data (**reproduced**: response contained `'tags': ['a', 'b', 'c']`). The documented schema (line 11) requires `[str]`; a plain string is a highly likely client mistake and it persists garbage instead of failing.
**Fix:**
```python
tags = data.get("tags", [])
if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
    return jsonify({"error": "tags must be a list of strings"}), 400
```

## Warnings

### WR-01: `FLASK_DEBUG=0` / `FLASK_DEBUG=false` enables debug mode

**File:** `apps/field-guide-api/app/config.py:26`
**Issue:** `DEBUG: bool = bool(os.environ.get("FLASK_DEBUG", ""))` treats ANY non-empty string as truthy. **Reproduced:** with `FLASK_DEBUG=0`, `Config.DEBUG == True`. The conventional way to disable debug (`FLASK_DEBUG=0`, `FLASK_DEBUG=false` — the exact semantics Flask's own CLI uses) silently *enables* it. The project's CLAUDE.md explicitly lists "debug mode in prod is a security risk". The `.env.example` comment documents the non-empty convention, but an operator setting `FLASK_DEBUG=0` in a container gets the opposite of what they asked for. Debug=True also flips `PROPAGATE_EXCEPTIONS`, changing error behavior under gunicorn.
**Fix:**
```python
DEBUG: bool = os.environ.get("FLASK_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")
```

### WR-02: Health ping has no timeout — Mongo outage blocks the sole gunicorn worker for up to 30s

**File:** `apps/field-guide-api/app/routes/health.py:30` (root cause also `app/config.py:20-22`)
**Issue:** `mongo.cx.admin.command("ping")` uses PyMongo's default `serverSelectionTimeoutMS` of 30000ms because neither the default `MONGO_URI` nor `init_app` configures a timeout. When MongoDB is unreachable, `/health` hangs ~30 seconds before returning 503. The deployment plan is gunicorn with **1 sync worker** (per CLAUDE.md stack); during a Mongo outage every readinessProbe hit occupies the only worker for 30s, stalling ALL requests and making Kubernetes probe timeouts (default 1s) fail by timeout rather than by the intended 503. The readiness signal this endpoint exists to provide (per its own docstring, lines 8-11) does not work under the failure condition it is designed to detect.
**Fix:** Bound server selection for the health check, e.g. append `?serverSelectionTimeoutMS=2000` to the default/documented `MONGO_URI`, or configure it in `create_app`: `app.config.setdefault("MONGO_SERVER_SELECTION_TIMEOUT_MS", 2000)` / pass `serverSelectionTimeoutMS=2000` through `mongo.init_app(app, serverSelectionTimeoutMS=2000)`.

### WR-03: `test_config_debug_defaults_false` is flaky when developer's local `.env` sets FLASK_DEBUG

**File:** `apps/field-guide-api/tests/test_factory.py:32-42`
**Issue:** The test does `os.environ.pop("FLASK_DEBUG", None)` (global env mutation, never restored — pollutes subsequent tests in the same session) and then `importlib.reload(cfg_module)`. The reload re-executes `load_dotenv()` (config.py:14), which re-reads `.env` from disk. Since the variable was just popped, `load_dotenv` (which only skips *existing* env vars) will re-set `FLASK_DEBUG` from the file. `.env.example` explicitly tells developers to set `FLASK_DEBUG=1` for local debugging — any developer who does so and runs `make test` gets a failing test that has nothing to do with their change. The reload also leaves a divergent `Config` class object from the one `app/__init__.py` captured at import.
**Fix:** Use `monkeypatch.delenv("FLASK_DEBUG", raising=False)` for auto-restore, and prevent the `.env` re-read during reload (e.g. `monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)` before `importlib.reload`), or test the parsing logic directly instead of reloading the module.

### WR-04: Local fixtures in test_routes.py shadow conftest's mocked-Mongo fixtures — unmocked DB trap + duplicated coverage

**File:** `apps/field-guide-api/tests/test_routes.py:18-34`
**Issue:** This file defines its own `app`/`client` fixtures that call `create_app` **without any mongomock patching**, silently shadowing the conftest.py fixtures that provide DB isolation. Today no test in this file touches the DB (all hit validation/metrics paths before Mongo), so the suite passes — but any future DB-touching test added here will attempt a real connection to `localhost:27017` with a 30s server-selection hang (see WR-02), producing an environment-dependent failure that looks nothing like its cause. Additionally, this file duplicates tests that already exist elsewhere: the three POST-400 tests and malformed-id 404 duplicate `test_entries.py:55-76,112-115`; the two /metrics tests duplicate `test_metrics.py:15-22`.
**Fix:** Delete the local `app`/`client` fixtures so the file uses conftest's mocked fixtures, and remove the duplicated test cases (keep the blueprint-importability and DEBUG-under-TESTING tests, which are unique to this file).

### WR-05: `make test` installs packages into whatever `pip` resolves to — no venv

**File:** `Makefile:10`
**Issue:** `cd apps/field-guide-api && pip install -q -r requirements-dev.txt && pytest` runs bare `pip`/`pytest` against the active interpreter. On this host the default `python` is pyenv 3.7.4 — Flask 3.1.3/gunicorn 26 require ≥3.10, so `make test` either fails on install or pollutes a global site-packages with pinned versions. The user-level project rules mandate venv for Python projects, and the core-value loop (`make cluster-up && make build && ...`) depends on `make test` being reproducible on Git Bash/WSL2.
**Fix:**
```make
test:
	cd apps/field-guide-api && \
	python3.11 -m venv .venv 2>/dev/null || true && \
	. .venv/bin/activate && \
	pip install -q -r requirements-dev.txt && pytest
```
(and add `.venv/` to `.gitignore` — `.venv/` is already covered.)

## Info

### IN-01: `MONGO_DBNAME` config value is dead

**File:** `apps/field-guide-api/app/config.py:23`
**Issue:** `MONGO_DBNAME` is defined but never read — Flask-PyMongo 3.x derives the database name exclusively from the `MONGO_URI` path (`/fieldguide`), and no application code references this key. Dead config invites drift (changing `MONGO_DBNAME` does nothing).
**Fix:** Remove the attribute, or add a comment that the URI path is authoritative.

### IN-02: `app/routes/__init__.py` re-exports are unused and undermine the deferral rationale

**File:** `apps/field-guide-api/app/routes/__init__.py:3-6`
**Issue:** Nothing imports `entries_bp`/`health_bp` from the package — `create_app` imports directly from the submodules. Moreover, because importing `app.routes.entries` first executes this `__init__.py` (which imports *both* blueprints), the two route modules are not actually independently importable, slightly contradicting the deferred-import commentary in `app/__init__.py:47`.
**Fix:** Empty the file (keep it as a package marker) or keep the re-exports and drop the misleading rationale.

### IN-03: Unused `import pytest` in four test files

**File:** `apps/field-guide-api/tests/test_factory.py:14`, `tests/test_entries.py:13`, `tests/test_health.py:12`, `tests/test_metrics.py:12`
**Issue:** `pytest` is imported but never referenced in these modules (no fixtures/marks defined locally).
**Fix:** Remove the unused imports.

### IN-04: `str()` coercion stores reprs of non-string title/content/category

**File:** `apps/field-guide-api/app/routes/entries.py:73-74,81`
**Issue:** Non-string values are coerced via `str()` rather than rejected. **Reproduced:** `{"title": {"a": 1}, "content": "c"}` → 201 with stored title `"{'a': 1}"`. Documents accumulate Python-repr garbage instead of the client receiving a 400.
**Fix:** Validate `isinstance(value, str)` for title/content/category and return 400 otherwise (naturally covered by the CR-01/CR-02 validation fix).

---

_Reviewed: 2026-07-04T22:37:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
