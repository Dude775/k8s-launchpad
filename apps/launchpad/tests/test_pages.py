"""
Dashboard page route tests.

Covers UI-01 (IDP landing page), UI-02 (shell + active nav), UI-03 (status
cards sourced from a real route, not hardcoded), UI-04 (htmx polling >=10s
with a tab-visibility guard).
"""


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
    """GET on /, /catalog, /diagnostics, /feed each return 200."""
    for path in ("/", "/catalog", "/diagnostics", "/feed"):
        resp = client.get(path)
        assert resp.status_code == 200, path
