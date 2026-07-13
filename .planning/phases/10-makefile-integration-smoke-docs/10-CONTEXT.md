# Phase 10: Makefile Integration + Smoke + Docs - Context

**Gathered:** 2026-07-13
**Status:** Ready for planning

<domain>
## Phase Boundary

`make up-all` brings up the kind cluster and deploys BOTH apps (field-guide-api +
launchpad) end-to-end in a single command; `make smoke-launchpad` proves the dashboard
reachable (200 on `/`, `/health`, `/api/status` at `localhost:8081`, field-guide-api
untouched on `8080`); `make help` lists all six launchpad targets alongside the existing
ones; the README headline demo becomes the browser flow (`make up-all` → open
`http://localhost:8081`) with real captured screenshots, existing Docker/Helm docs intact.

Requirements: DEP-04, DEP-05, DOCS-01. This is the final v1.1 phase — it fills the
guarded Makefile stubs created in Phase 5 (D-08) in place and wraps the manual deploy
loop live-verified in Phase 8 (D-09).

Out of scope: any real deployment pipeline behind the onboard form (PLAT-01, later PRD),
ArgoCD/observability (PRD-2/4), changes to app code or charts beyond what the demo flow
requires.

</domain>

<decisions>
## Implementation Decisions

### up-all composition + Makefile shape (DEP-04/05)
- **D-01:** `up-all: up build-launchpad load-launchpad deploy-launchpad` — reuses the
  proven v1.0 `up` aggregate untouched, then chains the launchpad trio. Smoke stays a
  separate explicit step (matches v1.0 where `up` doesn't auto-smoke). `up` itself
  remains field-guide-only (Phase 5 D-09 honored).
- **D-02:** `deploy-launchpad` mirrors `deploy` exactly: `helm upgrade --install
  $(LP_RELEASE) $(LP_CHART) --set image.repository=$(LP_IMAGE) --set image.tag=$(LP_TAG)
  --wait --timeout 180s`. With Phase 9's in-chart Mongo the pod reaches Ready, so
  `--wait` blocks until the readinessProbe passes and smoke can run immediately after.
- **D-03:** Housekeeping targets get full launchpad parity: add `undeploy-launchpad`,
  extend `clean-venv` to remove both apps' `.venv`s, and `reset-local` undeploys BOTH
  releases before `cluster-down` — teardown symmetric with up-all.
- **D-04:** `make help` moves to grouped sections using the standard `##@ Section` awk
  pattern (e.g. Cluster / field-guide-api / launchpad / Housekeeping) — reviewer-friendly
  with ~20 targets. SC #3 (all six launchpad targets listed with one-line descriptions,
  field-guide targets not displaced) still holds.

### smoke-launchpad + TTL verification (DEP-05, FEED-03 flag from Phase 9)
- **D-05:** `smoke-launchpad` is a near-copy of the proven v1.0 `smoke` recipe pointed at
  launchpad: pkill stale forwards → background `kubectl port-forward svc/$(LP_RELEASE)
  8081:80` → curl `/`, `/health`, `/api/status` expecting 200 → PASS/FAIL summary → trap
  cleanup. HTTP checks only — fast and deterministic.
- **D-06:** Add a `smoke-all: smoke smoke-launchpad` aggregate — one command proves both
  apps after up-all.
