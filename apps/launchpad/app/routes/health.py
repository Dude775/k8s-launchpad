"""
Health endpoint.

GET /health
  200 {"status": "ok"}   — plain liveness signal, no Mongo check (D-04)

This route name stays stable across phases: Phase 7 (STAT-03) evolves this
same /health in place into the real readiness probe (pings launchpad's own
MongoDB, returns 503 when down). Do not invent a separate /healthz.
"""

from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.route("/health", methods=["GET"])
def health():
    """Return a plain liveness signal."""
    return jsonify({"status": "ok"}), 200
