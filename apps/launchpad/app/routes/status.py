"""
Platform status JSON endpoint.

GET /api/status
  200 — JSON body with six fields: api_health, mongo_status, app_version,
        service_count, field_guide_healthy, metrics_preview.

JSON-only, always — no HX-Request branching (RESEARCH Open Question 3).
Shares get_platform_status() with /partials/status-cards (app/status.py) so
the JSON payload and the dashboard's rendered cards can never diverge.
Never 500s — every sub-check inside get_platform_status() is independently
exception-isolated.
"""

from flask import Blueprint, jsonify

from app.status import get_platform_status

status_bp = Blueprint("status", __name__)


@status_bp.route("/api/status", methods=["GET"])
def api_status():
    """Return real platform status as JSON (STAT-01, STAT-02)."""
    return jsonify(get_platform_status()), 200
