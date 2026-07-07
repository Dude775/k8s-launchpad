# Known Limitations

PRD-1 is the foundation milestone. Several capabilities are intentionally deferred to later PRDs.
This page lists what is out of scope now, why, and which future milestone picks it up.

## Out of Scope for PRD-1

### No GitOps / ArgoCD (PRD-2)
The `infra/argocd/` directory exists as a seam but is empty. Helm releases are managed manually
via `make deploy`. ArgoCD continuous reconciliation is planned for PRD-2.

### No Platform Dashboard or Repo Onboarding (PRD-3)
There is no web UI for registering Git repos or viewing deployment status. The Helm chart's
`values.yaml` is structured generically so PRD-3 can template new apps from it, but the
onboarding layer itself does not exist yet.

### No Prometheus / Grafana / Loki / Trivy (PRD-4)
The field-guide API exposes `/metrics` in Prometheus format as a scrape seam. Deploying
Prometheus, Grafana, Loki, or running Trivy vulnerability scans is deferred to PRD-4.

### Port-Forward Only — No Ingress or TLS
The API is reachable exclusively via `kubectl port-forward svc/field-guide-api 8080:80` on
`localhost`. No Ingress controller, no TLS, no NodePort. For a local kind cluster this is
sufficient; Ingress/TLS is over-engineering for the foundation milestone.

### kind Cluster is Ephemeral — Data Lost on Teardown
The MongoDB PVC uses kind's default hostPath StorageClass. Running `make cluster-down` or
`make reset-local` destroys the kind cluster and with it all MongoDB data. This is expected
for a local dev cluster; persistence hardening is out of scope for PRD-1.

### Committed Dev Password (`fieldguide-dev-password`)
The Helm chart ships with a committed local-dev MongoDB password. `helm install` prints a
warning at deploy time:

```
!! WARNING: MongoDB is running with the COMMITTED local-dev password.
!! This is acceptable ONLY on a local kind cluster.
```

This is intentional for frictionless local setup. Override it for anything beyond localhost:

```bash
helm upgrade field-guide-api charts/field-guide-api --set mongodb.auth.password=<real-password>
```

### Cosmetic gunicorn `/home/app` Warning in Startup Logs
gunicorn logs a permission warning at startup because the non-root user (`UID 10001`) has no
writable home directory. This warning is **harmless** — gunicorn serves traffic normally
throughout. The optional fix (`HOME=/tmp` env var or `--worker-tmp-dir`) is deferred and is
not a Phase 4 Dockerfile edit; the container is stable as-is.

### No RBAC or NetworkPolicies
The kind cluster runs without custom RBAC or NetworkPolicies. These are over-engineering for
a single-user local cluster; they will be relevant when the platform moves to a shared
environment in later PRDs.

### No AWS / EKS / Terraform
This milestone is entirely local and free. Cloud deployment (AWS/EKS/Terraform) is deferred
to the final PRD.

## See Also

- [docs/troubleshooting.md](troubleshooting.md) — symptom → cause → fix for common failures
- [README.md](../README.md) — quickstart and architecture overview
