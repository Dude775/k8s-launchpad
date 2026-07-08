"""
Test fixtures providing an isolated Flask test app with a mocked K8s client.

No real cluster or kubeconfig is used in any test. The K8s client is mocked
by monkeypatching app.k8s.get_k8s_clients directly (module-level function
replacement), the same monkeypatch-and-auto-restore discipline field-guide-api
uses for its mongomock injection.
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def app():
    """Isolated Flask test app — no cluster, no Mongo required for Phase 5."""
    from app import create_app

    application = create_app({"TESTING": True})
    yield application


@pytest.fixture
def client(app):
    """Flask test client using the isolated app."""
    return app.test_client()


@pytest.fixture
def k8s_disabled(monkeypatch):
    """Force app.k8s.get_k8s_clients() to return the disabled (None, None) state.

    This is the DEFAULT / expected state for local dev and CI (D-05, D-07) —
    it is a first-class tested path, not an error path.
    """
    import app.k8s as k8s_module

    monkeypatch.setattr(k8s_module, "get_k8s_clients", lambda: (None, None))
    return k8s_module


@pytest.fixture
def k8s_enabled(monkeypatch):
    """Force app.k8s.get_k8s_clients() to return mocked (CoreV1Api, AppsV1Api)
    instances, exercising the "cluster reachable" branch without a real cluster.
    """
    import app.k8s as k8s_module

    fake_core_v1 = MagicMock(name="CoreV1Api")
    fake_apps_v1 = MagicMock(name="AppsV1Api")
    monkeypatch.setattr(k8s_module, "get_k8s_clients", lambda: (fake_core_v1, fake_apps_v1))
    return fake_core_v1, fake_apps_v1


@pytest.fixture
def mock_requests_get(monkeypatch):
    """Placeholder pattern for mocking `requests.get` ahead of Phase 7's
    field-guide-api reachability check (STAT-02). No Phase 5 route calls
    `requests` yet — this fixture exists so the conftest module already
    demonstrates the mocking shape D-02 asks for, ready for Phase 7 to use.
    """
    import requests

    fake_response = MagicMock(status_code=200, json=lambda: {})
    monkeypatch.setattr(requests, "get", lambda *a, **kw: fake_response)
    return fake_response
