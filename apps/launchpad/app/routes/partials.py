"""
htmx partial-fragment routes.

GET /partials/status-cards
  200 — an HTML fragment (partials/status_cards.html alone) when the
        HX-Request header is present ("true"), or a full page
        (status_full_page.html, which includes the same fragment via
        base.html) otherwise.

Phase 6 established this route path and template name, and its own
docstring explicitly forbade an HX-Request-conditional branch at the time
("must NEVER grow an HX-Request-conditional branch... add a NEW route
instead"). Phase 7's success criterion 4 explicitly requires that exact
behavior — this is a deliberate, documented evolution of the Phase 6
contract, not a violation of it: the route path (/partials/status-cards)
and the fragment's template name (partials/status_cards.html) are
unchanged, satisfying Phase 6's own forward-looking note that "Phase 7
replaces the stub data... route path, template name, and the htmx hx-get
target in index.html all stay the same."

Phase 7 (STAT-01/02) replaces the Phase 6 stub data with real
get_platform_status() internals — the same helper GET /api/status uses, so
the JSON contract and the dashboard cards can never drift apart.
"""

from flask import Blueprint, render_template, request

from app.status import get_platform_status

partials_bp = Blueprint("partials", __name__, url_prefix="/partials")


@partials_bp.route("/status-cards", methods=["GET"])
def status_cards():
    """Real platform status, fragment for htmx or full page for direct
    navigation (STAT-01/02)."""
    status = get_platform_status()
    if request.headers.get("HX-Request") == "true":
        return render_template("partials/status_cards.html", status=status)
    return render_template("status_full_page.html", status=status)
