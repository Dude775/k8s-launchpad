"""
Health / readiness endpoint.

GET /health
  200 {"status": "ok", "mongo": "up"}    — MongoDB responds to ping
  503 {"status": "unavailable", "mongo": "down"}  — MongoDB unreachable

This endpoint is the readiness signal consumed by:
  - Plan 03 tests (smoke test without live DB via mock / TESTING override)
  - Kubernetes readinessProbe (Phase 2+)
  - PRD-4 Prometheus alerting (Phase 4)

mongo.cx is the underlying MongoClient from Flask-PyMongo 3.x;
admin.command("ping") is the lightweight connectivity check recommended by
the MongoDB driver docs and does not require auth on the admin database when
the server is accessible.
"""

from flask import Blueprint, jsonify

from app.extensions import mongo

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health():
    """Return MongoDB readiness status."""
    try:
        mongo.cx.admin.command("ping")
        return jsonify({"status": "ok", "mongo": "up"}), 200
    except Exception:
        return jsonify({"status": "unavailable", "mongo": "down"}), 503
