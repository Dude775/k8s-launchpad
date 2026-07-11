"""
get_cluster_state() branch tests (DIAG-02).

Covers all four branches of the aggregation helper: outside-cluster,
success (including a container_statuses=None coalesce case), 403 (RBAC
missing), and unreachable (timeout / non-403 ApiException) — none of these
may ever raise past get_cluster_state(). Reuses the k8s_disabled/k8s_enabled
fixtures from conftest.py, which only reach cluster_state.py because it
accesses the K8s client accessor via module attribute (from app import k8s
-> k8s.get_k8s_clients()), not a from-import (plan-check BLOCKER 3).
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import urllib3
from kubernetes.client.exceptions import ApiException

from app.cluster_state import _pod_age, get_cluster_state


def test_pod_age_none_timestamp_returns_unknown():
    assert _pod_age(None) == "unknown"


def test_pod_age_minutes_only():
    ts = datetime.now(timezone.utc) - timedelta(minutes=5)
    assert _pod_age(ts) == "5m"


def test_pod_age_hours():
    ts = datetime.now(timezone.utc) - timedelta(hours=3, minutes=10)
    assert _pod_age(ts) == "3h"


def test_pod_age_days():
    ts = datetime.now(timezone.utc) - timedelta(days=2, hours=5)
    assert _pod_age(ts) == "2d"


def test_pod_age_future_timestamp_clamps_to_zero():
    """A creation_timestamp in the future (clock skew) clamps the negative
    delta to 0 seconds -> "0m", never a negative age."""
    ts = datetime.now(timezone.utc) + timedelta(minutes=5)
    assert _pod_age(ts) == "0m"


def test_pod_age_malformed_timestamp_returns_unknown():
    """A non-datetime creation_timestamp (e.g. a plain string) raises inside
    the arithmetic -> caught, falls back to "unknown" (never raises)."""
    assert _pod_age("not-a-datetime") == "unknown"


def test_outside_cluster_returns_available_false(k8s_disabled):
    """(None, None) from get_k8s_clients() -> {"available": False}, not an
    error state (D-03)."""
    assert get_cluster_state() == {"available": False}


def test_success_maps_pods_and_deployments(k8s_enabled, monkeypatch):
    """Cluster reachable, list calls succeed -> mapped pods/deployments,
    both list calls scoped to POD_NAMESPACE with _request_timeout=5."""
    monkeypatch.setenv("POD_NAMESPACE", "launchpad")
    core_v1, apps_v1 = k8s_enabled

    fake_pod = SimpleNamespace(
        metadata=SimpleNamespace(name="launchpad-abc", creation_timestamp=datetime.now(timezone.utc)),
        status=SimpleNamespace(
            phase="Running",
            container_statuses=[SimpleNamespace(ready=True, restart_count=0)],
        ),
    )
    core_v1.list_namespaced_pod.return_value = SimpleNamespace(items=[fake_pod])

    fake_dep = SimpleNamespace(
        metadata=SimpleNamespace(name="launchpad"),
        spec=SimpleNamespace(replicas=1),
        status=SimpleNamespace(ready_replicas=0, updated_replicas=1, available_replicas=0),
    )
    apps_v1.list_namespaced_deployment.return_value = SimpleNamespace(items=[fake_dep])

    result = get_cluster_state()

    assert result["available"] is True
    assert result["pods"] == [
        {
            "name": "launchpad-abc",
            "phase": "Running",
            "ready": "1/1",
            "restarts": 0,
            "age": "0m",
        }
    ]
    assert result["deployments"] == [
        {
            "name": "launchpad",
            "ready": "0/1",
            "up_to_date": 1,
            "available": 0,
        }
    ]
    core_v1.list_namespaced_pod.assert_called_once_with("launchpad", _request_timeout=5)
    apps_v1.list_namespaced_deployment.assert_called_once_with("launchpad", _request_timeout=5)


def test_success_pod_with_no_container_statuses_coalesces(k8s_enabled, monkeypatch):
    """A pod with container_statuses=None coalesces via `or []` -> ready
    "0/0", restarts 0 (no crash)."""
    monkeypatch.setenv("POD_NAMESPACE", "launchpad")
    core_v1, apps_v1 = k8s_enabled

    fake_pod = SimpleNamespace(
        metadata=SimpleNamespace(name="launchpad-xyz", creation_timestamp=None),
        status=SimpleNamespace(phase="Pending", container_statuses=None),
    )
    core_v1.list_namespaced_pod.return_value = SimpleNamespace(items=[fake_pod])
    apps_v1.list_namespaced_deployment.return_value = SimpleNamespace(items=[])

    result = get_cluster_state()

    assert result["pods"] == [
        {
            "name": "launchpad-xyz",
            "phase": "Pending",
            "ready": "0/0",
            "restarts": 0,
            "age": "unknown",
        }
    ]
    assert result["deployments"] == []


def test_forbidden_403_returns_distinct_error(k8s_enabled):
    """A 403 ApiException -> {"available": True, "error": "forbidden"},
    distinct from outside-cluster (must never be conflated — Pitfall 1)."""
    core_v1, _apps_v1 = k8s_enabled
    core_v1.list_namespaced_pod.side_effect = ApiException(status=403, reason="Forbidden")

    assert get_cluster_state() == {"available": True, "error": "forbidden"}


def test_non_403_api_exception_returns_unreachable(k8s_enabled):
    """A non-403 ApiException (e.g. 500) -> unreachable, not forbidden."""
    core_v1, _apps_v1 = k8s_enabled
    core_v1.list_namespaced_pod.side_effect = ApiException(status=500, reason="Server Error")

    assert get_cluster_state() == {"available": True, "error": "unreachable"}


def test_max_retry_error_returns_unreachable(k8s_enabled):
    """A urllib3.exceptions.HTTPError (timeout / MaxRetryError) never
    propagates -> unreachable, never a 500 (Pitfall 2)."""
    core_v1, _apps_v1 = k8s_enabled
    core_v1.list_namespaced_pod.side_effect = urllib3.exceptions.MaxRetryError(pool=None, url="/api")

    assert get_cluster_state() == {"available": True, "error": "unreachable"}


def test_cluster_state_no_list_namespaced_call_missing_timeout():
    """Grep gate companion: every list_namespaced_* call in cluster_state.py
    passes _request_timeout= (ignores comment lines) — SC #5 enforcement."""
    import inspect

    import app.cluster_state as cluster_state_module

    source = inspect.getsource(cluster_state_module)
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "list_namespaced_" in stripped and "def " not in stripped:
            assert "_request_timeout=" in stripped
