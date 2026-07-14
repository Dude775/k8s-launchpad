---
phase: 10-makefile-integration-smoke-docs
reviewed: 2026-07-14T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - Makefile
  - README.md
  - docs/troubleshooting.md
  - docs/known-limitations.md
findings:
  critical: 1
  warning: 5
  info: 4
  total: 10
status: issues_found
fixes:
  fixed_at: 2026-07-14
  scope: critical_warning
  fixed: 6
  skipped: 0
  open_info: 4
---

# Phase 10: Code Review Report

**Reviewed:** 2026-07-14
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

Reviewed the Phase 10 Makefile targets (launchpad build/load/deploy/smoke, `up-all`,
`smoke-all`, `undeploy-launchpad`, `verify-ttl`, grouped help) and the restructured
README/troubleshooting/known-limitations docs. Cross-referenced Makefile claims against
`charts/launchpad/` (selectors, service names, credentials, TTL config) and both apps'
route definitions.

What checks out: smoke endpoint lists match actual Flask routes (`/`, `/health`,
`/api/status` for launchpad; `/health`, `/entries` for field-guide-api plus exporter
`/metrics`); the `verify-ttl` pod selector `app.kubernetes.io/name=launchpad-mongodb`
matches `launchpad.mongodb.selectorLabels` for the default release name; all five README
screenshots exist in `docs/screenshots/`; the "32 tests" claim is accurate (verified by
count); trap/`$$` escaping in smoke recipes is correct; `reset-local` fails closed when
non-interactive.

What does not: the headline `TTL_DEEP=1` mode of `verify-ttl` is mathematically incapable
of passing against the default deployment (7-day TTL vs. 90-second wait), and several
robustness claims (check-tools version printing, pkill guards on Git Bash, help grouping)
were verified false on the primary supported shell.

## Critical Issues

### CR-01: `verify-ttl TTL_DEEP=1` can never pass against a default deployment — probe is inserted with `ts: new Date()` but the TTL is 7 days

**Status:** FIXED — commit `eb0ecdd`. Probe `ts` is now backdated past the index's live `expireAfterSeconds` (+120s); `make verify-ttl TTL_DEEP=1` verified PASSING twice against the live cluster, probe auto-removed by the TTL monitor (count 0 after run). `docs/known-limitations.md` rewritten to describe the backdated-probe mechanism; stale `values.yaml:40-41` "smoke overrides" comment corrected.

**File:** `Makefile:95-112` (probe insert at `Makefile:97-98`)
**Issue:** The deep mode inserts a probe with `ts: new Date()` (now) and polls for its
deletion for at most 90 seconds (`for i in $$(seq 1 18); do sleep 5;`). MongoDB's TTL
monitor deletes a document only when `ts + expireAfterSeconds < now`. The deployed
`expireAfterSeconds` comes from `EVENTS_TTL_SECONDS`, which defaults to **604800 (7 days)**
in both `apps/launchpad/app/config.py:55` and `charts/launchpad/values.yaml:42` — and
nothing in this target (or `up-all`) overrides it to a short value. The comment in
`values.yaml:40-41` ("smoke overrides to a short value to verify expiry") describes an
override that does not exist anywhere in the Makefile. Result: `make verify-ttl TTL_DEEP=1`
deterministically prints `FAIL  probe document not expired within 90s` and exits 1 on every
correctly-functioning deployment. As a side effect, the failed probe document remains
visible in the dashboard activity feed for 7 days. `docs/known-limitations.md:94-96`
advertises this mode as "a real insert-and-wait round-trip ... closes the Phase 9 FEED-03
'verify live' flag" — the flag is not closed; the deep path has never been able to succeed.
**Fix:** Backdate the probe past the index's actual TTL so the next TTL-monitor pass
(≤60s cycle) removes it; the existing 90s poll then suffices:
```make
kubectl exec $$POD -- mongosh --quiet -u root -p launchpad-dev-password --authenticationDatabase admin launchpad \
  --eval 'var ttl = db.events.getIndexes().filter(function(i){ return "expireAfterSeconds" in i; })[0].expireAfterSeconds; db.events.insertOne({type: "ttl-deep-probe", service_name: null, ts: new Date(Date.now() - (ttl + 120) * 1000)})' >/dev/null; \
```
Alternatively, temporarily deploy with a short TTL (`--set config.eventsTtlSeconds=30`) as
the values.yaml comment implies — but the backdated-probe approach avoids a redeploy and
tests the real production index.

## Warnings

### WR-01: MongoDB root password hardcoded three times in `verify-ttl` — breaks the documented password-override path

**Status:** FIXED — commit `ffc104e`. Credentials now read once from the in-cluster Secret (`kubectl get secret $(LP_RELEASE)-mongodb` + `base64 -d`) with a fail-fast check, referenced via `$$MONGO_USER`/`$$MONGO_PASS` in all three exec calls; zero occurrences of the literal password remain in the Makefile. Verified live (default and TTL_DEEP modes).

