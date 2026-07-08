"""
app.k8s.get_k8s_clients() — both branches of the D-05 contract, exercised
without a real cluster or kubeconfig.
"""


def test_get_k8s_clients_returns_none_none_with_no_config(monkeypatch, tmp_path):
    """No KUBERNETES_SERVICE_HOST and no kubeconfig file => (None, None), no raise."""
    from app.k8s import get_k8s_clients

    monkeypatch.delenv("KUBERNETES_SERVICE_HOST", raising=False)
    monkeypatch.delenv("KUBERNETES_SERVICE_PORT", raising=False)
    monkeypatch.delenv("KUBECONFIG", raising=False)
    # Point HOME at an empty tmp_path so ~/.kube/config resolves to nothing —
    # hermetic regardless of a real kubeconfig on the dev/CI machine (RESEARCH Pitfall 2).
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))  # Windows kubeconfig lookup

    core_v1, apps_v1 = get_k8s_clients()

    assert core_v1 is None
    assert apps_v1 is None


def test_get_k8s_clients_returns_apis_when_incluster_config_present(monkeypatch):
    """Mock config.load_incluster_config to succeed => real API client types returned."""
    from unittest.mock import MagicMock

    import app.k8s as k8s_module

    monkeypatch.setattr(k8s_module.config, "load_incluster_config", MagicMock())

    core_v1, apps_v1 = k8s_module.get_k8s_clients()

    assert core_v1 is not None
    assert apps_v1 is not None


def test_get_k8s_clients_falls_back_to_kube_config(monkeypatch):
    """In-cluster config raises ConfigException => falls back to load_kube_config()."""
    from unittest.mock import MagicMock

    import app.k8s as k8s_module
    from kubernetes.config import ConfigException

    monkeypatch.setattr(
        k8s_module.config,
        "load_incluster_config",
        MagicMock(side_effect=ConfigException("no in-cluster config")),
    )
    monkeypatch.setattr(k8s_module.config, "load_kube_config", MagicMock())

    core_v1, apps_v1 = k8s_module.get_k8s_clients()

    assert core_v1 is not None
    assert apps_v1 is not None


def test_k8s_disabled_fixture(k8s_disabled):
    """k8s_disabled fixture forces get_k8s_clients() to (None, None)."""
    assert k8s_disabled.get_k8s_clients() == (None, None)


def test_k8s_enabled_fixture(k8s_enabled):
    """k8s_enabled fixture forces get_k8s_clients() to return mocked API clients."""
    import app.k8s as k8s_module

    core_v1, apps_v1 = k8s_module.get_k8s_clients()
    assert core_v1 is k8s_enabled[0]
    assert apps_v1 is k8s_enabled[1]
