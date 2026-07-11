"""
Read-only Kubernetes cluster-state aggregation helper.

get_cluster_state() is the SINGLE source of truth consumed by
GET /partials/cluster-state (app/routes/partials.py). It is a bare helper
(NO Blueprint) mirroring app/status.py's shape: a single exported function
that never raises, degrading to safe sentinel values on any failure.

CRITICAL (plan-check BLOCKER 3): this module imports `app.k8s` as a MODULE
and calls the accessor via that module attribute — it does NOT import the
accessor function by name directly into this namespace. tests/conftest.py's
k8s_disabled and k8s_enabled fixtures monkeypatch app.k8s.get_k8s_clients
directly; a direct-name import would bind the original function into this
module's namespace at import time (during create_app), so the later
monkeypatch would never reach it and the mocked-branch tests would fail
deterministically. This mirrors status.py's `import requests` ->
`requests.get(...)` idiom.
"""

import os
from datetime import datetime, timezone

import urllib3
from kubernetes.client.exceptions import ApiException

from app import k8s

# Mandatory timeout for every K8s list call (SC #5): with a single gunicorn
# worker, an unbounded API call can hang the entire pod. Never call
# list_namespaced_* without this timeout.
K8S_REQUEST_TIMEOUT_SECONDS = 5


def _pod_age(creation_timestamp) -> str:
    """Render a short age string from a tz-aware creation_timestamp.

    Never raises — falls back to "unknown" if the timestamp is missing or
    malformed.
    """
    if creation_timestamp is None:
        return "unknown"
    try:
        delta = datetime.now(timezone.utc) - creation_timestamp
        seconds = int(delta.total_seconds())
        if seconds < 0:
            seconds = 0
        days, remainder = divmod(seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, _ = divmod(remainder, 60)
        if days > 0:
            return f"{days}d"
        if hours > 0:
            return f"{hours}h"
        return f"{minutes}m"
    except Exception:
        return "unknown"


def _map_pod(pod) -> dict:
    """Map a V1Pod into the pods-table row shape (RESEARCH §Cluster State
    Table Data Shapes, VERIFIED against kubernetes==36.0.2 model files)."""
    container_statuses = pod.status.container_statuses or []
    ready_count = sum(1 for c in container_statuses if c.ready)
    total_count = len(container_statuses)
    restarts = sum(c.restart_count for c in container_statuses)
    return {
        "name": pod.metadata.name,
        "phase": pod.status.phase,
        "ready": f"{ready_count}/{total_count}",
        "restarts": restarts,
        "age": _pod_age(pod.metadata.creation_timestamp),
    }


def _map_deployment(dep) -> dict:
    """Map a V1Deployment into the deployments-table row shape."""
    return {
        "name": dep.metadata.name,
        "ready": f"{dep.status.ready_replicas or 0}/{dep.spec.replicas or 0}",
        "up_to_date": dep.status.updated_replicas or 0,
        "available": dep.status.available_replicas or 0,
    }


def get_cluster_state() -> dict:
    """Read pods/deployments in the launchpad namespace via the in-cluster
    ServiceAccount, degrading cleanly across three distinct failure states.

    Never raises. Return shapes:
      outside cluster:  {"available": False}
      403 (RBAC):       {"available": True, "error": "forbidden"}
      timeout/other:    {"available": True, "error": "unreachable"}
      success:          {"available": True, "pods": [...], "deployments": [...]}

    Exception detail is always discarded — never str(exception) — so no
    hostname, stack trace, or API server detail leaks into the returned
    dict (T-07-07 discipline, mirrored from status.py).
    """
    core_v1, apps_v1 = k8s.get_k8s_clients()
    if core_v1 is None:
        return {"available": False}

    namespace = os.environ.get("POD_NAMESPACE", "default")

    try:
        pod_list = core_v1.list_namespaced_pod(namespace, _request_timeout=K8S_REQUEST_TIMEOUT_SECONDS)
        deployment_list = apps_v1.list_namespaced_deployment(namespace, _request_timeout=K8S_REQUEST_TIMEOUT_SECONDS)
    except ApiException as exc:
        if exc.status == 403:
            return {"available": True, "error": "forbidden"}
        return {"available": True, "error": "unreachable"}
    except urllib3.exceptions.HTTPError:
        return {"available": True, "error": "unreachable"}

    pods = [_map_pod(pod) for pod in pod_list.items]
    deployments = [_map_deployment(dep) for dep in deployment_list.items]
    return {"available": True, "pods": pods, "deployments": deployments}
