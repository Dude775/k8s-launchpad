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

### Loki / Trivy / Alertmanager Remain Deferred (PRD-4)
As of Phase 11 (v2.0), Prometheus, Grafana, and kube-state-metrics are installed via
`infra/observability/` (a trimmed `kube-prometheus-stack` release in the `observability`
namespace) — the field-guide API's `/metrics` scrape seam is now actually scraped. Loki
(log aggregation), Trivy (vulnerability scanning), and Alertmanager (notification rules)
remain deferred; they are tracked in REQUIREMENTS.md Future Requirements.

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

### Committed Grafana Admin Password (`grafana-dev-password`)
The observability stack ships with a committed local-dev Grafana admin password,
`grafana-dev-password`, set in `infra/observability/values-trimmed.yaml`. This is a local
kind-cluster convenience value — never a real credential — and follows the same
committed-dev-password discipline as the MongoDB password documented above. Override it for
anything beyond localhost:

```bash
helm upgrade kube-prometheus-stack prometheus-community/kube-prometheus-stack -n observability \
  --reuse-values --set grafana.adminPassword=<real-password>
```

### CRD Teardown Leaves `monitoring.coreos.com` CRDs Installed
`make observability-down` / `scripts/observability-down.sh` runs `helm uninstall` only. By
Helm's documented `crds/` directory behavior, `helm uninstall` never removes CRDs it installed —
so the `monitoring.coreos.com` CustomResourceDefinitions (Prometheus, ServiceMonitor, etc.)
remain on the cluster after teardown. This is intentional (D-01): it makes re-running
`observability-up` faster and carries zero cascade-delete risk to Phase 12's ServiceMonitors,
which depend on those CRDs existing. If a full reset is ever wanted, the CRDs can be removed
manually:

```bash
kubectl delete crd -l app.kubernetes.io/part-of=kube-prometheus-stack
```

### Measured observability headroom: live Phase 11 install (2026-07-16)
First live-measured resource-headroom number, captured from `scripts/observability-up.sh`'s
Step 0 preflight check on a freshly-provisioned kind cluster (control-plane node, before the
observability stack existed) with both v1.1 apps (`field-guide-api`, `launchpad`) already
deployed via `make up-all`:

```
Allocatable: 10184928Ki (~9.71 GiB) | Already requested: 559104Ki (~546 MiB) | Headroom: 9625824Ki (~9.18 GiB) | Stack needs: 528384Ki (~516 MiB)
```

After install, the trimmed stack's actual scheduled memory requests summed from the live pods
(`kubectl get pods -n observability -o jsonpath=...requests.memory`) came to **~516 MiB**
(Grafana 128Mi + Prometheus 256Mi + the operator 100Mi + `kube-state-metrics` 32Mi, live-confirmed
`Burstable` QoS, not BestEffort; only the two Grafana sidecar containers remain on the chart's
default, unset resources) — matching the ~516Mi estimate baked into the script's preflight
comment, confirming this dev machine's Docker Desktop allocation (9.71 GiB node-allocatable) has
ample headroom (~9.18 GiB) for the trimmed stack. This is a starting-point measurement per the
STATE.md Phase 11 blocker note, not a hard budget — re-measure if Docker Desktop's memory
allocation changes.

### Windows/Docker Desktop: `helm --wait` and watch-based waits hang on this kind setup
Live-verified during Phase 11 Plan 03: `helm upgrade --install ... --wait --timeout 300s`
against this Windows host + Docker Desktop + kind cluster hangs indefinitely — reproduced twice,
each time with the `helm.exe` process accruing well under 3 seconds of CPU time over 20+ minutes
of wall-clock time while holding an established (but silently stalled) TCP connection to the
kind API server's host-mapped port. Killing the process, cleaning up the pending release, and
re-running `helm upgrade --install` **without** `--wait` completes normally in well under two
minutes; a plain polling `kubectl get pods` loop (no `--watch`, no `kubectl wait`) then confirms
readiness reliably. The working theory is that Docker Desktop's Windows port-forwarding proxy
does not reliably deliver the long-lived chunked-transfer HTTP responses that Kubernetes watch
connections depend on. `scripts/observability-up.sh` was fixed accordingly (Step 2 no longer
passes `--wait`; Step 3 polls with `kubectl get` on a 180s deadline instead of `kubectl wait`).
If this script is ported to a Linux/WSL2-native Docker host, `--wait`/`kubectl wait` should work
normally there — this is specifically a Windows Docker Desktop port-forwarding quirk, not a
kind or Helm defect.

### Anonymous Grafana Viewer Access
Grafana's `grafana.ini` enables anonymous access with the `Viewer` role (D-08), so Phase 15/16's
"Open in Grafana" deep links open without a login wall during demos. Admin login is retained for
editing dashboards. As with the rest of the platform (see "Port-Forward Only — No Ingress or
TLS" above), Grafana is reachable exclusively via `kubectl port-forward` on `localhost` — the
widened Viewer role is scoped to that local-only surface, not exposed on any network.

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
