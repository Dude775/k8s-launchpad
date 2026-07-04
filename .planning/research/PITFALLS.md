# Pitfalls Research

**Domain:** Local Kubernetes developer platform — kind + Helm + Flask + MongoDB on Windows/WSL2
**Researched:** 2026-07-04
**Confidence:** HIGH (most pitfalls verified against official docs, kind issues, Bitnami announcements)

---

## Critical Pitfalls

### Pitfall 1: kind Local Registry — containerd config not propagated to nodes

**What goes wrong:**
You start a local Docker registry container, push your image to `localhost:5001`, and pods still fail with `ErrImagePull` / `ImagePullBackOff`. The image is in the registry. The registry is running. But the kind nodes' containerd does not know to route `localhost:5001` through the registry container — `localhost` inside a container is the container's own loopback, not the host's.

**Why it happens:**
kind nodes are Docker containers with their own network namespace. `localhost:5001` inside a node container does not reach the host's port 5001. containerd must be explicitly told via `/etc/containerd/certs.d/localhost:5001/hosts.toml` to mirror `localhost:5001` → `http://kind-registry:5000` (the registry's Docker network hostname). Without this file on every node, pulls fail.

**How to avoid:**
Use the official kind-with-registry script pattern verbatim. It does three things in order: (1) creates the registry container pinned to a named Docker network, (2) creates the kind cluster with a `containerdConfigPatches` block enabling the `config_path` directory, (3) patches each node with the `hosts.toml` mirror file, and (4) connects the registry container to the `kind` Docker network. Do not split these steps or skip the network connection step.

Minimum cluster config patch:
```yaml
containerdConfigPatches:
  - |-
    [plugins."io.containerd.grpc.v1.cri".registry]
      config_path = "/etc/containerd/certs.d"
```

Then for each node, write `/etc/containerd/certs.d/localhost:5001/hosts.toml`:
```toml
[host."http://kind-registry:5000"]
  capabilities = ["pull", "resolve"]
```

**Warning signs:**
- `kubectl describe pod` shows `ErrImagePull` with message "no such host" or "connection refused" for `localhost:5001`
- `docker push localhost:5001/myimage:tag` succeeds but pod still fails
- `kind load docker-image` works but registry push does not (different code paths entirely)

**Phase to address:** Phase: Cluster Setup (kind + registry script)

---

### Pitfall 2: `kind load docker-image` + `:latest` tag = silent pull failure

**What goes wrong:**
You run `kind load docker-image myapp:latest`, it succeeds. You deploy. Kubernetes immediately tries to pull `myapp:latest` from the internet and fails with `ImagePullBackOff`. The loaded image is ignored.

**Why it happens:**
Kubernetes defaults `imagePullPolicy` to `Always` when the image tag is `latest`. `Always` means containerd will attempt a remote pull regardless of whether the image is already present locally. The kind-loaded image sits unused.

**How to avoid:**
Either (a) use versioned tags (`myapp:0.1.0`) — they default to `IfNotPresent` which uses the loaded copy — or (b) explicitly set `imagePullPolicy: IfNotPresent` in the Helm chart's Deployment template. For the registry-based approach (recommended for this project), tag as `localhost:5001/myapp:0.1.0` and push to registry; `imagePullPolicy: IfNotPresent` is still required during cluster-up before first push.

**Warning signs:**
- Pod stuck in `ImagePullBackOff` immediately after `kind load` reports success
- `kubectl describe pod` shows pull attempt against `docker.io/library/myapp` (default registry)
- Works with explicit `imagePullPolicy: Never` but not with default

**Phase to address:** Phase: Containerization + Helm chart authoring

---

### Pitfall 3: CRLF line endings in shell scripts break inside containers and WSL2

**What goes wrong:**
Scripts (the kind+registry setup script, entrypoints, healthcheck scripts) checked out on Windows have `\r\n` line endings. When executed inside a Linux container or WSL2, bash sees a trailing `\r` on every line, producing: `/bin/bash^M: No such file or directory` or `$'\r': command not found`.

