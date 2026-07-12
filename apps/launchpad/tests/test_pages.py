"""
Dashboard page route tests.

Covers UI-01 (IDP landing page), UI-02 (shell + active nav), UI-03 (status
cards sourced from a real route, not hardcoded), UI-04 (htmx polling >=10s
with a tab-visibility guard).

Also covers CAT-01..05 (Phase 9): the real /catalog list, the /catalog/new
onboard form (GET/POST, valid/invalid/duplicate), /catalog/<name> detail,
and the /catalog/<name>/delete confirm+POST deregister flow. Tests
monkeypatch app.catalog / app.events functions via module attribute (never
direct-name import) per the Phase 8 plan-check BLOCKER 3 discipline.
"""

import re


def _register(client, name="svc-a", **overrides):
    """POST a valid onboard form submission; returns the response."""
    data = {
        "name": name,
        "repo_url": "https://github.com/org/repo",
        "owner": "team-a",
        "environment": "dev",
        "description": "",
    }
    data.update(overrides)
    return client.post("/catalog/new", data=data)


# --------------------------------------------------------------------------- #
# Landing page content (UI-01)                                                 #
# --------------------------------------------------------------------------- #


def test_index_200_and_content(client):
    """GET / is 200 and presents k8s-launchpad as an Internal Developer Platform."""
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "k8s-launchpad" in body
    assert "Internal Developer Platform" in body


# --------------------------------------------------------------------------- #
# Active nav state (UI-02)                                                     #
# --------------------------------------------------------------------------- #


def test_active_nav_per_route(client):
    """GET /catalog highlights the Catalog nav link as active."""
    resp = client.get("/catalog")
    body = resp.get_data(as_text=True)
    assert 'aria-current="page"' in body


# --------------------------------------------------------------------------- #
# Status cards sourced from a real route, not hardcoded (UI-03)                #
# --------------------------------------------------------------------------- #


def test_status_cards_not_hardcoded(client):
    """The landing page fetches status cards via htmx, not hardcoded text."""
    body = client.get("/").get_data(as_text=True)
    assert 'hx-get="/partials/status-cards"' in body


# --------------------------------------------------------------------------- #
# htmx polling contract (UI-04)                                                #
# --------------------------------------------------------------------------- #


def test_polling_attribute_contract(client):
    """The status-cards section polls every 15s and is guarded by tab visibility."""
    body = client.get("/").get_data(as_text=True)
    assert "every 15s" in body
    assert "visibilityState" in body


# --------------------------------------------------------------------------- #
# All four page routes render (coverage for every pages.py function)           #
# --------------------------------------------------------------------------- #


def test_all_pages_render(client):
    """GET on /, /catalog, /catalog/new, /diagnostics, /feed, plus a seeded
    /catalog/<name> and /catalog/<name>/delete, each return 200."""
    for path in ("/", "/catalog", "/catalog/new", "/diagnostics", "/feed"):
        resp = client.get(path)
        assert resp.status_code == 200, path

    _register(client, name="rendered-svc")
    for path in ("/catalog/rendered-svc", "/catalog/rendered-svc/delete"):
        resp = client.get(path)
        assert resp.status_code == 200, path


# --------------------------------------------------------------------------- #
# Catalog list (CAT-01)                                                       #
# --------------------------------------------------------------------------- #


def test_catalog_empty_state(client):
    """GET /catalog with zero services renders the D-09 empty-state CTA, not
    an empty table."""
    resp = client.get("/catalog")
    body = resp.get_data(as_text=True)
    assert "No services registered yet" in body
    assert 'href="/catalog/new"' in body


def test_catalog_lists_seeded_service(client):
    """GET /catalog with a seeded service renders a table row linking to the
    detail page."""
    _register(client, name="listed-svc")
    resp = client.get("/catalog")
    body = resp.get_data(as_text=True)
    assert '<a href="/catalog/listed-svc">listed-svc</a>' in body


# --------------------------------------------------------------------------- #
# Onboard form — GET (CAT-02)                                                 #
# --------------------------------------------------------------------------- #


def test_catalog_new_get_renders_form(client):
    """GET /catalog/new returns 200 with a rendered ServiceForm."""
    resp = client.get("/catalog/new")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Service Name" in body
    assert 'action="/catalog/new"' in body


def test_catalog_new_get_renders_fresh_csrf_token(app):
    """GET /catalog/new returns 200 with a fresh CSRF token present when
    CSRF protection is enabled (mirrors production posture)."""
    app.config["WTF_CSRF_ENABLED"] = True
    client = app.test_client()
    resp = client.get("/catalog/new")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "csrf_token" in body


# --------------------------------------------------------------------------- #
# Onboard form — valid POST (CAT-02, FEED-02)                                 #
# --------------------------------------------------------------------------- #


