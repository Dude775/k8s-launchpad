"""
htmx partial-fragment route tests.

Covers the degraded-state contract for GET /partials/status-cards (UI-03/UI-04):
always 200, never a full page, never a 500, even before Phase 7 wires real data.
"""


def test_status_cards_degraded_when_no_data(client):
    """GET /partials/status-cards always returns 200 with the unknown/degraded
    empty-state fragment in Phase 6 — no data source exists yet (never 500)."""
    resp = client.get("/partials/status-cards")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Status unavailable" in body
    assert "<html" not in body  # fragment only, never a full page (RESEARCH Pitfall 3)
