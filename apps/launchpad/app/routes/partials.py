"""
htmx partial-fragment routes.

GET /partials/status-cards
  200 — HTML fragment only (never a full page, never wrapped in base.html).

This route is htmx-fragment-only BY DESIGN: it is only ever fetched via
htmx's hx-get from the #status-cards section on the landing page, never
navigated to directly by a user. It must NEVER grow an HX-Request-conditional
branch that wraps the fragment in base.html — that would silently change the
route's contract. If direct-navigation polish is ever wanted, add a NEW
route instead of mutating this one.

Phase 6: no status data source exists yet, so this always returns the
"unknown" degraded state (200, never 500). Phase 7 (STAT-*) replaces the
stub data with real /api/status internals in place — route path, template
name, and the htmx hx-get target in index.html all stay the same.
"""

from flask import Blueprint, render_template

partials_bp = Blueprint("partials", __name__, url_prefix="/partials")


@partials_bp.route("/status-cards", methods=["GET"])
def status_cards():
    """Phase 6: always-degraded stub. Phase 7 replaces the stub data with
    real /api/status internals — route path, template name, and the
    htmx hx-get target in index.html all stay the same."""
    return render_template(
        "partials/status_cards.html",
        status="unknown",
        cards=[],
    )
