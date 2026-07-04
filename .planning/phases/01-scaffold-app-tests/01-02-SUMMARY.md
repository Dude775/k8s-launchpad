---
phase: "01-scaffold-app-tests"
plan: "02"
subsystem: "field-guide-api"
tags: ["flask", "pymongo", "prometheus", "gunicorn", "application-factory", "api"]

dependency_graph:
  requires: ["01-01"]
  provides: ["flask-api-factory", "entries-crud", "health-endpoint", "metrics-seam"]
  affects: ["01-03"]

tech_stack:
  added:
    - "Flask==3.1.3"
    - "Flask-PyMongo==3.0.1"
    - "pymongo==4.13.2"
    - "gunicorn==26.0.0"
    - "prometheus-flask-exporter==0.23.2"
    - "python-dotenv==1.2.2"
  patterns:
    - "Application factory pattern (create_app with config_overrides)"
    - "Deferred blueprint imports inside factory (Task1/Task2 ordering safety)"
    - "Unbound extension singletons (mongo, metrics) bound at init_app time"
    - "PyMongo dict queries — no string interpolation (injection protection)"

key_files:
  created:
    - "apps/field-guide-api/app/__init__.py"
    - "apps/field-guide-api/app/config.py"
    - "apps/field-guide-api/app/extensions.py"
    - "apps/field-guide-api/app/routes/__init__.py"
    - "apps/field-guide-api/app/routes/entries.py"
    - "apps/field-guide-api/app/routes/health.py"
    - "apps/field-guide-api/wsgi.py"
    - "apps/field-guide-api/requirements.txt"
    - "apps/field-guide-api/.env.example"
    - "apps/field-guide-api/tests/__init__.py"
    - "apps/field-guide-api/tests/test_factory.py"
    - "apps/field-guide-api/tests/test_routes.py"
  modified: []

decisions:
  - "Deferred blueprint imports inside create_app() body — keeps app/__init__.py importable before route modules exist, enabling Task1/Task2 split and isolated test instances"
  - "PrometheusMetrics.for_app_factory() pattern — defers /metrics route registration to init_app time, required for application factory"
  - "PyMongo dict queries only — all queries passed as Python dicts, no string interpolation, satisfies T-02-03 injection threat mitigation"
  - "Config.DEBUG derived from bool(os.environ.get('FLASK_DEBUG', '')) — falsy by default, never hardcoded True"
  - "mongo.cx.admin.command('ping') for health check — lightweight connectivity check per MongoDB driver recommendation"
  - "Python 3.12 used instead of locked 3.11 — 3.11 not installed on this host; all pinned packages explicitly support 3.12 per CLAUDE.md compatibility matrix (Rule 3 deviation)"

metrics:
  duration: "~41 minutes"
  completed: "2026-07-04T16:23:30Z"
  tasks_completed: 2
  files_created: 12
  commits: 4
---

# Phase 01 Plan 02: Field-Guide Flask API Implementation Summary

**One-liner:** Flask application factory with env-driven config, PyMongo CRUD, Prometheus metrics seam, and gunicorn-ready wsgi:app entrypoint serving six API requirements.

## What Was Built

A fully working `apps/field-guide-api/` Flask package providing:

- **Application factory** (`create_app(config_overrides=None)`) — wires Flask-PyMongo and PrometheusMetrics, registers blueprints via deferred local imports, supports TESTING overrides
- **Config class** — reads `MONGO_URI` and `FLASK_DEBUG` exclusively from environment; defaults to `mongodb://localhost:27017/fieldguide`; `DEBUG` defaults to `False`
- **Extension singletons** — `mongo = PyMongo()` and `metrics = PrometheusMetrics.for_app_factory()`, both unbound until `init_app`
- **Entries CRUD blueprint** — `GET /entries`, `GET /entries/<id>` (404 on malformed ObjectId), `POST /entries` (400 on missing title/content)
- **Health blueprint** — `GET /health` pings MongoDB via `mongo.cx.admin.command("ping")`; returns `200 ok` or `503 unavailable`
- **Prometheus seam** — `/metrics` auto-registered by `prometheus-flask-exporter`
- **gunicorn entrypoint** — `wsgi.py` targeting `wsgi:app`; Flask dev server never in production path
- **Requirements** — all six packages pinned to exact versions per CLAUDE.md

