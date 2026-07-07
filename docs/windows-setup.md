# Windows Setup Guide

k8s-launchpad is developed on Windows with Git Bash as the primary terminal. This page
covers the full install path, the two Windows-specific gotchas you will hit otherwise, and
WSL2 as an optional secondary path.

## Primary Path: Git Bash

Git Bash (shipped with [Git for Windows](https://git-scm.com/downloads/win)) provides a
POSIX-compatible shell on Windows. All `make` targets are written for Bash and are verified
in Git Bash. Use it as your default terminal for this project.

### Install Required Tools

Run these commands in Git Bash (or PowerShell if winget is not in Git Bash PATH):

```powershell
winget install Docker.DockerDesktop         # Docker Desktop 27.x
winget install Kubernetes.kind              # kind 0.32.0
winget install Helm.Helm                    # Helm 4.x (or 3.21+)
winget install Kubernetes.kubectl           # kubectl 1.29+
```

Git for Windows bundles GNU make. Verify with `make --version`.

After installing, open a **new** Git Bash terminal (so PATH is refreshed) and run:

```bash
make check-tools
```

All five tools (`docker`, `kind`, `helm`, `kubectl`, `bash`) must show `ok`.

### Why MSYS_NO_PATHCONV=1

Git Bash converts POSIX paths that start with `/` into Windows paths
(e.g., `//localhost:5001/image` becomes `C:/Program Files/Git/localhost:5001/image`).
This silently corrupts Docker registry URLs and kubectl arguments.

The fix — `export MSYS_NO_PATHCONV=1` — is already set in the **Makefile header** and
in `scripts/cluster-setup.sh`. You do not need to set it manually as long as you invoke
commands through `make`.

If you call `docker` or `kubectl` directly from Git Bash with paths containing `//`,
prefix the command:

```bash
MSYS_NO_PATHCONV=1 docker push localhost:5001/field-guide-api:dev
```

### Why LF Line Endings Matter

Git Bash and WSL2 both invoke scripts with `#!/usr/bin/env bash`. If a script has Windows
CRLF line endings (`\r\n`), the shell reads `\r` as part of the interpreter name and fails
with:

```
bash: bad interpreter: No such file or directory
```

The `.gitattributes` file in the repo root enforces LF on every clone:

```
* text=auto eol=lf
*.sh text eol=lf
```

If you cloned with `core.autocrlf=true` already set in your Git config, the scripts may
have CRLF. Fix it once:

```bash
git config core.autocrlf false
git checkout -- scripts/cluster-setup.sh scripts/cluster-teardown.sh
```

## Optional Path: WSL2

WSL2 (Ubuntu 22.04+) works as an alternative if you prefer a native Linux environment.

**Requirements inside WSL2:**

- Docker Desktop must be installed on the Windows host with **WSL2 integration enabled** for
  your distro (Docker Desktop → Settings → Resources → WSL Integration).
- `kind`, `helm`, and `kubectl` must be installed inside the WSL2 distro (not just on Windows),
  because WSL2 and Windows share the same Docker daemon but each shell resolves PATH separately.

```bash
# Inside WSL2 Ubuntu
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.32.0/kind-linux-amd64
chmod +x ./kind && sudo mv ./kind /usr/local/bin/kind

curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl && sudo mv kubectl /usr/local/bin/
```

Then run `make check-tools` inside the WSL2 shell to confirm everything is reachable.

**Note:** `MSYS_NO_PATHCONV` is only needed for Git Bash, not WSL2.

## See Also

- [docs/troubleshooting.md](troubleshooting.md) — symptom → cause → fix for common failures
- [README.md](../README.md) — quickstart and the full `make` target listing
