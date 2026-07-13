"""
Platform events feed helper (FEED-01, FEED-02, FEED-03).

This module is a bare helper (NO Blueprint) — mirrors app/status.py's shape:
exported functions that never raise, degrading to safe sentinel values on
any failure. Exception detail is always discarded — never str(exception) —
so nothing internal leaks into any HTML or JSON representation (T-08-06 /
T-07-07 discipline).

Growth of the events collection is bounded by a TTL index on `ts` whose
expireAfterSeconds comes from config EVENTS_TTL_SECONDS (D-10, FEED-03).
NOTE (RESEARCH Pitfall 2): create_index() is NOT create-or-update for TTL
value changes — if EVENTS_TTL_SECONDS ever changes against a MongoDB that
already has the ts_1 index, MongoDB raises (swallowed here) and the old TTL
silently stays until a collMod migration; documented risk for this phase.

Callers in route modules must import this module as a module attribute
(`from app import events` -> `events.record_event(...)`) so tests can
monkeypatch these functions (Phase 8 plan-check BLOCKER 3 lesson).
"""

from datetime import datetime, timezone

from flask import current_app

from app.extensions import mongo

# Module-level once-per-process guard (D-12) — NOT stored on the Flask app
# object, because the requirement is "once per PROCESS" (gunicorn workers=1
# is locked, so process == the single worker); repeated create_app() calls
# in tests reset it explicitly via the hook below.
_platform_started_emitted = False


def ensure_indexes() -> None:
    """Create the TTL index on events.ts (D-10, FEED-03).

    expireAfterSeconds is config-driven (EVENTS_TTL_SECONDS, default 604800
    = 7 days) so smoke tests can verify expiry with a short window.
    Idempotent — safe to call on every create_app(). Never raises.
    """
    try:
        ttl_seconds = current_app.config["EVENTS_TTL_SECONDS"]
        mongo.db.events.create_index("ts", expireAfterSeconds=ttl_seconds)
    except Exception:
        pass


def record_event(event_type: str, service_name: str | None) -> bool:
    """Write one event document {type, service_name, ts} (FEED-02).

    Never raises — returns False on any failure so callers (registration /
    deregistration flows) can proceed even if the events write fails; the
    primary catalog mutation must never be blocked by a secondary
    feed-write failure.
    """
    try:
        mongo.db.events.insert_one(
            {
                "type": event_type,
                "service_name": service_name,
                "ts": datetime.now(timezone.utc),
            }
        )
        return True
    except Exception:
        return False


def list_recent_events(limit: int = 50) -> list[dict]:
    """The most recent events, newest first, capped at `limit` (FEED-01).

    Never raises — returns [] on any failure.
    """
    try:
        return list(mongo.db.events.find().sort("ts", -1).limit(limit))
    except Exception:
        return []


def get_events_for_service(name: str) -> list[dict]:
    """All events for one service, newest first (CAT-04 Related Events).

    Never raises — returns [] on any failure.
    """
    try:
        return list(mongo.db.events.find({"service_name": name}).sort("ts", -1))
    except Exception:
        return []


def emit_platform_started_once() -> None:
    """Fire the platform_started event exactly once per process (D-12).

    Never raises. If Mongo is unreachable at call time, the event write
    fails silently (same never-raise contract as record_event) and the
    guard flag is NOT set — so a later successful write attempt (e.g. a
    subsequent create_app() call once Mongo becomes reachable) can still
    fire it. This matches D-12's "first readiness" framing more precisely
    than an unconditional one-shot flag.
    """
    global _platform_started_emitted
    if _platform_started_emitted:
        return
    if record_event("platform_started", service_name=None):
        _platform_started_emitted = True


def reset_platform_started_guard_for_tests() -> None:
    """Test-only reset hook — conftest.py's `app` fixture calls this so each
    isolated test app can independently exercise the guard's first-call path."""
    global _platform_started_emitted
    _platform_started_emitted = False


def _relative_time(ts) -> str:
    """Render a "2 minutes ago"-style string from a tz-aware timestamp.

    Server-computed (Python, not JS) so it renders correctly on first paint
    before any htmx swap — mirrors cluster_state._pod_age's shape. Never
    raises: falls back to "unknown" if the timestamp is missing or malformed.
    """
    if ts is None:
        return "unknown"
    try:
        # CR-01: real PyMongo decodes BSON dates as timezone-NAIVE by default
        # (mongomock does not reproduce this). Normalize a naive datetime to
        # UTC-aware before the subtraction below; non-datetime garbage still
        # raises here and falls through to the except -> "unknown".
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - ts
        seconds = int(delta.total_seconds())
        if seconds < 0:
            seconds = 0
        if seconds < 60:
            return "just now"
        minutes = seconds // 60
        if minutes < 60:
            count, unit = minutes, "minute"
        elif minutes < 1440:
            count, unit = minutes // 60, "hour"
        else:
            count, unit = minutes // 1440, "day"
        suffix = "" if count == 1 else "s"
        return f"{count} {unit}{suffix} ago"
    except Exception:
        return "unknown"
