"""
Service catalog repository helper (CAT-01, CAT-02, CAT-05 data layer).

This module is a bare helper (NO Blueprint) — mirrors app/status.py's shape:
exported functions that never raise, degrading to safe sentinel values on
any failure. Exception detail is always discarded — never str(exception) —
so no hostname, stack trace, or connection-string fragment can leak into any
HTML or JSON representation (T-08-06 / T-07-07 discipline).

Uniqueness of the service name is enforced by the MongoDB unique index on
services.name (D-02, D-03) — register_service() translates the resulting
DuplicateKeyError into the locked UI-SPEC field-error copy instead of ever
letting it escape. Callers in route modules must import this module as a
module attribute (`from app import catalog` -> `catalog.register_service(...)`)
so tests can monkeypatch these functions (Phase 8 plan-check BLOCKER 3 lesson).
"""

from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from app.extensions import mongo

# Locked UI-SPEC Copywriting Contract strings — fixed generic copy, never
# built from exception detail.
DUPLICATE_NAME_ERROR = "This name is already registered — choose another."
GENERIC_SAVE_ERROR = "Could not save this service. Check the fields below and try again."


def ensure_indexes() -> None:
    """Create the unique index on services.name (D-02, D-03).

    Idempotent — safe to call on every create_app(). Never raises: an
    index-creation hiccup degrades silently rather than blocking startup.
    """
    try:
        mongo.db.services.create_index("name", unique=True)
    except Exception:
        pass


def list_services() -> list[dict]:
    """All registered services, newest-registered first (CAT-01).

    Never raises — returns [] when the collection is empty or the DB errors.
    """
    try:
        return list(mongo.db.services.find().sort("registered_at", -1))
    except Exception:
        return []


def get_service(name: str) -> dict | None:
    """The service registered under `name`, or None if absent / on failure.

    Plain equality match only — `name` is Regexp-validated by ServiceForm
    before it ever reaches a query, and PyMongo's dict-encoded query (never
    string interpolation, never $where) is injection-resistant (T-09-02).
    """
    try:
        return mongo.db.services.find_one({"name": name})
    except Exception:
        return None


def register_service(data: dict) -> tuple[bool, str | None]:
    """Persist one service registration (CAT-02).

    Returns (True, None) on success, (False, error_message) otherwise.
    Never raises — DuplicateKeyError becomes the locked uniqueness copy
    (race-safe: the unique index, not a pre-check, is the enforcement
    boundary), any other failure becomes the generic form-level copy.
    Stamps registered_at so list_services()' sort key always exists.
    """
    try:
        document = dict(data)
        document.setdefault("registered_at", datetime.now(timezone.utc))
        mongo.db.services.insert_one(document)
        return True, None
    except DuplicateKeyError:
        return False, DUPLICATE_NAME_ERROR
    except Exception:
        return False, GENERIC_SAVE_ERROR


def deregister_service(name: str) -> bool:
    """Remove the service registered under `name` (CAT-05).

    Returns True if a document was removed, False when the name is absent
    or the DB errors. Never raises.
    """
    try:
        result = mongo.db.services.delete_one({"name": name})
        return result.deleted_count == 1
    except Exception:
        return False
