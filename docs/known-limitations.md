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

### Committed Dev Password (`fieldguide-dev-password`, `launchpad-dev-password`)
The Helm chart ships with a committed local-dev MongoDB password. `helm install` prints a
warning at deploy time:

```
!! WARNING: MongoDB is running with the COMMITTED local-dev password.
!! This is acceptable ONLY on a local kind cluster.
```

This is intentional for frictionless local setup. The `charts/launchpad` chart carries the same
committed-password discipline (`charts/launchpad/values.yaml:56`, `launchpad-dev-password`).
Override it for anything beyond localhost:

```bash
helm upgrade field-guide-api charts/field-guide-api --set mongodb.auth.password=<real-password>
helm upgrade launchpad charts/launchpad --set mongodb.auth.password=<real-password>
```

### WR-01 — Committed Local-Dev `mongoUri` Defaults (launchpad)
The launchpad chart's `mongoUri` (`charts/launchpad/values.yaml:72`) embeds a local-dev
hostname **and** the committed credential above as a single committed default:

```
mongodb://root:launchpad-dev-password@launchpad-mongodb:27017/launchpad?authSource=admin&serverSelectionTimeoutMS=2000
```

This is an accepted local-dev limitation, not a production secret — the hostname
(`launchpad-mongodb`) only resolves inside the cluster's own namespace, and the password is the
same committed local-dev value documented above. Keep `mongoUri` and
`mongodb.auth.password` in sync when overriding for any non-local use:

```bash
helm upgrade launchpad charts/launchpad --set mongoUri=<real-uri>
```

(Flagged in Phase 9 review/verification as WR-01; genuinely open — tracked here rather than
fixed in-chart because PRD-1/v1.1 scope is local-only.)

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

### Events TTL Expiry Verified Live Only (not unit tests)
The launchpad activity feed's events collection is TTL-bounded (`EVENTS_TTL_SECONDS`), but
actual expiry behavior is MongoDB server-side background work — not something a unit test can
exercise meaningfully. Verification is live-only, via `make verify-ttl`:

```
==> Verifying events TTL index...
  PASS  events.ts TTL index present
```

The default mode asserts the `expireAfterSeconds` index exists (deterministic, fast). Run with
`TTL_DEEP=1` for a real insert-and-wait round-trip: it inserts a probe event whose `ts` is
backdated past the index's actual `expireAfterSeconds` (read live from the index, so it tracks
any TTL override), then polls until MongoDB's TTL monitor — which runs roughly every 60 seconds —
deletes the already-expired probe (slow, ~60-90s). This closes the Phase 9 FEED-03 "verify live"
flag. Because the probe is backdated, it sorts to the bottom of the activity feed and is removed
on the monitor's next pass even if a run is interrupted.

## See Also

- [docs/troubleshooting.md](troubleshooting.md) — symptom → cause → fix for common failures
- [README.md](../README.md) — quickstart and architecture overview
