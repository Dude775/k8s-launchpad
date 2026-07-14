# Troubleshooting

Common symptoms, their likely causes, and fixes for the k8s-launchpad local stack.

## Symptom → Cause → Fix

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `ERROR: kind is not installed or not on PATH` | kind binary not on PATH | Install with `winget install Kubernetes.kind` or download from https://kind.sigs.k8s.io/dl/v0.32.0/kind-windows-amd64.exe; confirm with `kind version` |
| `ERROR: Docker daemon is not running` | Docker Desktop not started | Start Docker Desktop; wait for the whale icon to appear in the taskbar before retrying `make cluster-up` |
| `ERROR: docker is not installed or not on PATH` | Docker CLI not on PATH | Ensure Docker Desktop is installed and that "Add Docker to PATH" was selected during install |
| `ImagePullBackOff` on the `registry-verify` pod | containerd mirror not patched on cluster nodes (`hosts.toml` missing) | Re-run `make cluster-up` — the script is idempotent; it re-applies the `hosts.toml` patch to every node and retries the verify pod |
| `bad interpreter: No such file or directory` when running scripts | CRLF line endings in shell scripts | Run `git config core.autocrlf false` and re-checkout the affected file (`git checkout scripts/cluster-setup.sh`). The `.gitattributes` file enforces LF on every clone, so this only appears if autocrlf was set to `true` before cloning. |
| `/health` returns `503` or connection refused immediately after `make deploy` | MongoDB pod not Ready yet — Helm `--wait` covers the app pod but MongoDB can take 15–30 s extra | Wait 30 s, then run `kubectl get pods`; once the `-mongodb` pod shows `1/1 Running`, retry the request |
| `kubectl port-forward` dies silently / `Connection refused` on `localhost:8080` | A stale `kubectl port-forward` process is still holding the port | Run `pkill -f "kubectl port-forward"` (WSL2) to kill any orphaned forward, then retry. Stock Git Bash ships no `pkill` — find the PID with `netstat -ano \| grep :8080` and force-kill it with `taskkill //PID <pid>` instead. `make smoke` runs the `pkill` guard automatically only where `pkill` exists (WSL2); on stock Git Bash it prints a note and skips the cleanup. |
| `make smoke` fails with `FAIL /health → 000` | port-forward did not start in time | Increase the `sleep 3` in the `smoke` target to `sleep 5` for slower machines, or run `make port-forward` in one terminal and `curl` manually in another |
| `helm upgrade --install` fails with `ImagePullBackOff` on the app pod | Image not pushed to the local registry before deploy | Run `make build && make load` before `make deploy`, or use `make up` which chains all four steps |
| `no such host: kind-registry` inside the cluster pod | Registry container not connected to the kind Docker network | Re-run `make cluster-up`; step 4 of the script connects `kind-registry` to the `kind` Docker network if it is not already attached |
| `kubectl port-forward` dies silently / `Connection refused` on `localhost:8081` (launchpad) | A stale `kubectl port-forward svc/launchpad` process is still holding port 8081 — sometimes a native Windows `kubectl.exe` started from another Git Bash shell isn't reached by `pkill -f` | Run `pkill -f "kubectl port-forward svc/launchpad"` (WSL2) to kill any orphaned forward, then retry. `make smoke-launchpad` runs this guard automatically only where `pkill` exists (WSL2); stock Git Bash ships no `pkill`, so the target prints a note and skips the cleanup. If `pkill` is unavailable or the port is still held, find the PID with `netstat -ano \| grep :8081` and force-kill it with `taskkill //PID <pid>` |
| `localhost:8081` returns `503` / connection refused right after `make deploy-launchpad` (or `make up-all`) | The `launchpad-mongodb` pod is not Ready yet — Helm `--wait` covers the launchpad app pod but its in-chart MongoDB can take 15–30 s extra | Wait 30 s, then run `kubectl get pods`; once the `launchpad-mongodb` pod shows `1/1 Running`, retry `curl http://localhost:8081/health` |

## See Also

- [docs/windows-setup.md](windows-setup.md) — Git Bash / WSL2 path issues and MSYS setup
- [docs/known-limitations.md](known-limitations.md) — out-of-scope items and known caveats