**File:** `Makefile:91, 97, 102`
**Issue:** `-u root -p launchpad-dev-password` is inlined in all three `kubectl exec`
invocations. `docs/known-limitations.md:44-46` explicitly instructs users to override the
password (`--set mongodb.auth.password=<real-password>`); anyone who follows that
instruction gets an authentication failure from `verify-ttl` that is then misreported as
"FAIL no TTL index on events.ts" (see IN-02). It also violates the project rule "no
hardcoded secrets" in spirit — even a committed dev credential should have a single
source of truth, not three copies.
**Fix:** Read the credential from the in-cluster Secret (single source of truth, survives
overrides), or at minimum hoist to overridable variables:
```make
LP_MONGO_PASS = $$(kubectl get secret launchpad-mongodb -o jsonpath='{.data.MONGO_INITDB_ROOT_PASSWORD}' | base64 -d)
```
or `LP_MONGO_USER ?= root` / `LP_MONGO_PASSWORD ?= launchpad-dev-password` at the top of
the Makefile and reference `$(LP_MONGO_PASSWORD)` in the recipe.

### WR-02: `check-tools` prints error strings instead of versions for helm and kubectl

**Status:** FIXED — commit `60a1f44`. Per-tool `case` dispatch (`helm version --short`, `kubectl version --client`, `kind version`, `--version` for the rest); verified live — all five tools print clean version strings.

**File:** `Makefile:153`
**Issue:** The loop runs `$$tool --version` for every tool, but helm and kubectl do not
support a `--version` flag. Verified live on this host:
`helm --version` → `Error: unknown flag: --version`; `kubectl --version` →
`error: unknown flag: --version`. Because stderr is captured (`2>&1`) and the exit code of
the command substitution is ignored, the target prints
`ok  helm  (Error: unknown flag: --version)` — the target's stated purpose ("verify
required tools ... and print versions", also promised in README:83) is broken for 2 of 5
tools, and the `ok` + error-text combination is actively confusing.
**Fix:** Use per-tool version commands instead of a uniform flag:
```make
for tool in docker kind helm kubectl bash; do \
  if command -v $$tool >/dev/null 2>&1; then \
    case $$tool in \
      helm)    VER=$$(helm version --short 2>&1 | head -1) ;; \
      kubectl) VER=$$(kubectl version --client 2>&1 | head -1) ;; \
      kind)    VER=$$(kind version 2>&1 | head -1) ;; \
      *)       VER=$$($$tool --version 2>&1 | head -1) ;; \
    esac; \
    echo "  ok  $$tool  ($$VER)"; \
  ...
```

### WR-03: `pkill` does not exist in Git Bash — the stale-port-forward guard is a silent no-op on the primary supported shell

**Status:** FIXED — commit `ed8653b`. Both smoke targets now gate on `command -v pkill` and print an explicit note (pointing at docs/troubleshooting.md) when absent; troubleshooting row for :8080 gained the `netstat -ano`/`taskkill //PID` fallback and both rows now state the guard runs automatically only where `pkill` exists (WSL2). Verified live via `make smoke-all` on Git Bash (note printed, all endpoints PASS).

**File:** `Makefile:67, 167`; `docs/troubleshooting.md:15, 19`
**Issue:** README:75 declares Git Bash the primary supported shell, but Git for Windows
ships no `pkill` (verified on this host: `command -v pkill` → not found, `uname` →
MINGW64). In `smoke` and `smoke-launchpad`, `pkill -f ... 2>/dev/null || true` degrades to
a silent no-op, so the stale-forward cleanup these targets advertise never happens on Git
Bash. Worse, `docs/troubleshooting.md:15` prescribes `pkill -f "kubectl port-forward"` as
the fix for the port-8080 symptom with no fallback — a command the primary-shell user
cannot run. (Line 19 for port 8081 does provide the `netstat`/`taskkill //PID` fallback;
line 15 does not, and both lines claim the smoke targets "do this automatically", which is
untrue on Git Bash.)
**Fix:** In the Makefile, gate on availability and warn:
`command -v pkill >/dev/null && pkill -f "kubectl port-forward svc/$(RELEASE)" 2>/dev/null || true`
plus a note in the recipe echo when pkill is absent. In `troubleshooting.md:15`, add the
same `netstat -ano | grep :8080` + `taskkill //PID <pid>` fallback that line 19 has, and
soften the "does this automatically" claim to note it requires `pkill` (WSL2) and is a
no-op in stock Git Bash.

### WR-04: `up`, `up-all`, and `smoke-all` encode strict ordering via prerequisite lists — broken under `make -j`

**Status:** FIXED — commit `3d62c08`. `.NOTPARALLEL:` added near the top with an explanatory comment; `make -j4 -n up-all` verified working.