def test_catalog_new_post_valid_registers_and_redirects(client, monkeypatch):
    """POST /catalog/new with valid data calls register_service, fires
    service_registered via events.record_event, and redirects (302) to
    /catalog."""
    import app.events as events_module

    calls = []
    monkeypatch.setattr(
        events_module,
        "record_event",
        lambda event_type, service_name: calls.append((event_type, service_name)) or True,
    )

    resp = _register(client, name="new-svc")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/catalog"
    assert calls == [("service_registered", "new-svc")]


def test_catalog_new_post_valid_persists_document(client):
    """A successful POST /catalog/new actually writes a document (visible on
    a subsequent GET /catalog)."""
    _register(client, name="persisted-svc")
    body = client.get("/catalog").get_data(as_text=True)
    assert "persisted-svc" in body


# --------------------------------------------------------------------------- #
# Onboard form — invalid POST (CAT-03, D-06)                                  #
# --------------------------------------------------------------------------- #


def test_catalog_new_post_invalid_rerenders_without_calling_register(client, monkeypatch):
    """POST /catalog/new with invalid data re-renders onboard_form.html (200,
    full page — no redirect), preserving entered values and NOT calling
    catalog.register_service."""
    import app.catalog as catalog_module

    called = []
    monkeypatch.setattr(
        catalog_module, "register_service", lambda data: called.append(data) or (True, None)
    )

    resp = client.post(
        "/catalog/new",
        data={"name": "BAD NAME", "repo_url": "not-a-url", "owner": "", "environment": "dev"},
    )
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Use lowercase letters, numbers, and hyphens only (2–40 characters)." in body
    assert "Owner is required." in body
    assert "Enter a valid http:// or https:// URL." in body
    assert "BAD NAME" in body  # preserved value
    assert called == []


def test_catalog_new_post_duplicate_name_rerenders_with_uniqueness_message(client):
    """POST /catalog/new where register_service returns (False, msg)
    (duplicate name) re-renders the form showing the uniqueness message; no
    redirect."""
    _register(client, name="dup-svc")
    resp = _register(client, name="dup-svc", owner="team-b")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "This name is already registered" in body


# --------------------------------------------------------------------------- #
# Detail page (CAT-04)                                                        #
# --------------------------------------------------------------------------- #


def test_catalog_detail_shows_registration_and_events(client):
    """GET /catalog/<name> returns 200 with the registration and its
    related events."""
    _register(client, name="detail-svc", owner="team-detail")
    resp = client.get("/catalog/detail-svc")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "detail-svc" in body
    assert "team-detail" in body
    assert "Service registered" in body  # related event via shared partial


def test_catalog_detail_404_when_absent(client):
    """GET /catalog/<absent> returns 404."""
    resp = client.get("/catalog/does-not-exist")
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Deregister confirm + POST (CAT-05, D-08)                                    #
# --------------------------------------------------------------------------- #


def test_catalog_delete_confirm_renders(client):
    """GET /catalog/<name>/delete returns 200 rendering the confirm page."""
    _register(client, name="delete-me")
    resp = client.get("/catalog/delete-me/delete")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Deregister delete-me?" in body
    assert 'method="post"' in body


def test_catalog_delete_confirm_404_when_absent(client):
    """GET /catalog/<absent>/delete returns 404."""
    resp = client.get("/catalog/does-not-exist/delete")
    assert resp.status_code == 404


def test_catalog_delete_post_removes_and_redirects(client, monkeypatch):
    """POST /catalog/<name>/delete calls catalog.deregister_service, fires
    service_deregistered via events.record_event, and redirects (302) to
    /catalog."""
    import app.events as events_module

    _register(client, name="to-remove")

    calls = []
    monkeypatch.setattr(
        events_module,
        "record_event",
        lambda event_type, service_name: calls.append((event_type, service_name)) or True,
    )

    resp = client.post("/catalog/to-remove/delete")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/catalog"
    assert ("service_deregistered", "to-remove") in calls

    # document actually removed
    body = client.get("/catalog").get_data(as_text=True)
    assert "to-remove" not in body


# --------------------------------------------------------------------------- #
# CSRF protection is live (CAT-03, T-09-06)                                   #
# --------------------------------------------------------------------------- #


def test_onboard_form_rejects_missing_csrf_token(app):
    """WTF_CSRF_ENABLED=True (overriding the test-default False): a missing
    or invalid csrf_token on POST /catalog/new returns 400; a token scraped
    from a prior GET does NOT return 400."""
    app.config["WTF_CSRF_ENABLED"] = True
    client = app.test_client()

    get_resp = client.get("/catalog/new")
    match = re.search(r'name="csrf_token" type="hidden" value="([^"]+)"', get_resp.text)
    token = match.group(1)

    bad_resp = client.post("/catalog/new", data={"name": "svc", "csrf_token": "invalid"})
    assert bad_resp.status_code == 400

    good_resp = client.post(
        "/catalog/new",
        data={
            "name": "svc-a",
            "repo_url": "https://github.com/org/repo",
            "owner": "team",
            "environment": "dev",
            "csrf_token": token,
        },
    )
    assert good_resp.status_code != 400
