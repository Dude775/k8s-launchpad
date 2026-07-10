"""
Health endpoint.

GET /health
  200 {"status": "ok", "mongo": "up"}          — launchpad's own MongoDB ping succeeded
  503 {"status": "unavailable", "mongo": "down"} — the ping raised

This is the Kubernetes readinessProbe target (wired in Phase 8's Deployment
manifest, not this phase, but the contract must be correct now so Phase 8
can wire it without further route changes). This route name stays stable
across phases — do not invent a separate /healthz.

CRITICAL (STAT-03 / RESEARCH Pitfall 1): this module imports ONLY
app.extensions.mongo. It must never import the outbound HTTP client library
or reference the sibling service's base-URL config key — see app/status.py
for the cross-service reachability check consumed by /api/status. A
field-guide-api outage must never cause Kubernetes to mark this pod NotReady.
"""

from flask import Blueprint, jsonify

from app.extensions import mongo

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health():
    """Return launchpad's own MongoDB readiness status.

    NEVER calls field-guide-api — see /api/status for downstream checks.
    """
    try:
        mongo.cx.admin.command("ping")
        return jsonify({"status": "ok", "mongo": "up"}), 200
    except Exception:
        return jsonify({"status": "unavailable", "mongo": "down"}), 503
