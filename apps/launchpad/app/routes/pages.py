"""
Dashboard page routes.

GET /             200 — landing page (UI-01: presents k8s-launchpad as an IDP)
GET /catalog       200 — service catalog page
GET /diagnostics   200 — platform diagnostics page
GET /feed          200 — activity feed page

Phase 6 scope: all four routes render inside the shared base.html shell
(sidebar nav + topbar). /catalog, /diagnostics, and /feed render thin
placeholder content in Phase 6 — Phase 8 (STAT-*) fills in diagnostics,
Phase 9 (CAT-*) fills in catalog and feed. These route names stay stable
across phases: later phases evolve the same routes in place, mirroring the
Phase 5 "/health" convention. Do not rename or restructure.
"""

from flask import Blueprint, render_template

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/", methods=["GET"])
def index():
    """Render the landing page with the live status-cards section."""
    return render_template("index.html")


@pages_bp.route("/catalog", methods=["GET"])
def catalog():
    """Render the service catalog page (Phase 9 fills in real content)."""
    return render_template("catalog.html")


@pages_bp.route("/diagnostics", methods=["GET"])
def diagnostics():
    """Render the diagnostics page (Phase 8 fills in real content)."""
    return render_template("diagnostics.html")


@pages_bp.route("/feed", methods=["GET"])
def feed():
    """Render the activity feed page (Phase 9 fills in real content)."""
    return render_template("feed.html")
