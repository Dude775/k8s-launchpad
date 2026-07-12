"""
Dashboard page routes.

GET /                          200 — landing page (UI-01: presents k8s-launchpad as an IDP)
GET /catalog                    200 — service catalog list (CAT-01)
GET/POST /catalog/new           200/302 — onboard-a-service form (CAT-02, CAT-03)
GET /catalog/<name>             200/404 — service detail + related events (CAT-04)
GET /catalog/<name>/delete      200/404 — zero-JS deregister confirm page (CAT-05)
POST /catalog/<name>/delete     302/404 — deregister a service (CAT-05)
GET /diagnostics                200 — platform diagnostics page
GET /feed                       200 — activity feed page

Phase 6 scope: all four original routes render inside the shared base.html
shell (sidebar nav + topbar). Phase 8 (STAT-*) filled in diagnostics; Phase 9
(CAT-*) fills in catalog (list, onboard, detail, deregister) and feed. These
route names stay stable across phases: later phases evolve the same routes
in place, mirroring the Phase 5 "/health" convention. Do not rename or
restructure.

Module-attribute import discipline (Phase 8 plan-check BLOCKER 3, carried
into Phase 9): `from app import catalog, events` — NEVER
`from app.catalog import register_service` etc. — so tests can monkeypatch
catalog.register_service / events.record_event directly at the module level.
"""

from datetime import datetime, timezone

from flask import Blueprint, abort, redirect, render_template, url_for

from app import catalog, events
from app.forms import ServiceForm

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/", methods=["GET"])
def index():
    """Render the landing page with the live status-cards section."""
    return render_template("index.html")


@pages_bp.route("/catalog", methods=["GET"])
def catalog_list():
    """Render the service catalog list (CAT-01) — table or D-09 empty state."""
    services = catalog.list_services()
    return render_template("catalog.html", services=services)


@pages_bp.route("/catalog/new", methods=["GET", "POST"])
def catalog_new():
    """Onboard-a-service form (CAT-02, CAT-03).

    GET: render a fresh ServiceForm (fresh CSRF token).
    POST valid: persist via catalog.register_service, fire service_registered,
    redirect to /catalog. POST invalid (form validation OR duplicate name):
    full-page re-render with the SAME form object (D-06) — never a redirect,
    never a partial write.
    """
    form = ServiceForm()
    if form.validate_on_submit():
        data = {
            "name": form.name.data,
            "repo_url": form.repo_url.data,
            "owner": form.owner.data,
            "description": form.description.data,
            "environment": form.environment.data,
            "registered_at": datetime.now(timezone.utc),
        }
        success, message = catalog.register_service(data)
        if success:
            events.record_event("service_registered", data["name"])
            return redirect(url_for("pages.catalog_list"))
        form.name.errors.append(message)
    return render_template("onboard_form.html", form=form)


@pages_bp.route("/catalog/<name>", methods=["GET"])
def catalog_detail(name):
    """Service detail: full registration + related events (CAT-04)."""
    service = catalog.get_service(name)
    if service is None:
        abort(404)
    related_events = events.get_events_for_service(name)
    return render_template(
        "detail.html", service=service, events_for_service=related_events, events=events
    )


@pages_bp.route("/catalog/<name>/delete", methods=["GET"])
def catalog_delete_confirm(name):
    """Zero-JS deregister confirmation page (CAT-05, D-08)."""
    service = catalog.get_service(name)
    if service is None:
        abort(404)
    return render_template("confirm_delete.html", service=service)


@pages_bp.route("/catalog/<name>/delete", methods=["POST"])
def catalog_delete(name):
    """Deregister a service: remove the document, fire service_deregistered,
    redirect to /catalog (CAT-05)."""
    success = catalog.deregister_service(name)
    if success:
        events.record_event("service_deregistered", name)
    return redirect(url_for("pages.catalog_list"))


@pages_bp.route("/diagnostics", methods=["GET"])
def diagnostics():
    """Render the diagnostics page (Phase 8 fills in real content)."""
    return render_template("diagnostics.html")


@pages_bp.route("/feed", methods=["GET"])
def feed():
    """Render the activity feed page (Phase 9 fills in real content)."""
    return render_template("feed.html")
