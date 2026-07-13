# Phase 10: Makefile Integration + Smoke + Docs - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-13
**Phase:** 10-Makefile Integration + Smoke + Docs
**Areas discussed:** up-all composition, smoke-launchpad scope, Demo access path, README + screenshots

---

## up-all composition

| Option | Description | Selected |
|--------|-------------|----------|
| up + launchpad trio | `up-all: up build-launchpad load-launchpad deploy-launchpad`; smoke stays separate | ✓ |
| Full chain incl. smoke | up-all also runs smoke + smoke-launchpad at the end | |
| Independent chain | up-all lists all 7 prerequisite targets explicitly without depending on `up` | |

**User's choice:** up + launchpad trio (recommended)

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, mirror deploy | `--wait --timeout 180s`, identical shape to field-guide `deploy` | ✓ |
| No --wait | Return immediately after helm install | |
| You decide | Planner's call | |

**User's choice:** deploy-launchpad mirrors deploy with `--wait --timeout 180s`

| Option | Description | Selected |
|--------|-------------|----------|
| Full parity | undeploy-launchpad + clean-venv both venvs + reset-local undeploys both releases | ✓ |
| Minimal — SC only | Only the six required targets + up-all | |
| You decide | Planner picks | |

**User's choice:** Full housekeeping parity

| Option | Description | Selected |
|--------|-------------|----------|
| Grouped sections | `##@ Section` awk headers (Cluster / field-guide-api / launchpad / Housekeeping) | ✓ |
| Keep flat | Current one-line-per-target listing in file order | |
| You decide | Planner's call | |

**User's choice:** Grouped help sections

---

## smoke-launchpad scope

| Option | Description | Selected |
|--------|-------------|----------|
| No — HTTP checks only | smoke-launchpad stays 200-checks only; TTL documented as manual check | |
| Yes — fold TTL check in | smoke-launchpad also verifies the events TTL index | |
| Separate target | Dedicated TTL verification target kept out of the regular smoke path | ✓ |

**User's choice:** Separate TTL target

| Option | Description | Selected |
|--------|-------------|----------|
| Index presence | kubectl exec + mongosh getIndexes, assert expireAfterSeconds | |
| Real expiry round-trip | Insert doc with short TTL, poll until deleted (~1-2 min) | |
| Both, tiered | Default = index presence; opt-in flag runs the slow round-trip | ✓ |

**User's choice:** Both, tiered (default index presence; `TTL_DEEP=1`-style flag for real expiry)

| Option | Description | Selected |
|--------|-------------|----------|
| Yes to both | `smoke-all: smoke smoke-launchpad`; smoke-launchpad near-copies v1.0 smoke mechanics | ✓ |
| No smoke-all | Keep the two smokes separate | |
| You decide | Planner's call on the aggregate | |

**User's choice:** smoke-all aggregate + v1.0 smoke mechanics mirrored

---

## Demo access path

| Option | Description | Selected |
|--------|-------------|----------|
| port-forward-launchpad | Second terminal, foreground, Ctrl-C to stop — mirror of v1.0 pattern | ✓ |
| Combined port-forward-all | One target backgrounds both forwards (needs lifecycle mgmt) | |
| up-all ends with instructions | Epilogue only; access manual per-app | |

**User's choice:** `make port-forward-launchpad` in a second terminal

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, print epilogue | 3-4 line echo at end of up-all: port-forward-launchpad → URL → smoke-all | ✓ |
| No epilogue | README carries the instructions | |

**User's choice:** Yes — up-all prints a "what next" epilogue

---

## README + screenshots

| Option | Description | Selected |
|--------|-------------|----------|
| New headline, keep body | Intro + Quickstart rewritten around browser demo; curl flow moves down; rest stays | ✓ |
| Full rewrite | Restructure whole README around the two-app platform story | |
| Additive section only | Untouched README + a 'Dashboard demo' section near the top | |

**User's choice:** New headline, keep body

| Option | Description | Selected |
|--------|-------------|----------|
| Capture real screenshots now | Live-demo shots (dashboard, catalog+form, diagnostics, feed) into docs/screenshots/, embedded in README | ✓ |
| Plan document only | docs/screenshots-plan.md with placeholder embeds | |
| Plan + capture headline shot | Shot-list doc + one hero screenshot | |

**User's choice:** Capture real screenshots now

| Option | Description | Selected |
|--------|-------------|----------|
| Targeted updates | troubleshooting (8081 conflicts, NotReady→Mongo, stale forwards) + known-limitations (dev password, WR-01, TTL timing); windows-setup untouched | ✓ |
| README only | Leave docs/ pages as v1.0 artifacts | |
| You decide | Planner decides | |

**User's choice:** Targeted docs/ updates

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, fix it | Re-capture real /health spaced-JSON output; closes PROJECT.md tech-debt note | ✓ |
| Leave it | Out of the SC's letter | |

**User's choice:** Fix the /health compact-JSON cosmetic debt

---

## Claude's Discretion

- TTL target name (`verify-ttl` vs `smoke-ttl`) and deep-mode flag name
- Exact `##@` section names/ordering, epilogue wording, PASS/FAIL formatting
- `build-launchpad`/`load-launchpad` bodies (mirrors of `build`/`load` with LP_ vars)
- Screenshot filenames/framing; optional shot-list note in docs/
- Additional troubleshooting entries beyond those listed

## Deferred Ideas

- Combined `port-forward-all` target (backgrounded forwards + stop target) — rejected for
  v1.1; revisit if the demo grows more apps.
