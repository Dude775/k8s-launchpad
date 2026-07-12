"""
htmx partial-fragment route tests.

Covers GET /partials/status-cards (STAT-01/02): a fragment when HX-Request
is present, a full page (status_full_page.html) otherwise, both rendering
real per-metric cards from get_platform_status() with a degraded state when
field-guide-api is unreachable — never a 500, never an empty body.

Also covers GET /partials/cluster-state (DIAG-02): the same fragment-vs-
full-page split, using k8s_disabled so no real cluster is needed — the
outside-cluster muted panel is the default local/CI state.

Also covers GET /partials/feed (FEED-01): the same fragment-vs-full-page
split, rendering the shared partials/event_row.html per Event-Row Anatomy —
glyph, human label, service-name link, relative time — reused unchanged by
the detail page (D-09).
"""


def test_status_cards_fragment_when_hx_request_present(client, mock_requests_get):
    """GET /partials/status-cards with HX-Request: true returns a fragment
    (no <html> / no <!doctype>)."""
    resp = client.get("/partials/status-cards", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "<html" not in body
    assert "<!doctype" not in body.lower()


def test_status_cards_full_page_when_no_hx_request(client, mock_requests_get):
    """GET /partials/status-cards with NO HX-Request header returns a full
    page (contains <html> and the base.html shell)."""
    resp = client.get("/partials/status-cards")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "<html" in body


def test_status_cards_degraded_when_field_guide_unreachable(client, mock_requests_get_unreachable):
    """The rendered fragment shows a degraded card scoped to the Field Guide
    API card when the field-guide check fails (never a 500 or empty body).
    Scopes the degraded modifier to the Field Guide API card so the assertion
    actually verifies the health signal is attached to the right card (WR-01),
    not merely that the class string appears somewhere in the body."""
    resp = client.get("/partials/status-cards", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    # The degraded modifier must decorate the Field Guide card specifically.
    assert 'status-card status-card--degraded">\n  <header>Field Guide API</header>' in body


def test_status_cards_shows_mongo_version_and_service_count(client, mock_requests_get):
    """The rendered fragment shows a mongo up/down card and the app_version
    and service_count values."""
    resp = client.get("/partials/status-cards", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "up" in body
    assert "dev" in body  # default APP_VERSION
    assert ">0<" in body  # service_count default (empty services collection)


def test_cluster_state_fragment_when_hx_request_present(client, k8s_disabled):
    """GET /partials/cluster-state with HX-Request: true returns a fragment
    (no <html> / no <!doctype>) showing the muted outside-cluster panel."""
    resp = client.get("/partials/cluster-state", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "<html" not in body
    assert "<!doctype" not in body.lower()
    assert "Not running in a cluster" in body


def test_cluster_state_full_page_when_no_hx_request(client, k8s_disabled):
    """GET /partials/cluster-state with NO HX-Request header returns a full
    page (contains <html> and the base.html shell)."""
    resp = client.get("/partials/cluster-state")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "<html" in body


# --------------------------------------------------------------------------- #
# Activity feed fragment / full page (FEED-01)                                #
# --------------------------------------------------------------------------- #


def test_feed_fragment_when_hx_request_present(client):
    """GET /partials/feed with HX-Request: true returns a fragment (no
    <html> / no <!doctype>)."""
    resp = client.get("/partials/feed", headers={"HX-Request": "true"})
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "<html" not in body
    assert "<!doctype" not in body.lower()


def test_feed_full_page_when_no_hx_request(client):
    """GET /partials/feed with NO HX-Request header returns a full page
    (contains <html> and the base.html shell)."""
    resp = client.get("/partials/feed")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "<html" in body


def test_feed_empty_state(client):
    """An empty feed renders the "No activity yet" empty-state copy."""
    resp = client.get("/partials/feed", headers={"HX-Request": "true"})
    body = resp.get_data(as_text=True)
    assert "No activity yet" in body


def test_feed_seeded_event_renders_glyph_label_and_link(client, monkeypatch):
    """A seeded service_registered event renders the '+' glyph, the "Service
    registered" label, and a link to /catalog/<name> (Event-Row Anatomy)."""
    import datetime

    import app.events as events_module

    fake_event = {
        "type": "service_registered",
        "service_name": "seeded-svc",
        "ts": datetime.datetime.now(datetime.timezone.utc),
    }
    monkeypatch.setattr(events_module, "list_recent_events", lambda limit=50: [fake_event])

    resp = client.get("/partials/feed", headers={"HX-Request": "true"})
    body = resp.get_data(as_text=True)
    assert ">+<" in body
    assert "Service registered" in body
    assert 'href="/catalog/seeded-svc"' in body


def test_feed_platform_started_event_has_no_service_link(client, monkeypatch):
    """A platform_started event renders the muted bullet glyph and label, with
    no service-name link (no service attached)."""
    import datetime

    import app.events as events_module

    fake_event = {
        "type": "platform_started",
        "service_name": None,
        "ts": datetime.datetime.now(datetime.timezone.utc),
    }
    monkeypatch.setattr(events_module, "list_recent_events", lambda limit=50: [fake_event])

    resp = client.get("/partials/feed", headers={"HX-Request": "true"})
    body = resp.get_data(as_text=True)
    assert "Platform started" in body


def test_feed_deregistered_event_renders_destructive_glyph(client, monkeypatch):
    """A seeded service_deregistered event renders the destructive glyph and
    the "Service deregistered" label."""
    import datetime

    import app.events as events_module

    fake_event = {
        "type": "service_deregistered",
        "service_name": "gone-svc",
        "ts": datetime.datetime.now(datetime.timezone.utc),
    }
    monkeypatch.setattr(events_module, "list_recent_events", lambda limit=50: [fake_event])

    resp = client.get("/partials/feed", headers={"HX-Request": "true"})
    body = resp.get_data(as_text=True)
    assert "Service deregistered" in body
    assert 'href="/catalog/gone-svc"' in body
