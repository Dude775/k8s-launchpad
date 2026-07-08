"""
Lazy Kubernetes client accessor.

get_k8s_clients() is the ONLY entry point. It is never called at import time
or inside create_app() — callers (Phase 8 diagnostics routes) invoke it
per-request. With no cluster config reachable it returns (None, None) and
raises nothing; callers check for None to detect the disabled state (D-05).

Both loaders below raise the SAME exception type when their respective
config source is absent — kubernetes.config.config_exception.ConfigException,
a plain Exception subclass — confirmed by reading the current kubernetes-client/
python master branch source (incluster_config.py raises ConfigException when
KUBERNETES_SERVICE_HOST/PORT env vars are unset or the service-account token/
cert files are missing; kube_config.py raises the same ConfigException when
the kubeconfig file does not exist at the resolved path). Catching only
ConfigException — not a bare `except Exception` — keeps this narrow and
avoids masking real bugs (e.g. a TypeError from a future refactor).
"""

from kubernetes import client, config
from kubernetes.config import ConfigException


def get_k8s_clients():
    """Return (CoreV1Api, AppsV1Api) if a cluster is reachable, else (None, None).

    Fallback order (D-05, locked): in-cluster config first, then local
    kubeconfig. This is the correct order for a service that should trust its
    own ServiceAccount identity when actually running as a pod — the
    opposite of kubernetes.config.load_config()'s convenience-wrapper order
    (kubeconfig first), which is meant for CLI tooling, not services.

    No caching (D-06) — a plain function is enough for the Phase 5 skeleton.
    """
    try:
        config.load_incluster_config()
    except ConfigException:
        pass
    else:
        return client.CoreV1Api(), client.AppsV1Api()

    try:
        config.load_kube_config()
    except ConfigException:
        pass
    else:
        return client.CoreV1Api(), client.AppsV1Api()

    return None, None