- **D-07:** The Phase 9 live-TTL flag ("TTL expiry verified live via smoke, not unit
  tests") is satisfied by a SEPARATE dedicated target (e.g. `verify-ttl`), kept out of
  the regular smoke path. It is tiered: the default run asserts the `expireAfterSeconds`
  index exists on the `events` collection (kubectl exec into launchpad's Mongo pod →
  mongosh `getIndexes`, echo the value — seconds, deterministic); an opt-in flag
  (e.g. `TTL_DEEP=1`) runs the slow real-expiry round-trip using Phase 9's
  configurable-TTL seam (insert doc with short TTL, poll until Mongo's ~60s TTL monitor
  deletes it).

### Demo access path
- **D-08:** Reviewer flow: `make up-all`, then `make port-forward-launchpad` in a second
  terminal (foreground `kubectl port-forward svc/$(LP_RELEASE) 8081:80`, Ctrl-C to stop),
  then open `http://localhost:8081` — exact mirror of the v1.0 port-forward pattern. No
  backgrounded combined port-forward target.
- **D-09:** `up-all` ends with a short 3-4 line echo epilogue pointing at
  `make port-forward-launchpad`, the browser URL `http://localhost:8081`, and
  `make smoke-all` — Helm NOTES.txt spirit; the demo is self-guiding from one command.

### README + screenshots + docs (DOCS-01)
- **D-10:** README restructure = new headline, keep body: rewrite the intro + Quickstart
  around the browser demo (up-all → port-forward-launchpad → localhost:8081); the
  field-guide curl flow moves to a "Developer loop / API workload" section below.
  Architecture, Security Note, Troubleshooting pointers, Known Limitations sections stay.
- **D-11:** Capture REAL screenshots now during the live demo — dashboard landing,
  catalog + onboard form, diagnostics, feed — stored in `docs/screenshots/` and embedded
  in the README. The repo is visually demoable on GitHub without running anything.
- **D-12:** docs/ pages get targeted launchpad updates where they genuinely apply:
  `docs/troubleshooting.md` (port 8081 conflicts, launchpad pod NotReady → Mongo, stale
  port-forwards), `docs/known-limitations.md` (committed local-dev Mongo password, WR-01
  committed local-dev `mongoUri` hostname/credentials as chart defaults, TTL timing verified
  live only). No rewrite of `docs/windows-setup.md`.
  *(Amended 2026-07-13 during plan verification: the original D-12 listed a "WR-01 degraded-CSS
  gap" inherited from a stale PROJECT.md tech-debt note, but that CSS gap was already FIXED in
  Phase 7 — commit `c977206` added the `.status-card--ok/--degraded/--unknown` rules to
  `apps/launchpad/app/static/style.css:101-109`. Retargeted to the genuinely open WR-01 from the
  Phase 9 review/verification: `charts/launchpad/values.yaml:72` embeds a local-dev hostname and
  credentials in the `mongoUri` default — documented as an accepted local-dev limitation, not
  production secrets.)*
- **D-13:** Fix the known cosmetic debt while re-capturing README output: the `/health`
  example must show Flask's real spaced JSON, not compact JSON. All captured outputs in
  the new README are real, not typed. (Closes the PROJECT.md tech-debt note.)

### Locked by ROADMAP success criteria (not re-decided here)
- `make up-all` completes without error in Git Bash, bringing up cluster + both apps (SC #1)
- `smoke-launchpad` → 200 on `/`, `/health`, `/api/status` from `localhost:8081`;
  field-guide-api stays on `localhost:8080`, no port collision (SC #2)
- `make help` lists all six launchpad targets with one-line descriptions (SC #3)
- README headline demo = `make up-all` → open `http://localhost:8081`, screenshots plan,
  existing Docker/Helm setup docs intact (SC #4)

### Claude's Discretion
- Exact name of the TTL target (`verify-ttl` vs `smoke-ttl`) and the deep-mode flag name.
- Exact `##@` section names/ordering in help, epilogue wording, PASS/FAIL formatting.
- `build-launchpad`/`load-launchpad` bodies (obvious mirrors of `build`/`load` with
  `LP_IMAGE`/`LP_TAG`).
- Screenshot filenames, exact shot framing, and whether a short shot-list note
  accompanies them in docs/.
- Which specific troubleshooting entries earn inclusion beyond the listed ones.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase spec & requirements
- `.planning/ROADMAP.md` §"Phase 10: Makefile Integration + Smoke + Docs" — goal + 4 success criteria (the locked contract)
- `.planning/REQUIREMENTS.md` — DEP-04, DEP-05, DOCS-01 (full requirement text + traceability)

### The files this phase edits in place
- `Makefile` — the six guarded launchpad stubs (Phase 5) to fill in place; `IMAGE/TAG/RELEASE/CHART` + `LP_*` variable conventions; the proven `smoke`, `deploy`, `up`, `help` (awk), `reset-local`, `clean-venv` recipes to mirror/extend
- `README.md` — current 170-line structure (headline quickstart to restructure per D-10; `/health` compact-JSON debt per D-13)
- `docs/troubleshooting.md`, `docs/known-limitations.md` — targeted launchpad additions (D-12)

### Prior phase contracts honored here
- `.planning/phases/05-monorepo-scaffold-app-factory/05-CONTEXT.md` — D-08/D-09: guarded stubs filled in place, `up` never gains launchpad deps (up-all is the aggregate)
- `.planning/phases/08-helm-chart-k8s-diagnostics/08-CONTEXT.md` — D-07 image convention `localhost:5001/launchpad`, D-09 manual deploy loop these targets wrap
- `.planning/phases/09-service-catalog-events-mongodb-crud/09-CONTEXT.md` — D-10 TTL configurable seam + "verified live via smoke" flag that D-07 (this phase) resolves; in-chart Mongo that makes `--wait` viable (D-02)

### Deploy surface
- `charts/launchpad/` — the chart `deploy-launchpad` installs (values.yaml image repo/tag seam; Service name for port-forward/smoke)
- `apps/launchpad/Dockerfile` — build context for `build-launchpad`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Makefile` `smoke` target: complete background-port-forward + curl + trap-cleanup recipe — `smoke-launchpad` is a near-copy at `svc/launchpad 8081:80` with `/`, `/health`, `/api/status`
- `Makefile` `deploy` target: `helm upgrade --install --set image.* --wait --timeout 180s` shape — `deploy-launchpad` mirrors with `LP_*` vars
- `Makefile` `help` awk one-liner: extend with the standard `##@` section-header pattern (D-04)
- `docs/` directory: troubleshooting/known-limitations pages already exist — extend, don't create new structure

### Established Patterns
- `SHELL := /bin/bash` + `export MSYS_NO_PATHCONV=1` + POSIX-safe recipes — all new targets must work in Git Bash on Windows (SC #1 is Git Bash-anchored)
- `$$` for shell vars inside recipes; `##`-comment help convention on every target
- Many small lowercase conventional commits
- README convention: captured outputs are real terminal output (v1.0 discipline; D-13 re-affirms)

### Integration Points
- The six stub targets (`build-launchpad` … `smoke-launchpad`) already exist in `.PHONY` and `make help` — bodies are replaced in place, no new target names for the six
- New aggregate targets: `up-all`, `smoke-all`, `undeploy-launchpad`, TTL target — need `.PHONY` + `##`/`##@` annotations
- `charts/launchpad` values.yaml `image.repository`/`image.tag` seam receives `LP_IMAGE`/`LP_TAG` exactly as field-guide-api's chart does
- launchpad Service listens on port 80 in-cluster (mirrored chart) — port-forward maps `8081:80`

</code_context>

<specifics>
## Specific Ideas

- The demo moment to protect: a reviewer types ONE command (`make up-all`), reads the
  epilogue, port-forwards, and lands on a live dashboard at `http://localhost:8081` —
  then `make smoke-all` prints PASS lines for both apps.
- Screenshots make the GitHub repo self-demonstrating: dashboard, catalog + onboard form,
  diagnostics (in-cluster state visible), feed — captured from the real running cluster.

</specifics>

<deferred>
## Deferred Ideas

- Combined `port-forward-all` target (backgrounded forwards for both apps + stop target)
  — considered for demo access, rejected in favor of the simple foreground per-app
  pattern; revisit if the demo grows more apps.

</deferred>

---

*Phase: 10-Makefile Integration + Smoke + Docs*
*Context gathered: 2026-07-13*