**File:** `Makefile:138, 140, 146`
**Issue:** `up-all: up build-launchpad load-launchpad deploy-launchpad` relies on Make's
serial left-to-right prerequisite evaluation. Under `make -j` (or `MAKEFLAGS=-j` in the
environment), the four prerequisites run in parallel: `deploy-launchpad` can execute before
`build-launchpad`/`load-launchpad` finish, and before `up` has created the cluster —
yielding `ImagePullBackOff` or a hard failure against a nonexistent cluster. Same defect in
`up` (line 138, pre-existing but in scope as the base of the new `up-all`). Since README
markets `make up-all` as the single entry command, this is a real failure mode for users
with parallel-make habits.
**Fix:** Add `.NOTPARALLEL:` near the top of the Makefile (simplest, this Makefile has no
parallelism to lose), or chain explicitly in the recipe:
```make
up-all:
	$(MAKE) up
	$(MAKE) build-launchpad
	$(MAKE) load-launchpad
	$(MAKE) deploy-launchpad
```

### WR-05: Duplicate `##@ field-guide-api` section — help output prints the header twice and README's claimed grouping doesn't match

**Status:** FIXED — commit `1bc51a7`. Target blocks reordered into Cluster / field-guide-api / launchpad / Stack / Housekeeping (recipes byte-identical — sorted-diff against HEAD showed only the duplicate header removed and `##@ Stack` added); `up`/`up-all`/`smoke-all`/`check-tools` now live under `##@ Stack`; README:114 updated to match the real `make help` output (verified live).

**File:** `Makefile:32, 121`; `README.md:113-114`
**Issue:** `##@ field-guide-api` appears at both line 32 (above `test`) and line 121
(above `build`/`load`/`deploy`/`undeploy`/`up`/`up-all`/`smoke-all`/`check-tools`/
`port-forward`/`smoke`). `make help` therefore prints a "field-guide-api" section header
twice, with the cross-app targets (`up-all`, `smoke-all`, `check-tools`) miscategorized
under it. README:113-114 claims targets are "grouped by Cluster / field-guide-api /
launchpad / Housekeeping" — the actual output order is field-guide-api, launchpad, Cluster,
field-guide-api (again), Housekeeping. For a project whose README lists "Self-documenting
DX" as a headline feature, the flagship `make help` output is wrong.
**Fix:** Consolidate all field-guide-api targets under one `##@ field-guide-api` header,
and move `up`, `up-all`, `smoke-all`, `check-tools` under a new `##@ Stack` (or
`##@ Aggregate`) section. Update README:114 to match the final grouping.

## Info

> Fix scope was Critical + Warning only — IN-01 through IN-04 remain OPEN (not addressed).

### IN-01: `verify-ttl` index check matches any TTL index on `events`, not specifically the `ts` index

**File:** `Makefile:91-94`
**Issue:** `grep -q expireAfterSeconds` over `JSON.stringify(db.events.getIndexes())`
passes if any index on the collection carries `expireAfterSeconds`, yet the PASS message
asserts "events.ts TTL index present". A future non-ts TTL index would mask loss of the ts
index.
**Fix:** Assert on the specific index in the eval instead of grep:
`--eval 'quit(db.events.getIndexes().some(function(i){ return i.key && i.key.ts === 1 && "expireAfterSeconds" in i; }) ? 0 : 1)'`.

### IN-02: `verify-ttl` misattributes exec/auth failures as "no TTL index"

**File:** `Makefile:91-94`
**Issue:** If `kubectl exec` fails (pod not Ready, container restarting, wrong password
after an override — see WR-01), the pipeline output is empty, grep fails, and the target
prints `FAIL  no TTL index on events.ts` — a wrong diagnosis. The pod lookup at line 89
also takes `.items[0]` with no `--field-selector=status.phase=Running`, so during a
Recreate rollout it can select the terminating pod.
**Fix:** Add `--field-selector=status.phase=Running` to the `kubectl get pods` call and
capture the mongosh output into a variable first, distinguishing "exec failed" from "index
missing" in the FAIL message.

### IN-03: README architecture diagram omits the launchpad app the README is now built around

**File:** `README.md:32-42`
**Issue:** The v1.1 README restructure makes the launchpad dashboard the headline
(`make up-all`, demo-flow section, screenshots), but the mermaid diagram still shows only
`make up` → field-guide-api pod + one MongoDB. The launchpad pod, its own MongoDB, and the
launchpad→field-guide-api status probe are absent.
**Fix:** Add `launchpad pod` and `launchpad MongoDB` nodes (and the `up-all` entry) to the
diagram, or retitle it "field-guide-api build-to-deploy loop".

### IN-04: Fixed `sleep 3` before curl in smoke targets is a known race with no retry

**File:** `Makefile:71, 171`
**Issue:** Both smoke targets wait a fixed 3 seconds for the port-forward, then curl once
per endpoint. On slow machines the first curl returns `000` and the run fails —
acknowledged in `docs/troubleshooting.md:16`, whose remedy is "edit the Makefile". A retry
loop makes the documented failure mode disappear.
**Fix:** Replace the single curl with bounded retries, e.g.
`CODE=$$(curl -s --retry 5 --retry-connrefused --retry-delay 1 -o /dev/null -w '%{http_code}' ...)`
(curl ≥7.52), or an `until`/`for` readiness poll on the first endpoint before the loop.

---

_Reviewed: 2026-07-14_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
