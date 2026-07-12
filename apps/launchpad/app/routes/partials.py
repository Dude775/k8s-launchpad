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

GET /partials/cluster-state
  200 — an HTML fragment (partials/cluster_state.html alone) when the
        HX-Request header is present ("true"), or a full page
        (cluster_state_full_page.html) otherwise. Same fragment-vs-full-page
        split as /partials/status-cards, mirrored byte-for-byte (DIAG-02).

GET /partials/feed
  200 — an HTML fragment (partials/feed_events.html alone) when the
        HX-Request header is present ("true"), or a full page
        (feed_full_page.html) otherwise. Same fragment-vs-full-page split as
        the two routes above (FEED-01).
"""

from flask import Blueprint, render_template, request

from app import events
from app.cluster_state import get_cluster_state
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


@partials_bp.route("/cluster-state", methods=["GET"])
def cluster_state():
    """Read-only Kubernetes pods/deployments state, fragment for htmx or
    full page for direct navigation (DIAG-02)."""
    state = get_cluster_state()
    if request.headers.get("HX-Request") == "true":
        return render_template("partials/cluster_state.html", state=state)
    return render_template("cluster_state_full_page.html", state=state)


@partials_bp.route("/feed", methods=["GET"])
def feed():
    """Recent platform events, fragment for htmx or full page for direct
    navigation (FEED-01)."""
    recent = events.list_recent_events()
    if request.headers.get("HX-Request") == "true":
        return render_template("partials/feed_events.html", events_list=recent, events=events)
    return render_template("feed_full_page.html", events_list=recent, events=events)