## Verification Results

All plan verify commands passed:

| Check | Result |
|-------|--------|
| `from app import create_app` (import-only, before routes exist) | IMPORT_OK |
| `create_app({'TESTING':True})` end to end, DEBUG=False | FACTORY_STRUCT_OK |
| POST /entries empty body → 400 | ROUTES_OK |
| GET /entries/malformed → 404 (not 500) | OK |
| GET /metrics → 200 with Prometheus text | OK |
| No hardcoded credentials in source | OK |
| All six packages pinned | OK |

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| Task 1 RED | 2e60774 `test(01-02): add failing test for application factory` | PASS |
| Task 1 GREEN | 43b4650 `feat(01-02): implement application factory config and extension wiring` | PASS |
| Task 2 RED | d08ecda `test(01-02): add failing test for entries routes and health endpoint` | PASS |
| Task 2 GREEN | 399f0e4 `feat(01-02): implement entries CRUD blueprint and health readiness endpoint` | PASS |

RED commits confirmed failing via `ImportError` / `ModuleNotFoundError` before implementation. GREEN commits confirmed passing all plan verify commands.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Python 3.12 used instead of locked Python 3.11**
- **Found during:** Task 1 setup
- **Issue:** Python 3.11 is not installed on this host; only 3.10, 3.12, 3.13 are available
- **Fix:** Used Python 3.12 to create the virtual environment; all six pinned packages explicitly support Python 3.12 per CLAUDE.md compatibility matrix (`prometheus-flask-exporter 0.23.2: tested against Python 3.8–3.12`, `gunicorn 26.0.0: requires ≥3.10`)
- **Impact:** None — the app code is fully Python 3.11-compatible; Docker image (Plan 04) will use `python:3.11-slim` per CLAUDE.md
- **Files modified:** None (venv only, not committed)

## Security Notes

Threat model mitigations applied (all T-02-xx from plan):

| Threat | Mitigation | Status |
|--------|-----------|--------|
| T-02-01: MongoDB URI disclosure | `MONGO_URI` read only from `os.environ`; no literal credentials in source | Applied |
| T-02-02: Flask debug mode elevation | `DEBUG = bool(os.environ.get("FLASK_DEBUG", ""))` — False by default; gunicorn entrypoint | Applied |
| T-02-03: Injection via POST body / path | Queries passed as Python dicts; `ObjectId()` in try/except → 404; required-field validation | Applied |
| T-02-SC: Supply chain (pip deps) | All six packages pinned to exact versions verified in CLAUDE.md | Applied |

## Known Stubs

None — all endpoints are implemented and data flows through to MongoDB. The `/health` endpoint returns 503 when MongoDB is unreachable (not a stub; correct behavior).

## Threat Flags

None — no new network endpoints, auth paths, file access patterns, or schema changes beyond what the plan's threat model covers.

## Self-Check

Files created/exist:
- [x] `apps/field-guide-api/app/__init__.py` — contains `def create_app`
- [x] `apps/field-guide-api/app/config.py` — contains `MONGO_URI`
- [x] `apps/field-guide-api/app/extensions.py` — contains `PyMongo()` and `PrometheusMetrics`
- [x] `apps/field-guide-api/app/routes/__init__.py` — re-exports `entries_bp`, `health_bp`
- [x] `apps/field-guide-api/app/routes/entries.py` — exports `entries_bp`, uses `mongo.db`
- [x] `apps/field-guide-api/app/routes/health.py` — exports `health_bp`, calls `command('ping')`
- [x] `apps/field-guide-api/wsgi.py` — contains `from app import create_app`
- [x] `apps/field-guide-api/requirements.txt` — contains `Flask==3.1.3`
- [x] `apps/field-guide-api/.env.example` — contains `MONGO_URI=`
- [x] `apps/field-guide-api/tests/test_factory.py`
- [x] `apps/field-guide-api/tests/test_routes.py`

Commits exist:
- [x] 2e60774 — test(01-02): add failing test for application factory
- [x] 43b4650 — feat(01-02): implement application factory config and extension wiring
- [x] d08ecda — test(01-02): add failing test for entries routes and health endpoint
- [x] 399f0e4 — feat(01-02): implement entries CRUD blueprint and health readiness endpoint
