"""
Prometheus /metrics parity verification (STAT-04).

/metrics needs NO new wiring — prometheus-flask-exporter has registered it
since Phase 5. This test locks in parity with field-guide-api's /metrics by
asserting the same default HTTP request count and duration metric families
are present, and that the response is valid Prometheus text.
"""


def test_metrics_endpoint_returns_200_prometheus_text(client):
    """GET /metrics returns 200 with a Prometheus text/plain content type."""
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.content_type


def test_metrics_contains_field_guide_api_parity_families(client):
    """The /metrics body contains flask_http_request_total and
    flask_http_request_duration_seconds — the same default metric families
    field-guide-api exposes, confirming parity."""
    resp = client.get("/metrics")
    body = resp.get_data(as_text=True)
    assert "flask_http_request_total" in body
    assert "flask_http_request_duration_seconds" in body
