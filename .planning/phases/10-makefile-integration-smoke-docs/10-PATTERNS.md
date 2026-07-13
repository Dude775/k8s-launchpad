# Phase 10: Makefile Integration + Smoke + Docs - Pattern Map

**Mapped:** 2026-07-13
**Files analyzed:** 6 (all edited in place, no new source files except docs/screenshots/)
**Analogs found:** 6 / 6

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `Makefile` — `build-launchpad` | config/utility (build script target) | request-response (docker CLI invocation) | `Makefile` `build` target (lines 69-70) | exact |
| `Makefile` — `load-launchpad` | config/utility | request-response | `Makefile` `load` target (lines 72-73) | exact |
| `Makefile` — `deploy-launchpad` | config/utility | request-response (helm CLI) | `Makefile` `deploy` target (lines 77-80) | exact |
| `Makefile` — `port-forward-launchpad` | config/utility | streaming (long-lived process) | `Makefile` `port-forward` target (lines 101-102) | exact |
| `Makefile` — `smoke-launchpad` | test | request-response (HTTP smoke checks) | `Makefile` `smoke` target (lines 104-121) | exact |
| `Makefile` — `test-launchpad` | test | batch | Already implemented (lines 41-46), mirrors `test` (lines 31-36) — no change needed, kept for context | exact (already done) |
| `Makefile` — `up-all` (new aggregate) | config/utility | batch (chained targets) | `Makefile` `up` target (line 85) | exact |
| `Makefile` — `smoke-all` (new aggregate) | test | batch | `Makefile` `up` target composition pattern + `smoke`/`smoke-launchpad` | role-match |
| `Makefile` — `undeploy-launchpad` (new) | config/utility | request-response | `Makefile` `undeploy` target (lines 82-83) | exact |
| `Makefile` — `verify-ttl` (new, name at Claude's discretion) | test | request-response (kubectl exec + mongosh) | `Makefile` `check-tools` (loop + PASS/FAIL echo, lines 87-99) + `smoke` (trap/cleanup shape) | role-match |
| `Makefile` — `help` (grouped `##@` rewrite) | config/utility | transform (awk parsing) | `Makefile` `help` awk one-liner (lines 27-29) | exact (extend in place) |
| `Makefile` — `clean-venv` (extend) | config/utility | file-I/O | `Makefile` `clean-venv` (line 130-131) | exact (extend in place) |
| `Makefile` — `reset-local` (extend) | config/utility | batch (destructive teardown) | `Makefile` `reset-local` (lines 133-140) | exact (extend in place) |
| `README.md` | documentation | transform (content restructure) | `README.md` itself — Quickstart/Demo Flow/Architecture sections (lines 64-128) | exact (self-analog, restructure in place) |
| `docs/troubleshooting.md` | documentation | transform | `docs/troubleshooting.md` existing table rows (lines 7-18) | exact (append rows) |
| `docs/known-limitations.md` | documentation | transform | `docs/known-limitations.md` existing `###` entries (lines 8-59) | exact (append section) |
| `docs/screenshots/` | asset directory | file-I/O | No existing analog — net-new directory | none (net-new, see "No Analog Found") |

## Pattern Assignments

### `Makefile` — `build-launchpad`, `load-launchpad`, `deploy-launchpad`, `undeploy-launchpad` (config/utility, request-response)

**Analog:** `Makefile` lines 69-83 (`build`, `load`, `deploy`, `undeploy`)

**Exact excerpt to mirror** (`E:\Genspark\k8s-launchpad\Makefile:69-83`):
```makefile
build: ## build the field-guide-api Docker image and tag it for the local registry
	docker build -t $(IMAGE):$(TAG) apps/field-guide-api

load: ## push the built image to the local kind registry (localhost:5001)
	docker push $(IMAGE):$(TAG)

# IMAGE/TAG are forwarded to the chart so build/load/deploy stay coordinated:
#   make build TAG=v1.0 && make load TAG=v1.0 && make deploy TAG=v1.0
deploy: ## install or upgrade the Helm release (idempotent; helm upgrade --install)
	helm upgrade --install $(RELEASE) $(CHART) \
		--set image.repository=$(IMAGE) --set image.tag=$(TAG) \
		--wait --timeout 180s

undeploy: ## remove the Helm release and all chart-owned resources
	helm uninstall $(RELEASE)
```

**Direct substitution for launchpad** — swap `$(IMAGE)/$(TAG)/$(RELEASE)/$(CHART)` for `$(LP_IMAGE)/$(LP_TAG)/$(LP_RELEASE)/$(LP_CHART)` (already declared at `Makefile:16-19`) and swap `apps/field-guide-api` for `apps/launchpad`:
```makefile
build-launchpad: ## build the launchpad Docker image and tag it for the local registry
	docker build -t $(LP_IMAGE):$(LP_TAG) apps/launchpad

load-launchpad: ## push the built launchpad image to the local kind registry (localhost:5001)
	docker push $(LP_IMAGE):$(LP_TAG)

deploy-launchpad: ## install or upgrade the launchpad Helm release (idempotent; helm upgrade --install)
	helm upgrade --install $(LP_RELEASE) $(LP_CHART) \
		--set image.repository=$(LP_IMAGE) --set image.tag=$(LP_TAG) \
		--wait --timeout 180s

undeploy-launchpad: ## remove the launchpad Helm release and all chart-owned resources
	helm uninstall $(LP_RELEASE)
```
This is CONTEXT.md D-02 verbatim — `--wait --timeout 180s` is viable because Phase 9 added in-chart Mongo so the readinessProbe passes before `--wait` returns.

---

### `Makefile` — `port-forward-launchpad` (config/utility, streaming)

**Analog:** `Makefile` lines 101-102 (`port-forward`)

```makefile
port-forward: ## forward svc/field-guide-api to localhost:8080 (Ctrl-C to stop)
	kubectl port-forward svc/$(RELEASE) 8080:80
```

**Direct substitution** (per D-08 — foreground, Ctrl-C to stop, no backgrounding):
```makefile
port-forward-launchpad: ## forward svc/launchpad to localhost:8081 (Ctrl-C to stop)
	kubectl port-forward svc/$(LP_RELEASE) 8081:80
```
Confirmed against `charts/launchpad/templates/service.yaml:12-17` — Service `port: 80` (from `values.yaml` `service.port: 80`), so `8081:80` is the correct mapping (mirrors field-guide-api's `8080:80`, only the local port changes to avoid the port collision SC #2 requires).

---

### `Makefile` — `smoke-launchpad` (test, request-response)

**Analog:** `Makefile` lines 104-121 (`smoke`)

**Full excerpt** (`E:\Genspark\k8s-launchpad\Makefile:104-121`):
```makefile
smoke: ## background port-forward, curl /health + /entries + /metrics, PASS/FAIL, cleanup
	@echo "==> Starting smoke test..."; \
	pkill -f "kubectl port-forward svc/$(RELEASE)" 2>/dev/null || true; \
	kubectl port-forward svc/$(RELEASE) 8080:80 &>/dev/null & \
	PF_PID=$$!; \
	trap "kill $$PF_PID 2>/dev/null || true" EXIT; \
	sleep 3; \
	STATUS=0; \
	for endpoint in health entries metrics; do \
	  CODE=$$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/$$endpoint); \
	  if [ "$$CODE" = "200" ]; then \
	    echo "  PASS  /$$endpoint → $$CODE"; \
	  else \
	    echo "  FAIL  /$$endpoint → $$CODE"; \
	    STATUS=1; \
	  fi; \
	done; \
	if [ $$STATUS -eq 0 ]; then echo "==> smoke PASSED"; else echo "==> smoke FAILED"; exit 1; fi
```

**Near-copy for launchpad** (per D-05) — swap port to 8081, svc name to `$(LP_RELEASE)`, endpoint list changes. Note: launchpad's endpoints are `/`, `/health`, `/api/status` (NOT bare word suffixes like `health`/`entries`/`metrics` — `/` and `/api/status` need explicit path handling since the analog's `for endpoint in ...; do curl .../$$endpoint` loop assumes a flat single-segment path):
```makefile
smoke-launchpad: ## background port-forward, curl /, /health, /api/status, PASS/FAIL, cleanup
	@echo "==> Starting launchpad smoke test..."; \
	pkill -f "kubectl port-forward svc/$(LP_RELEASE)" 2>/dev/null || true; \
	kubectl port-forward svc/$(LP_RELEASE) 8081:80 &>/dev/null & \
	PF_PID=$$!; \
	trap "kill $$PF_PID 2>/dev/null || true" EXIT; \
	sleep 3; \
	STATUS=0; \
	for endpoint in "" health api/status; do \
	  CODE=$$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8081/$$endpoint); \
	  if [ "$$CODE" = "200" ]; then \
	    echo "  PASS  /$$endpoint → $$CODE"; \
	  else \
	    echo "  FAIL  /$$endpoint → $$CODE"; \
	    STATUS=1; \
	  fi; \
	done; \
	if [ $$STATUS -eq 0 ]; then echo "==> launchpad smoke PASSED"; else echo "==> launchpad smoke FAILED"; exit 1; fi
```
Verified route existence: `apps/launchpad/app/routes/pages.py:36` (`@pages_bp.route("/", methods=["GET"])`), `apps/launchpad/app/routes/health.py:27` (`@health_bp.route("/health", ...)`), `apps/launchpad/app/routes/status.py:22` (`@status_bp.route("/api/status", ...)`) — all three confirmed GET, all expected 200.

**pkill guard note:** the analog's `pkill -f "kubectl port-forward svc/$(RELEASE)"` pattern only kills forwards matching the exact release name — safe to run alongside `smoke` without cross-killing field-guide-api's forward, since `$(LP_RELEASE)` (`launchpad`) is a distinct string from `$(RELEASE)` (`field-guide-api`).

---

### `Makefile` — `up-all`, `smoke-all` (aggregates, batch)

**Analog:** `Makefile` line 85 (`up`) for composition style:
```makefile
up: cluster-up build load deploy  ## bring up the full local stack (cluster-up → build → load → deploy)
```

**Per D-01/D-06, direct compositions:**
```makefile
up-all: up build-launchpad load-launchpad deploy-launchpad  ## bring up cluster + BOTH apps (up, then launchpad build/load/deploy)
	@echo ""
	@echo "==> up-all complete. Both apps deployed."
	@echo "==> Next: make port-forward-launchpad  (then open http://localhost:8081)"
	@echo "==> Then: make smoke-all"

smoke-all: smoke smoke-launchpad  ## smoke-test BOTH apps (field-guide-api on 8080, launchpad on 8081)
```
D-09's epilogue (3-4 lines, Helm NOTES.txt spirit) is placed as a trailing `@echo` block on `up-all` itself, matching the reviewer-self-guiding requirement. Reference `charts/launchpad/templates/NOTES.txt` for the "spirit" tone if a copy of its wording is useful (not read in full here — file exists at `charts/launchpad/templates/NOTES.txt`; Helm renders it post-install, this Makefile epilogue is the make-level equivalent).

---

### `Makefile` — `verify-ttl` (test, request-response via kubectl exec + mongosh)

**No direct analog exists** (first kubectl-exec-into-pod target in this Makefile) — compose from two existing shapes:

1. PASS/FAIL echo + loop pattern from `check-tools` (`Makefile:87-99`):
```makefile
check-tools: ## verify required tools are on PATH and print versions
	@echo "==> Checking required tools..."; \
	PASS=1; \
	for tool in docker kind helm kubectl bash; do \
	  if command -v $$tool >/dev/null 2>&1; then \
	    echo "  ok  $$tool  ($$($$tool --version 2>&1 | head -1))"; \
	  else \
	    echo "  MISSING  $$tool"; \
	    PASS=0; \
	  fi; \
	done; \
	if [ $$PASS -eq 0 ]; then echo "==> check-tools FAILED — install missing tools"; exit 1; fi; \
	echo "==> check-tools PASSED"
```

2. Mongo pod naming from `charts/launchpad/values.yaml:50-72` and `charts/launchpad/templates/mongodb/service.yaml` — the in-chart Mongo Deployment/Service/Secret are all named via the `launchpad.mongodb.fullname` helper, which for the default release name `launchpad` resolves to `launchpad-mongodb` (confirmed in `values.yaml:67`: `mongodb://root:launchpad-dev-password@launchpad-mongodb:27017/launchpad?authSource=admin...`). The Deployment's container is named `mongodb` (`charts/launchpad/templates/mongodb/deployment.yaml:35`).

**Composed target (D-07 tiered default — index existence check, deterministic):**
```makefile
verify-ttl: ## verify the TTL index exists on launchpad's events collection (deep round-trip: TTL_DEEP=1)
	@echo "==> Verifying events TTL index..."; \
	POD=$$(kubectl get pods -l app.kubernetes.io/name=launchpad-mongodb -o jsonpath='{.items[0].metadata.name}' 2>/dev/null); \
	if [ -z "$$POD" ]; then echo "==> verify-ttl FAILED — launchpad mongodb pod not found"; exit 1; fi; \
	kubectl exec $$POD -- mongosh --quiet -u root -p launchpad-dev-password --authenticationDatabase admin launchpad \
	  --eval 'JSON.stringify(db.events.getIndexes())' | grep -q expireAfterSeconds \
	  && echo "  PASS  events.ts TTL index present" \
	  || { echo "  FAIL  no TTL index on events.ts"; exit 1; }
	@if [ "$$TTL_DEEP" = "1" ]; then \
	  echo "==> TTL_DEEP=1: running live expiry round-trip (slow, ~60-90s)..."; \
	  : ; \
	fi
```
Note: pod selector label (`app.kubernetes.io/name=launchpad-mongodb` or similar) should be verified against `charts/launchpad/templates/_helpers.tpl` labels block during implementation — planner/implementer should Read `_helpers.tpl` to confirm the exact selector label emitted by `launchpad.mongodb.selectorLabels` before finalizing this target, since this pattern-mapper did not re-read that file (already covered enough ground with `values.yaml`/`service.yaml`/`deployment.yaml` naming references above). The `TTL_DEEP=1` deep-mode body (insert short-TTL doc, poll until Mongo's TTL monitor deletes it) is Claude's discretion per CONTEXT.md — no existing analog for a polling-loop target; compose from the `smoke` target's `sleep`+loop shape if needed.

---

### `Makefile` — `help` (grouped `##@` rewrite)

**Analog:** `Makefile` lines 27-29 (current flat awk one-liner):
```makefile
help: ## print this help message (default goal)
	@awk 'BEGIN {FS = ":.*##"; printf "Usage:\n  make \033[36m<target>\033[0m\n\nTargets:\n"} \
	  /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
```

**Standard `##@` grouped extension** (widely-used community pattern, e.g. from Carvel/Kubebuilder Makefiles) — add `##@ Section` markers above each target group and extend the awk script to recognize them:
```makefile
help: ## print this help message (default goal)
	@awk 'BEGIN {FS = ":.*##"; printf "Usage:\n  make \033[36m<target>\033[0m\n"} \
	  /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2 } \
	  /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)
```
Then annotate each existing target's preceding line with e.g. `##@ Cluster`, `##@ field-guide-api`, `##@ launchpad`, `##@ Housekeeping` (placed once per section, above the first target in that section) per D-04. This is an in-place edit to the SAME target — no new file, no new pattern category; only the awk script body and surrounding `##@` comment lines change.

---

### `Makefile` — `clean-venv`, `reset-local` (extend for launchpad parity)

**Analog:** `Makefile` lines 130-140:
```makefile
clean-venv: ## remove the app virtualenv (re-run 'make test' to recreate)
	rm -rf apps/field-guide-api/.venv

reset-local: ## DESTRUCTIVE — undeploy + destroy cluster + registry (loses all data)
	@echo "!!"
	@echo "!! WARNING: This removes the Helm release, kind cluster, and local registry."
	@echo "!! All in-cluster data (MongoDB PVC contents) will be lost."
	@echo "!!"
	@read -p "!! Type YES to continue: " confirm && [ "$$confirm" = "YES" ]
	$(MAKE) undeploy || true
	$(MAKE) cluster-down
```

**Extended for D-03 (both apps):**
```makefile
clean-venv: ## remove both apps' virtualenvs (re-run 'make test'/'make test-launchpad' to recreate)
	rm -rf apps/field-guide-api/.venv
	rm -rf apps/launchpad/.venv

reset-local: ## DESTRUCTIVE — undeploy BOTH releases + destroy cluster + registry (loses all data)
	@echo "!!"
	@echo "!! WARNING: This removes both Helm releases, the kind cluster, and the local registry."
	@echo "!! All in-cluster data (MongoDB PVC contents, both apps) will be lost."
	@echo "!!"
	@read -p "!! Type YES to continue: " confirm && [ "$$confirm" = "YES" ]
	$(MAKE) undeploy || true
	$(MAKE) undeploy-launchpad || true
	$(MAKE) cluster-down
```

---

### `Makefile` — `.PHONY` and variable declarations

**Analog:** `Makefile` lines 22-23 (existing `.PHONY` list, already includes the 6 stub names) plus the Phase-annotation comment convention on line 22:
```makefile
# ─── Targets ──────────────────────────────────────────────────────────────────
# Phase 1: test | Phase 2: cluster-up, cluster-down | Phase 3: build, load, deploy, undeploy | Phase 4: help, up, check-tools, port-forward, smoke, clean, clean-venv, reset-local | Phase 5: test-launchpad, build-launchpad, load-launchpad, deploy-launchpad, port-forward-launchpad, smoke-launchpad
.PHONY: test cluster-up cluster-down build load deploy undeploy help up check-tools port-forward smoke clean clean-venv reset-local test-launchpad build-launchpad load-launchpad deploy-launchpad port-forward-launchpad smoke-launchpad
```
Append `Phase 10: up-all, smoke-all, undeploy-launchpad, verify-ttl` to the comment and add those four names to `.PHONY` — matches the established "phase-annotated running list" convention exactly.

---

### `README.md` (documentation, transform)

**Analog:** the file's own existing structure — sections to restructure are self-contained; use the SAME section headers, just reordered/rewritten content (per D-10, "keep body" — Architecture/Security Note/Troubleshooting pointers/Known Limitations survive untouched).

**Headline + Quickstart restructure target** (currently `README.md:1-14` intro + `README.md:64-82` Quickstart) — rewrite the intro's "one command brings it all up" code fence and the Quickstart section to lead with:
```bash
make up-all
make port-forward-launchpad   # in a second terminal
# open http://localhost:8081
make smoke-all
```
replacing the current PRD-1-only framing:
```
make cluster-up && make build && make load && make deploy
```
(`README.md:12-14`, superseded — becomes the "Developer loop / API workload" section per D-10, not deleted).

**Demo Flow section rewrite target** (`README.md:96-128`) — currently field-guide-only port-forward + curl walkthrough with a "Screenshots (planned)" checklist (`README.md:125-128`):
```markdown
**Screenshots (planned):**
- [ ] Platform dashboard showing registered repos (PRD-3)
- [ ] Grafana dashboard with request-rate + error-rate panels (PRD-4)
- [ ] ArgoCD app health view with synced Helm release (PRD-2)
```
Per D-11, this checklist becomes REAL embedded screenshots (`docs/screenshots/dashboard.png` etc., exact filenames at Claude's discretion) using standard markdown image syntax `![alt](docs/screenshots/xxx.png)`, and the field-guide curl walkthrough (`README.md:104-123`) moves down into a new "Developer loop / API workload" section.

**`/health` compact-JSON fix (D-13)** — current cosmetic debt at `README.md:107-108`:
```
curl http://localhost:8080/health
# {"status":"ok","mongo":"up"}
```
Source route returns via `jsonify({"status": "ok", "mongo": "up"}), 200` (`apps/field-guide-api/app/routes/health.py:31`). Flask's `jsonify` is compact by default; the fix is to actually re-capture the REAL terminal output (which may still be compact unless `curl | python -m json.tool` or similar is used) — D-13 says "must show Flask's real spaced JSON, not compact JSON. All captured outputs in the new README are real, not typed." This implies either (a) the app config sets pretty-printing, or (b) the capture command pipes through a formatter. Planner/implementer should verify actual `/health` output when re-capturing live rather than assume a specific JSON layout — this is a live-capture correctness issue, not a Makefile/pattern issue.

**Repository Layout table** (`README.md:130-140`) — no analog changes needed; already generic. Do not touch unless launchpad app dir needs adding (check if `apps/launchpad/` and `charts/launchpad/` are already implicitly covered by the existing generic wording "e.g. `apps/field-guide-api/`" — likely fine as-is, but planner may add a launchpad example alongside).

---

### `docs/troubleshooting.md` (documentation, transform)

**Analog:** existing table format, `docs/troubleshooting.md:7-18` — every row follows `| Symptom | Likely Cause | Fix |`.

**Exact row-format to copy** (last row as the closest analog for a new port-forward-related row):
```markdown
| `kubectl port-forward` dies silently / `Connection refused` on `localhost:8080` | A stale `kubectl port-forward` process is still holding the port | Run `pkill -f "kubectl port-forward"` to kill any orphaned forward, then retry. `make smoke` does this automatically via its `pkill` guard at the start of the target. |
```

**New rows to append per D-12** (port 8081 conflicts, launchpad pod NotReady → Mongo, stale port-forwards for launchpad specifically) — follow the identical `| Symptom | Cause | Fix |` shape, referencing `make smoke-launchpad`'s own `pkill -f "kubectl port-forward svc/$(LP_RELEASE)"` guard (this phase's new target) the same way the existing row references `make smoke`'s guard. A NotReady-due-to-Mongo row should mirror the existing row at `docs/troubleshooting.md:14`:
```markdown
| `/health` returns `503` or connection refused immediately after `make deploy` | MongoDB pod not Ready yet — Helm `--wait` covers the app pod but MongoDB can take 15–30 s extra | Wait 30 s, then run `kubectl get pods`; once the `-mongodb` pod shows `1/1 Running`, retry the request |
```
adapted for launchpad's `launchpad-mongodb` pod name and `/health` endpoint at port 8081.

---

### `docs/known-limitations.md` (documentation, transform)

**Analog:** existing `###`-headed entries, e.g. `docs/known-limitations.md:31-44` (Committed Dev Password entry) — exact structure to mirror for the launchpad-specific password entry:
```markdown
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
```

**New entries to append per D-12** (committed launchpad-dev-password — note `charts/launchpad/values.yaml:56` already has `password: launchpad-dev-password` with the exact same discipline; WR-01 degraded-CSS gap; TTL timing verified live only per D-07/Phase 9). Mirror the exact `###` heading + prose + fenced warning + override command shape shown above, substituting `launchpad-dev-password` and `charts/launchpad`. The TTL entry should reference this phase's new `verify-ttl` target as the "verified live" evidence, closing the Phase 9 FEED-03 flag noted in `docs/known-limitations.md`'s pattern (no existing TTL entry yet — net new `###` block, same format).

---

## Shared Patterns

### `LP_*` variable namespace
**Source:** `Makefile:16-19`
```makefile
# launchpad image coordinates (namespaced LP_ prefix — never shadow field-guide-api)
LP_IMAGE   ?= localhost:5001/launchpad
LP_TAG     ?= dev
LP_RELEASE ?= launchpad
LP_CHART   ?= charts/launchpad
```
**Apply to:** every new/filled launchpad target (`build-launchpad`, `load-launchpad`, `deploy-launchpad`, `port-forward-launchpad`, `smoke-launchpad`, `undeploy-launchpad`, `verify-ttl`) — always use `$(LP_*)`, never hardcode `launchpad` string literals where a variable exists (exception: pod label selectors / mongo db name in `verify-ttl`, which are chart-internal names not exposed as Makefile vars).

### pkill-guard + background-port-forward + trap-cleanup
**Source:** `Makefile:104-121` (`smoke`)
**Apply to:** `smoke-launchpad` (exact structural copy, different svc/port/endpoints)

### Idempotent `helm upgrade --install --wait --timeout 180s`
**Source:** `Makefile:77-80` (`deploy`)
**Apply to:** `deploy-launchpad` (exact structural copy, different release/chart/image vars). Do NOT use `--atomic` (deprecated in Helm 4 per CLAUDE.md project instructions — renamed `--rollback-on-failure`); the existing `deploy` target already avoids it, so `deploy-launchpad` must too.

### PASS/FAIL echo convention
**Source:** `Makefile:87-99` (`check-tools`) and `Makefile:104-121` (`smoke`)
```
  PASS  /health → 200
  FAIL  /health → 000
==> smoke PASSED
==> smoke FAILED
```
**Apply to:** `smoke-launchpad`, `smoke-all` (aggregate simply chains, no new echo format needed), `verify-ttl`.

### `##`-comment help convention + phase-annotated `.PHONY` list
**Source:** `Makefile:22-23` and every target's trailing `## description` comment
**Apply to:** all new targets (`up-all`, `smoke-all`, `undeploy-launchpad`, `verify-ttl`) must have a one-line `##` comment (feeds `make help`) and must be added to `.PHONY`.

### Docs cross-linking convention
**Source:** `docs/troubleshooting.md:20-23` ("See Also" footer) and `docs/known-limitations.md:61-64`
**Apply to:** no new cross-link sections needed — existing "See Also" footers in both docs already reference each other and README; just ensure new content is placed inside the existing table/section structure, not as separate new footer links.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `docs/screenshots/` (new directory + image files) | asset | file-I/O | No existing screenshots directory or image assets in the repo; this is a net-new directory per D-11. Planner should treat this as: create directory, capture real PNGs during live demo, embed via markdown `![alt](docs/screenshots/name.png)` in README. No code pattern to copy — this is a manual capture step, not a code-generation step. |
| `Makefile` `verify-ttl` deep-mode (`TTL_DEEP=1` real polling round-trip) | test | event-driven (poll-until-condition) | No existing polling-loop target in the Makefile (closest is `smoke`'s single `sleep 3`, not a poll loop). Compose from RESEARCH-free first principles per Claude's Discretion (CONTEXT.md) — a `while` loop with `mongosh --eval` re-checks + short `sleep` + max-iteration bound is the standard shape; no in-repo precedent to copy verbatim. |

## Metadata

**Analog search scope:** `Makefile` (full file, 141 lines), `README.md` (full file, 170 lines), `docs/troubleshooting.md`, `docs/known-limitations.md`, `charts/launchpad/values.yaml`, `charts/launchpad/templates/service.yaml`, `charts/launchpad/templates/mongodb/*.yaml`, `apps/launchpad/app/routes/{health,status,pages}.py`, `apps/launchpad/app/events.py`, `apps/launchpad/Dockerfile`, `apps/field-guide-api/app/routes/health.py`, `.planning/phases/09-service-catalog-events-mongodb-crud/09-CONTEXT.md`
**Files scanned:** 17
**Pattern extraction date:** 2026-07-13
