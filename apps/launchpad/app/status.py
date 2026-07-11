"""
Platform status aggregation helper.

get_platform_status() is the SINGLE source of truth consumed by both
GET /api/status (JSON) and GET /partials/status-cards (HTML fragment/full
page) — see app/routes/status.py and app/routes/partials.py. This keeps the
JSON contract and the dashboard's rendered cards from ever silently drifting.

This module is a bare helper (NO Blueprint) — mirrors app/k8s.py's shape: a
single exported function that never raises, degrading to safe sentinel
values on any sub-check failure.

CRITICAL (RESEARCH Pitfall 1): app/routes/health.py must NEVER import this
module or reach across the cluster to field-guide-api — this module is the
ONLY place that outbound cross-service call is allowed to happen.
"""

import requests
from flask import current_app
from prometheus_client import REGISTRY

from app.extensions import mongo

# Mandatory timeout for every outbound call to field-guide-api (RESEARCH
# Pitfall 2 / T-07-06): with a single gunicorn worker, an unbounded
# requests.get() can hang the entire pod, including its own /health and
# /metrics traffic. Never call requests.get() without this timeout.
FIELD_GUIDE_TIMEOUT_SECONDS = 2


def _metrics_preview() -> dict:
    """Sum the flask_http_request_total counter from the SAME Prometheus
    registry that backs /metrics (prometheus_client.REGISTRY — the default
    registry prometheus-flask-exporter uses; no second registry is created).

    Never raises — falls back to {"http_requests_total": 0} if the registry
    read fails for any reason (RESEARCH Pattern 2 exception-isolation style).
    """
    try:
        total = 0
        for family in REGISTRY.collect():
            if family.name != "flask_http_request":
                continue
            for sample in family.samples:
                if sample.name == "flask_http_request_total":
                    total += sample.value
        return {"http_requests_total": int(total)}
    except Exception:
        return {"http_requests_total": 0}


def get_platform_status() -> dict:
    """Aggregate platform status for /api/status and the status-cards fragment.

    Every sub-check is independently exception-isolated — this function
    NEVER raises. Contrast with /health (app/routes/health.py), which checks
    ONLY launchpad's own MongoDB and is the Kubernetes readinessProbe target;
    this function additionally reaches across the cluster network to
    field-guide-api and must degrade gracefully when it is unreachable.

    Returns a dict with exactly six keys: api_health, mongo_status,
    app_version, service_count, field_guide_reachable, metrics_preview.
    Exception detail is always discarded — never str(exception) — so no
    hostname, stack trace, or connection-string fragment leaks into the
    JSON or HTML representations (T-07-07).
    """
    mongo_status = "down"
    try:
        mongo.cx.admin.command("ping")
        mongo_status = "up"
    except Exception:
        pass

    field_guide_reachable = False
    base_url = current_app.config["FIELD_GUIDE_BASE_URL"]
    try:
        resp = requests.get(f"{base_url}/health", timeout=FIELD_GUIDE_TIMEOUT_SECONDS)
        field_guide_reachable = resp.status_code == 200
    except requests.exceptions.RequestException:
        field_guide_reachable = False

    service_count = 0
    try:
        # Not hardcoded (RESEARCH Pitfall 4) — returns 0 today because the
        # services collection is empty; Phase 9 populates it. No schema,
        # seed data, or registration logic belongs in this phase.
        service_count = mongo.db.services.count_documents({})
    except Exception:
        service_count = 0

    return {
        "api_health": "ok" if mongo_status == "up" else "degraded",
        "mongo_status": mongo_status,
        "app_version": current_app.config["APP_VERSION"],
        "service_count": service_count,
        "field_guide_reachable": field_guide_reachable,
        "metrics_preview": _metrics_preview(),
    }
