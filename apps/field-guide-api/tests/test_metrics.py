"""
Prometheus metrics endpoint test.

GET /metrics  200  Prometheus text format

The endpoint is registered by prometheus-flask-exporter in create_app().
We verify reachability and that the response contains Prometheus-format
markers — either a `# HELP`/`# TYPE` comment line or the well-known
`python_info` metric that the client always emits.
"""

import pytest


def test_metrics_endpoint(client):
    """GET /metrics returns 200 with Prometheus text-format content."""
    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.data
    # Prometheus text exposition format always starts with comment lines
    # beginning with '# HELP' or '# TYPE', or includes standard python_info.
    assert b"# HELP" in body or b"# TYPE" in body or b"python_info" in body