**Why it happens:**
Git on Windows defaults to `core.autocrlf=true`, converting LF to CRLF on checkout. VS Code on Windows defaults to CRLF for new files. A script with `#!/bin/bash\r\n` has a broken shebang; bash cannot find the interpreter `bash\r`.

**How to avoid:**
Commit a `.gitattributes` file as the very first commit (before any scripts):
```
*.sh    text eol=lf
*.yaml  text eol=lf
*.yml   text eol=lf
Makefile text eol=lf
```
This enforces LF on checkout for all shell scripts and YAML regardless of platform. Verify with `file scripts/cluster-up.sh` in WSL2 — should say "ASCII text" not "ASCII text, with CRLF line terminators".

**Warning signs:**
- `^M` visible in `cat -A script.sh`
- `bad interpreter` errors when running scripts in WSL2 or from Makefile
- Scripts work in Git Bash (which tolerates CRLF) but fail inside `docker exec` or `kubectl exec`

**Phase to address:** Phase: Repo scaffold (first commit, before any scripts exist)

---

### Pitfall 4: MSYS path mangling in Git Bash breaks docker and kubectl flags

**What goes wrong:**
Running `docker run -v /c/Users/...:/app` or `kubectl cp /path/to/file pod:/dest` from Git Bash causes errors because MSYS2 (Git Bash's runtime) auto-translates Unix paths to Windows paths when calling native Windows binaries. The translated path is wrong or contains backslashes that the tool rejects.

**Why it happens:**
MSYS2 translates arguments beginning with `/` to Windows paths before passing them to `.exe` binaries. So `/app` becomes `C:\app`, and `-v /app:/container` becomes `-v C:\app:C:\container`, which is not what docker expects.

**How to avoid:**
In Makefile targets that use volume mounts or path arguments, prefix with `MSYS_NO_PATHCONV=1`:
```makefile
MSYS_NO_PATHCONV=1 docker run -v $(PWD)/data:/data myimage
```
Or set at the top of the Makefile:
```makefile
export MSYS_NO_PATHCONV := 1
```
For kubeconfig paths, use the WSL2 Unix path explicitly (`~/.kube/config`) rather than Windows paths. Alternatively, run all cluster operations from inside WSL2, not Git Bash.

**Warning signs:**
- docker `-v` mount errors mentioning unexpected colons or Windows drive letters
- kubectl errors about invalid kubeconfig path containing backslashes
- Commands work in WSL2 terminal but fail identically in Git Bash

**Phase to address:** Phase: Makefile + Cluster Setup

---

### Pitfall 5: Bitnami MongoDB chart image unavailability (post-August 2025)

**What goes wrong:**
`helm install` or `helm upgrade` for MongoDB using `repo.helms.sh/bitnami` or `docker.io/bitnami/mongodb` with a versioned tag (e.g., `7.0.x`) fails with `ImagePullBackOff` because the image no longer exists at `docker.io/bitnami/`.

**Why it happens:**
Bitnami announced effective August 28, 2025: versioned MongoDB images moved from the public `docker.io/bitnami` catalog to `docker.io/bitnamilegacy` (no further updates) or behind a Broadcom commercial subscription. OCI-packaged Helm charts at `docker.io/bitnamicharts` remain available but reference image tags that no longer pull without credentials. Only a limited "latest-only" free tier remains at `docker.io/bitnami`.

**How to avoid:**
For this project, use the official MongoDB community Docker image (`mongo:7.0`) with a minimal custom Deployment manifest or a simple community Helm chart (e.g., the `mongodb` chart from `https://charts.helm.sh/stable` community fork). Alternatively, use MongoDB's own official Helm chart via `https://mongodb.github.io/helm-charts` (the MongoDB Community Kubernetes Operator). Do NOT depend on `helm repo add bitnami https://charts.bitnami.com/bitnami` pulling versioned images; it will fail in 2025+.

Simple Deployment alternative that avoids the Bitnami dependency entirely:
```yaml
image: mongo:7.0
```
with a Kubernetes Secret for `MONGO_INITDB_ROOT_USERNAME` / `MONGO_INITDB_ROOT_PASSWORD`.

**Warning signs:**
- `helm install` succeeds but MongoDB pod stuck in `ImagePullBackOff`
- `kubectl describe pod` shows `403 Forbidden` or `unauthorized` from `docker.io/bitnami/mongodb`
- Works on older environments that cached the image, fails on fresh clusters

**Phase to address:** Phase: MongoDB in-cluster deployment

---

### Pitfall 6: Secrets committed to git before .gitignore exists

**What goes wrong:**
A `.env` file, `values-local.yaml` with real passwords, or a kubeconfig gets committed before `.gitignore` is in place. Even after adding `.gitignore` and removing the file, the secret remains in git history forever — visible to anyone who clones the repo.

**Why it happens:**
Developers scaffold the app, create `.env` to test locally, then forget to add `.gitignore` first. Or they add `values-local.yaml` with `mongodb.auth.rootPassword: mypassword` intending to "clean it up later."

**How to avoid:**
The `.gitignore` file must be the very first commit or part of the repo initialization commit — before any code, env files, or kubeconfigs. Minimum entries:
```
.env
*.local.yaml
kubeconfig
*.kubeconfig
__pycache__/
.venv/
*.pyc
.pytest_cache/
```
Use `git status` before every commit to verify no unintended files are staged. Add a `make check-secrets` target that greps for common secret patterns.

**Warning signs:**
- `git log --all --full-history -- .env` shows a result
- `.env` appears in `git diff HEAD` as tracked
- `git status` shows `.env` as "Changes to be committed" but it contains real values

**Phase to address:** Phase: Repo scaffold (first commit)

---

### Pitfall 7: Flask dev server in production Docker image

**What goes wrong:**
The Dockerfile `CMD` uses `flask run` or `python app.py` with `app.run(debug=True)`. The app technically starts and responds to requests, passing local tests. In a Kubernetes pod, it handles one request at a time, leaks debug information, and does not respond to `SIGTERM` — Kubernetes sends `SIGTERM` before `SIGKILL`, but Flask's dev server ignores it, causing a 30-second forced kill delay on every rollout.

**Why it happens:**
`flask run` is the natural development command. Developers copy it to Dockerfile CMD without switching to a production WSGI server.

**How to avoid:**
Dockerfile CMD must use gunicorn from day one:
```dockerfile
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "30", "app:app"]
```
Set `--workers 1` for the local dev image to avoid the multiprocess prometheus issue (see Pitfall 8). Never set `debug=True` outside of `if __name__ == "__main__"` guards. The Flask dev server is acceptable for `make run-local` (host execution), not in Docker.

**Warning signs:**
- Dockerfile CMD contains `flask run` or `python app.py`
- Pod takes 30+ seconds to terminate during `kubectl rollout restart`
- `/metrics` returns inconsistent values across requests (sign of multiprocess without multiprocess mode)
- `app.run(debug=True)` present unconditionally in `app.py`

**Phase to address:** Phase: Containerization (Dockerfile)

---

### Pitfall 8: prometheus_client multiprocess collision with gunicorn workers

**What goes wrong:**
The `/metrics` endpoint returns counters that reset between scrapes, show 0 when traffic exists, or return different values on each request. Prometheus graphs are meaningless.

**Why it happens:**
prometheus_client stores metrics in-process by default. With gunicorn using N workers, each worker maintains its own in-memory metric state. A scrape hits worker A, next scrape hits worker B — you get one worker's partial view. Counters appear to restart. Gauges oscillate.

**How to avoid:**
Since `/metrics` is a seam for PRD-4 (not actively scraped in PRD-1), set `--workers 1` in gunicorn for now and document that multi-worker support requires `PROMETHEUS_MULTIPROC_DIR`. When workers > 1 is needed:
1. Set env var `PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc`
2. Create that directory before gunicorn starts (Dockerfile or entrypoint)
3. Wipe it on gunicorn startup (stale mmap files cause incorrect cumulative counts)
4. Add `MultiProcessCollector` in the `/metrics` route handler

**Warning signs:**
- `/metrics` returns different Counter values on repeated `curl` calls
- Metrics that should monotonically increase appear to reset
- Works with `gunicorn --workers 1` but breaks with 2+

**Phase to address:** Phase: Flask app + Containerization; full fix deferred to PRD-4

---

### Pitfall 9: Makefile — tabs, shell assumptions, make not installed in Git Bash

**What goes wrong:**
Three failure modes:
1. Makefile recipe lines use spaces instead of tabs (editor auto-converts) → `make: *** missing separator. Stop.`
2. `make` is not in Git Bash's PATH (Git Bash does not ship with make) → `make: command not found`
3. Recipes use bash-isms (`[[`, `source`, `local`) but SHELL defaults to `sh` → syntax errors

**Why it happens:**
VS Code and many editors replace tabs with spaces on paste or auto-format. Git Bash on Windows only includes core POSIX tools; `make` requires separate installation (Chocolatey, MSYS2, or WSL). `SHELL` is never inherited from environment in make; it defaults to `/bin/sh`.

**How to avoid:**
- Configure VS Code to never expand tabs in Makefile (`.editorconfig`: `[Makefile] indent_style = tab`)
- Document in README that `make` on Windows requires: `choco install make` or run from WSL2
- Set at top of Makefile: `SHELL := /bin/bash` and add `.SHELLFLAGS := -eu -o pipefail -c`
- Mark all non-file targets: `.PHONY: cluster-up cluster-down build load deploy test clean`
- Test every Makefile target in both Git Bash and WSL2 before marking the phase done

**Warning signs:**
- `make: *** missing separator` on any target
- `[[: not found` or `source: not found` in recipe output
- `make cluster-up` works in WSL2 but fails in Git Bash with path errors

**Phase to address:** Phase: Makefile scaffold (wrap every other phase)

---

### Pitfall 10: MongoDB auth — connection string mismatch and authSource

**What goes wrong:**
Flask connects to MongoDB with pymongo using a connection string that matches the chart's root username/password but authentication still fails with `Authentication failed`. Or auth passes but the app writes to a database it cannot read back because authSource defaults differ.

**Why it happens:**
MongoDB's `MONGO_INITDB_ROOT_USERNAME` creates a user in the `admin` database. pymongo connection strings that omit `authSource=admin` default to authenticating against the database named in the URI, not `admin`. So `mongodb://root:pass@mongodb:27017/fieldguide` attempts auth against `fieldguide` where the root user does not exist.

**How to avoid:**
Connection string must explicitly specify authSource:
```
mongodb://root:$(MONGO_ROOT_PASSWORD)@mongodb:27017/fieldguide?authSource=admin
```
Inject the password from a Kubernetes Secret via environment variable into the Flask pod — never hardcode. The Secret name must match what the chart creates (or use `auth.existingSecret` in chart values to control the name explicitly).

**Warning signs:**
- `pymongo.errors.OperationFailure: Authentication failed` in Flask logs
- Works with `auth.enabled: false` in chart values but breaks with auth enabled
- `kubectl logs` shows successful MongoDB startup but Flask crashes on first DB call

**Phase to address:** Phase: MongoDB deployment + Flask app integration

---

### Pitfall 11: MongoDB data loss on `kind cluster-down`

**What goes wrong:**
`make cluster-down` destroys the kind cluster. All MongoDB data (PVCs backed by kind's default `standard` StorageClass, which maps to node-local storage inside Docker containers) is permanently lost. This is expected but surprises developers if not documented.

**Why it happens:**
kind's nodes are Docker containers. When the kind cluster is deleted, those containers are removed — taking all PVC data with them. There is no persistence layer that survives cluster teardown by design.

**How to avoid:**
Document this explicitly in README: "Data is ephemeral. `make cluster-down` destroys all MongoDB data." For PRD-1, this is acceptable — the field-guide app can seed data on startup from a fixtures file. Add a `make seed` target that POST-s fixture entries after deploy. Do NOT spend time on hostPath volume persistence for local kind in PRD-1; it is a distraction.

**Warning signs:**
- Developer surprised that MongoDB is empty after `make cluster-down && make cluster-up`
- Time spent debugging PVC binding for local persistence instead of building the platform

**Phase to address:** Phase: MongoDB deployment — document explicitly, add seed target

---

### Pitfall 12: Docker Desktop vs. native Docker in WSL2 — split daemon problem

**What goes wrong:**
You install Docker Desktop on Windows with WSL2 backend AND separately install Docker Engine inside WSL2. Now there are two Docker daemons. Images built in one are invisible to the other. kind clusters created in one context are invisible to kubectl in the other. `kind get clusters` returns empty from WSL2 while the cluster runs fine in Docker Desktop.

**Why it happens:**
Docker Desktop with WSL2 backend exposes the Docker socket into WSL2 distros, but only for the Docker Desktop daemon. A natively installed Docker Engine in WSL2 runs its own separate daemon on `/var/run/docker.sock`. `DOCKER_HOST` and Docker context determine which daemon each CLI call reaches.

**How to avoid:**
Choose one approach and document it in README. Recommended: Docker Desktop with WSL2 backend integration enabled (Settings → Resources → WSL Integration → enable for your distro). Do NOT install Docker Engine natively inside WSL2 alongside Docker Desktop. Verify with `docker context ls` — only one context should be active. All make targets run against the same Docker daemon.

**Warning signs:**
- `kind get clusters` returns empty in WSL2 terminal after successful `kind create cluster` in PowerShell
- Images built with `docker build` are not found by `kind load docker-image`
- `kubectl get nodes` returns "connection refused" even though the cluster was just created

**Phase to address:** Phase: Cluster Setup — README prerequisite section

---

### Pitfall 13: Helm chart `version` vs `appVersion` confusion causing stale deploys

**What goes wrong:**
You fix a bug in the Flask app, rebuild and push the image, run `helm upgrade`. But the running pods do not restart — the old version keeps serving. Or: `helm package` fails with "version already exists" because `version` in Chart.yaml was not bumped.

**Why it happens:**
Helm's `version` field tracks the chart packaging version. `appVersion` is metadata only — it does not control which image is deployed. The image tag in `values.yaml` controls that. If you rebuild `myapp:0.1.0` and push a new image under the same tag, `helm upgrade` sees no change in the chart spec and may not restart pods. Additionally, Helm chart repos reject packages with duplicate `version` values.

**How to avoid:**
- Use mutable-tag + explicit `helm upgrade --recreate-pods` OR use immutable image tags (increment tag on every build: `0.1.0`, `0.1.1`)
- In PRD-1, use a `BUILD_TAG` variable (e.g., git short SHA or timestamp) in Makefile: `docker build -t localhost:5001/field-guide-api:$(shell git rev-parse --short HEAD)`
- Set `image.tag` in `values.yaml` to `latest` as default, override via `--set image.tag=$(BUILD_TAG)` in the `make deploy` target
- Bump `version` in Chart.yaml whenever chart templates change; bump `appVersion` when the app version changes

**Warning signs:**
- `helm upgrade` exits 0 but pod does not restart (no `MODIFIED` in `kubectl get pods -w`)
- Running container still shows old response after upgrade
- `helm package` fails with "Error: file already exists"

**Phase to address:** Phase: Helm chart + Makefile deploy target

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| `imagePullPolicy: Always` with `:latest` | No need to tag builds | Cluster always tries remote pull; breaks offline | Never for kind local dev |
| Hardcoding `MONGO_URI` in Deployment env | Quick wiring | Breaks PRD-3 templating; secret in manifest | Never |
| `flask run` in Dockerfile CMD | Fast to write | Dev server in prod; no graceful shutdown | Never |
| Skipping resource `limits` in Helm chart | Simpler chart | OOM kills entire kind node in low-memory scenarios | Only during initial scaffold, fix before first deploy |
| Bitnami MongoDB chart with latest bitnami image | One-liner chart dep | Breaks on fresh cluster post-Aug 2025 | Never for new projects |
| Single-process gunicorn (`--workers 1`) | Avoids prometheus multiproc complexity | Not representative of production; PRD-4 will need fix | Acceptable for PRD-1; must document |
| No `.gitattributes` | Fewer files to maintain | CRLF scripts fail inside containers silently | Never |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| kind ↔ local registry | Assume localhost:5001 works without containerd mirror config | Run official kind-with-registry script that patches each node's `hosts.toml` |
| Flask ↔ MongoDB | Omit `authSource=admin` in connection string | Always append `?authSource=admin` when using root user |
| gunicorn ↔ prometheus_client | Default single-process mode with multiple workers | Use `--workers 1` for PRD-1; add `PROMETHEUS_MULTIPROC_DIR` when scaling |
| Helm ↔ Kubernetes Secret | Store password in `values.yaml` | Use `auth.existingSecret` or a Secret template with `secretKeyRef` in Deployment |
| Makefile ↔ Git Bash | Missing `MSYS_NO_PATHCONV=1` on docker `-v` flags | Export at Makefile top or prefix individual targets |
| kind ↔ Docker Desktop | Two Docker daemons coexisting | Pick one, verify with `docker context ls`, document in README |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| MongoDB root password in `values.yaml` committed to git | Permanent credential exposure in git history | Create a Kubernetes Secret separately; reference via `auth.existingSecret` or `secretKeyRef` |
| `.env` committed before `.gitignore` | Credentials in git history forever | `.gitignore` as first commit; `pre-commit` hook to block `.env` |
| `debug=True` in Flask Dockerfile | Exposes interactive debugger endpoint on `/` | Guard with `if __name__ == "__main__"` only; never in gunicorn CMD |
| Running container as root | Full root access inside container if compromised | Add `USER 1000` in Dockerfile; set `securityContext.runAsNonRoot: true` in Helm chart |
| kubeconfig committed to repo | Anyone with repo access can control the cluster | Add `kubeconfig` and `*.kubeconfig` to `.gitignore` before scaffold |

---

## "Looks Done But Isn't" Checklist

- [ ] **Registry wiring:** `docker push localhost:5001/app:tag` succeeds AND `kubectl run test --image=localhost:5001/app:tag` also succeeds — verify BOTH
- [ ] **Graceful shutdown:** `kubectl delete pod <pod>` completes within 10 seconds — if it takes 30s, gunicorn is not receiving SIGTERM
- [ ] **MongoDB auth:** Flask logs show successful DB connection after pod start, not just "MongoDB pod is Running"
- [ ] **Makefile targets:** Every target tested in Git Bash AND WSL2, not just one shell
- [ ] **Secrets not committed:** `git log --all -- .env` returns nothing; `grep -r "password" charts/` returns only template refs, not literal values
- [ ] **imagePullPolicy:** Helm chart deployment template explicitly sets `imagePullPolicy: IfNotPresent`, not relying on default
- [ ] **CRLF:** `file scripts/*.sh` shows "ASCII text" with no "CRLF" in WSL2
- [ ] **Resource limits:** `kubectl describe pod <app>` shows non-empty `Limits` section
- [ ] **Bitnami image pull:** Fresh `make cluster-up && make deploy` on a machine that has never pulled the MongoDB image succeeds without credentials

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Registry not reachable from nodes | MEDIUM | Delete and recreate cluster with correct kind config; re-run registry script |
| CRLF in scripts after first commit | MEDIUM | Add `.gitattributes`, run `git add --renormalize .`, recommit affected scripts |
| Secret committed to git | HIGH | `git filter-repo --path .env --invert-paths`; rotate ALL credentials in the secret; notify collaborators to re-clone |
| Wrong Bitnami chart image | LOW | Switch to `mongo:7.0` official image; rewrite Helm dependency or Deployment; no data loss if cluster is ephemeral |
| imagePullPolicy:Always causing pull failures | LOW | Edit `values.yaml` / Helm template; `helm upgrade` |
| Makefile spaces instead of tabs | LOW | Re-open in editor with "show whitespace" enabled; replace; verify with `cat -A Makefile` |
| Two Docker daemons | MEDIUM | `docker context use <correct-context>`; recreate kind cluster in correct context |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| CRLF line endings | Phase 1: Repo scaffold (`.gitattributes` first commit) | `file scripts/*.sh` in WSL2 shows no CRLF |
| Secrets committed before .gitignore | Phase 1: Repo scaffold | `git log --all -- .env` returns nothing |
| Docker daemon split (Desktop vs WSL2) | Phase 2: Cluster setup (README prerequisites) | `docker context ls` shows one active context |
| kind registry containerd wiring | Phase 2: Cluster setup (kind+registry script) | `kubectl run --image=localhost:5001/test:tag` pulls successfully |
| imagePullPolicy:Always + :latest | Phase 3: Helm chart authoring | Chart template has explicit `imagePullPolicy: IfNotPresent` |
| Bitnami MongoDB image unavailability | Phase 4: MongoDB deployment | Fresh cluster + `make deploy` pulls mongo image without error |
| MongoDB authSource mismatch | Phase 4: MongoDB + Flask integration | Flask logs show "Connected to MongoDB" on pod start |
| MongoDB data loss on cluster-down | Phase 4: MongoDB deployment (documentation + seed target) | README documents ephemeral behavior; `make seed` exists |
| Flask dev server in Dockerfile | Phase 3: Containerization | Dockerfile CMD uses `gunicorn`; `docker inspect` confirms |
| prometheus_client multiprocess | Phase 3: Containerization (defer full fix to PRD-4) | `--workers 1` documented; PRD-4 backlog item created |
| MSYS path mangling | Phase 2+5: Cluster setup + Makefile | All `make` targets pass in Git Bash without path errors |
| Makefile tabs + shell | Phase 5: Makefile scaffold | `make -n cluster-up` exits 0 in both shells; no separator errors |
| Helm version/appVersion confusion | Phase 3: Helm chart + deploy target | New image tag triggers pod replacement; stale image not served |
| Secrets in Helm values.yaml | Phase 3: Helm chart | `grep -r password charts/` returns only `secretKeyRef` references |

---

## Sources

- [kind Local Registry official docs](https://kind.sigs.k8s.io/docs/user/local-registry/)
- [kind WSL2 docs](https://kind.sigs.k8s.io/docs/user/using-wsl2/)
- [KiND — How I Wasted a Day Loading Local Docker Images (iximiuz)](https://iximiuz.com/en/posts/kubernetes-kind-load-docker-image/)
- [Bitnami catalog deprecation announcement — Issue #35164](https://github.com/bitnami/charts/issues/35164)
- [Bitnami MongoDB Helm dependency broken — LibreChat Discussion #10255](https://github.com/danny-avila/LibreChat/discussions/10255)
- [Docker and Git Bash / MSYS2 path conversion workaround (GitHub Gist)](https://gist.github.com/borekb/cb1536a3685ca6fc0ad9a028e6a959e3)
- [Prometheus multiprocess mode official docs](https://prometheus.github.io/client_python/multiprocess/)
- [CRLF line endings breaking CI (iotools)](https://iotools.cloud/journal/crlf-vs-lf-line-ending-bug-ci/)
- [12 Helm Chart Mistakes — DevOps Training Institute](https://www.devopstraininginstitute.com/blog/12-helm-chart-mistakes-how-to-fix-them)
- [kind Issue #2665 — localhost:5000 not reachable](https://github.com/kubernetes-sigs/kind/issues/2665)

---
*Pitfalls research for: kind + Helm + Flask + MongoDB on Windows/WSL2 (k8s-launchpad PRD-1)*
*Researched: 2026-07-04*
