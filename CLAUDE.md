<!-- GSD:project-start source:PROJECT.md -->
## Project

**k8s-launchpad**

k8s-launchpad is a self-hosted Internal Developer Platform (IDP) — a "mini-Heroku" running on a local Kubernetes cluster. A developer registers a Git repo through a web dashboard; the platform automatically builds it (Docker), deploys it (Helm), syncs it via GitOps (ArgoCD), monitors it (Prometheus/Grafana/Loki), and scans it for vulnerabilities (Trivy), with a self-diagnostics engine that health-checks the platform's own components. Built as a portfolio piece to demonstrate platform-engineering-level thinking.

**This milestone (PRD-1) covers ONLY the foundation:** monorepo, a sample "field-guide" Flask API (the platform's dogfood app), containerization, a local kind cluster with local registry, and Helm deployment. Everything runs locally and free.

**Core Value:** `make cluster-up && make build && make load && make deploy` produces a running, reachable app on a local kind cluster — the full local build-to-deploy loop works end to end.

### Constraints

- **Tech stack (LOCKED)**: Python 3.11 + Flask backend; MongoDB (local, containerized); Docker; kind (Kubernetes in Docker); local registry (kind's or a local Docker registry container); Helm 3; monorepo — do not re-ask or substitute
- **Budget**: Everything local and free — no cloud, no AWS in this milestone
- **Security**: .env for local config, Kubernetes Secrets in-cluster; NEVER commit real secrets; .gitignore before first meaningful commit
- **Platform**: Windows host with WSL2 / Git Bash — make targets and scripts must work in that environment
- **Git**: Many small human-style commits (lowercase, short messages)
- **Autonomy**: Operate autonomously on routine implementation choices; pause only for (a) cloud cost, (b) real credentials/secrets, (c) contradicting a locked decision. Record decisions in CONTEXT.md.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Core Technologies
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11 | Runtime (locked) | Matches developer stack; gunicorn 26 requires ≥3.10; LTS support through 2027 |
| Flask | 3.1.3 | REST API framework (locked) | Latest stable (Feb 2026); drops Werkzeug legacy; async-ready; minimal surface area matches IDP dogfood scope |
| Flask-PyMongo | 3.0.1 | MongoDB integration extension | Requires Flask ≥3.0 + PyMongo ≥4.0; officially maintained under mongodb-labs; cleaner app-factory support than raw MongoClient wiring |
| PyMongo | 4.13.2 | MongoDB driver | Latest stable; `patch-version-number = 4.13.2` confirmed in official snooty.toml; synchronous API appropriate for Flask |
| gunicorn | 26.0.0 | WSGI production server | Latest stable (May 2026); requires Python ≥3.10; standard for Flask-in-container; 1 worker per Kubernetes pod (let K8s scale horizontally) |
| prometheus-flask-exporter | 0.23.2 | /metrics endpoint | Latest (Mar 2025); wraps `prometheus_client`; zero-config auto-instruments HTTP duration, request count, exceptions; exposes on `/metrics` matching PRD-4 Prometheus scrape seam |
| python-dotenv | 1.2.2 | Local .env loading | Latest (Mar 2026); standard for local config without committing secrets |
| kind | v0.32.0 | Local Kubernetes cluster (locked) | Latest release; Kubernetes 1.33.1 default node image; CI-friendly, disposable, free |
| Docker | 27.x (host-installed) | Container runtime (locked) | Required by kind; build target for Flask image |
| Helm | 3.21.2 (locked) | Chart packaging (locked) | Latest Helm 3 (Jun 2026); bug fixes through Jul 2026. **See note below on Helm 4.** |
### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.1.1 | Test runner | Always; latest stable (Jun 2026); async-aware; rich fixture model |
| pytest-flask | 1.3.0 | Flask test client fixture | Always; v1.3.0 fixed Flask 3.0 compatibility (removed deprecated `request_ctx`); provides `client` fixture via `conftest.py` |
| pytest-cov | 5.x (latest) | Coverage reporting | Always; plug into `make test` for 95% target; `--cov=src --cov-report=term-missing` |
| Werkzeug | (Flask dep, auto) | WSGI utilities | Do not pin separately; Flask 3.x pins compatible version |
### Development Tools
| Tool | Purpose | Notes |
|------|---------|-------|
| registry:3 | Local OCI registry container | Run as `kind-registry` on `localhost:5001`; push with `docker push localhost:5001/image:tag`; pods reference same host:port via containerd mirror config |
| make | Makefile task runner | Set `SHELL := /bin/bash` at top; add `MSYS_NO_PATHCONV=1` export for Git Bash path-conversion bug; all targets must be POSIX-safe |
| .gitattributes | LF enforcement | Add `* text=auto eol=lf` + `*.sh text eol=lf` to prevent CRLF in scripts on Windows; critical for WSL2/Git Bash shells — CRLF in shell scripts causes `bad interpreter: No such file or directory` |
## Installation (requirements.txt)
# requirements-dev.txt
## MongoDB In-Cluster: Simple Manifest (NOT Bitnami)
- `mongodb-deployment.yaml` — `Deployment` using `mongo:7` (official Docker Hub image; latest LTS)
- `mongodb-service.yaml` — `ClusterIP` Service on port 27017
- `mongodb-pvc.yaml` — `PersistentVolumeClaim` backed by kind's default hostPath StorageClass
- `mongodb-secret.yaml` — Kubernetes `Secret` with `MONGO_INITDB_ROOT_USERNAME` / `MONGO_INITDB_ROOT_PASSWORD` (base64, from values)
## kind + Local Registry Pattern
### Canonical 2025/2026 Setup
#!/usr/bin/env bash
# 1. Start registry container (idempotent)
# 2. Create kind cluster with containerd mirror config
- |-
# 3. Write hosts.toml on each node so containerd resolves localhost:5001 -> registry
# 4. Connect registry to kind network (if not already)
# 5. Document registry via ConfigMap (for tooling discovery)
- Build: `docker build -t localhost:5001/field-guide-api:latest ./apps/field-guide-api`
- Push to registry: `docker push localhost:5001/field-guide-api:latest`
- Helm values: `image.repository: localhost:5001/field-guide-api`
- Pod image pull: pods reference `localhost:5001/...` (containerd mirrors it via `kind-registry:5000`)
## Docker Image Best Practices
# --- Builder stage ---
# --- Runtime stage ---
# Copy installed packages from builder
# Non-root user
## Helm Chart Structure
## Alternatives Considered
| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| Flask-PyMongo 3.0.1 | raw `pymongo.MongoClient` in app factory | Flask-PyMongo handles app-context teardown, connection pooling, and URI config automatically; less boilerplate |
| prometheus-flask-exporter | bare `prometheus_client` + custom `/metrics` route | prometheus-flask-exporter auto-instruments all routes; bare client requires manual labeling for every route |
| python:3.11-slim base | python:3.11-alpine | Alpine = musl libc = no pre-compiled wheels for PyMongo, cryptography, etc.; slower builds, larger final size after gcc |
| python:3.11-slim base | python:3.11 (full Debian) | Full image is ~1GB+; slim removes docs, man pages, locale data while keeping glibc; negligible feature difference |
| Simple MongoDB manifest | Bitnami mongodb Helm chart | Bitnami behind Broadcom paywall since Sep 29 2025; no longer free |
| Simple MongoDB manifest | MongoDB Community Operator | Operator adds CRDs, RBAC, MongoDBCommunity CRs — 6+ resources for a single-instance learning deployment; PRD-1 scope |
| registry:3 + kind | minikube registry addon | kind is locked; minikube is a separate tool with heavier resource profile |
| gunicorn | Flask dev server (`flask run`) | Dev server is single-threaded, not signal-safe, not for containers; gunicorn handles SIGTERM for graceful K8s pod termination |
| Helm 4.2.2 | Helm 3.21.2 | Charts are identical; Helm 3 EOL Jul 2026 (security patches only Nov 2026). If installing fresh, use Helm 4. If team has Helm 3, charts work unchanged. |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Bitnami MongoDB Helm chart | Behind Broadcom subscription paywall since Sep 29 2025; no longer free/public | Simple Kubernetes manifests with `mongo:7` official image |
| Alpine base image for Python | musl libc means no pre-compiled wheels; C-extension packages (PyMongo, cryptography) need full build toolchain — negates size benefit | `python:3.11-slim` |
| Flask dev server in Docker | Single-threaded, no SIGTERM handling, debug mode in prod is a security risk | `gunicorn` with 1 worker |
| `registry:2` in kind scripts | Official kind docs now reference `registry:3`; registry:2 still works but is dated | `registry:3` |
| Helm `--atomic` flag in Makefile | Renamed to `--rollback-on-failure` in Helm 4; flag is deprecated | Use `--rollback-on-failure` or avoid in Makefile for portability |
| `git add -A` before first commit | Will capture `.env`, `__pycache__`, kubeconfig if .gitignore not in place | Commit `.gitignore` first; then add specific paths |
| CRLF line endings in shell scripts | Git Bash / WSL2 bash fails with `bad interpreter: No such file or directory` on CRLF scripts | `.gitattributes` with `* text=auto eol=lf`; `*.sh text eol=lf` |
## WSL2 / Git Bash Makefile Compatibility
### Required Makefile Header
### Required `.gitattributes`
* text=auto eol=lf
### Makefile Targets Checklist
- Use `$$` for shell variables inside Makefile rules (single `$` is Makefile variable)
- Use `$(shell ...)` for shell substitution in variable definitions
- Avoid Windows-style paths; use relative paths from repo root
- `make -f Makefile` works identically in WSL2, Git Bash, and native Linux
## Version Compatibility Matrix
| Package | Compatible With | Notes |
|---------|-----------------|-------|
| Flask 3.1.3 | Flask-PyMongo 3.0.1, Werkzeug ≥3.0 | Flask-PyMongo 3.x requires Flask ≥3.0 |
| Flask-PyMongo 3.0.1 | PyMongo ≥4.0, MongoDB ≥4.4 | |
| PyMongo 4.13.2 | MongoDB 4.4, 5.0, 6.0, 7.0 | `mongo:7` Docker image is the right pairing |
| gunicorn 26.0.0 | Python ≥3.10, Flask 3.x | gunicorn dropped Python 3.9 support |
| prometheus-flask-exporter 0.23.2 | Flask 1.x–3.x, Python 3.8–3.12 | Tested against Python 3.11 |
| pytest-flask 1.3.0 | pytest ≥5.2, Flask 3.0+ | v1.3.0 specifically fixed Flask 3.0 compat |
| python-dotenv 1.2.2 | Python ≥3.10 (dropped 3.9 in 1.2.x) | |
| kind v0.32.0 | Docker 27.x, Kubernetes 1.33.1 default node image | |
## Sources
- `/pallets/flask` (Context7) — Flask 3.x versions, app factory patterns
- `/mongodb/docs-pymongo` (Context7) — PyMongo 4.13.2 snooty.toml confirmation
- `/pytest-dev/pytest` (Context7) — pytest fixtures, plugin list
- [Flask PyPI](https://pypi.org/project/Flask/) — version 3.1.3, Feb 2026 (HIGH confidence)
- [gunicorn PyPI](https://pypi.org/project/gunicorn/) — version 26.0.0, May 2026 (HIGH confidence)
- [pytest PyPI](https://pypi.org/project/pytest/) — version 9.1.1, Jun 2026 (HIGH confidence)
- [pytest-flask PyPI](https://pypi.org/project/pytest-flask/) — version 1.3.0, Flask 3 compat (HIGH confidence)
- [prometheus-flask-exporter PyPI](https://pypi.org/project/prometheus-flask-exporter/) — 0.23.2 (HIGH confidence)
- [python-dotenv PyPI](https://pypi.org/project/python-dotenv/) — 1.2.2, Mar 2026 (HIGH confidence)
- [Flask-PyMongo PyPI](https://pypi.org/project/Flask-PyMongo/) — 3.0.1, Jan 2025, requires Flask≥3 (HIGH confidence)
- [kind local registry docs](https://kind.sigs.k8s.io/docs/user/local-registry/) — registry:3, containerd config patch, ConfigMap pattern (HIGH confidence)
- [Bitnami catalog changes issue #35164](https://github.com/bitnami/charts/issues/35164) — paywall effective Sep 2025 (HIGH confidence)
- [Helm GitHub releases](https://github.com/helm/helm/releases) — Helm 4.2.2 latest, Helm 3.21.2 latest Helm 3 (HIGH confidence)
- [Helm 4 overview docs](https://helm.sh/docs/overview/) — Helm 3 charts compatible with Helm 4 unchanged (HIGH confidence)
- [kind GitHub releases](https://github.com/kubernetes-sigs/kind/releases) — v0.32.0 (MEDIUM confidence, inferred from search)
- WSL2/Makefile CRLF — Microsoft WSL issue tracker, multiple community sources (MEDIUM confidence)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
