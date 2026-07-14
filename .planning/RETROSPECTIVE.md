# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — Foundation

**Shipped:** 2026-07-07
**Phases:** 4 | **Plans:** 12 | **Sessions:** multiple (4-day span, 114 commits)

### What Was Built
- Flask field-guide API (app factory, MongoDB CRUD, /health readiness, /metrics seam) with 32 tests at 100% coverage
- Idempotent kind + registry:3 cluster infrastructure with self-verifying push/pull wiring
- Multi-stage non-root gunicorn image + lint-clean Helm chart with embedded mongo:7 manifests
- Self-documenting Makefile developer CLI (15 targets) + portfolio-grade README and docs/ pages
- Live-verified `make up` → `make smoke` end-to-end loop, human-approved (MAKE-02 core value)

### What Worked
- Research-before-plan caught real-world traps early: Bitnami paywall (avoided ImagePullBackOff), CRLF/Git Bash pitfalls, registry:3 hosts.toml pattern — zero mid-phase stack reversals
- Blocking human-verify checkpoints on live-loop plans (03-04, 04-03) kept "it works" honest — captured real terminal output instead of claimed output
- Verification-only plans (no source changes) as phase closers proved the milestone core value directly
- Layered phase order (app → cluster → image/chart → DX) produced zero cross-layer rework

### What Was Inefficient
- The 04-03 executor worktree was orphaned at its blocking human gate — the drafted SUMMARY sat uncommitted in the worktree and required a manual reconciliation session to salvage, validate, and merge
- REQUIREMENTS.md checkboxes were never ticked during phase completion — all 21 showed "Pending" at milestone close despite full verification evidence, forcing a close-time audit
- An interrupted `helm upgrade` left the release locked in `pending-upgrade`, blocking `make deploy` until a manual `helm rollback`
- The summary-extract tooling failed on the `**One-liner:**` line format, injecting placeholder garbage into MILESTONES.md (fixed manually)

### Patterns Established
- registry:3 + per-node containerd hosts.toml + self-verifying push/pull check at cluster-up
- Plain official-image manifests over paywalled/heavyweight charts (mongo:7 vs Bitnami)
- Multi-stage python:3.11-slim, numeric non-root UID 10001, exec-form gunicorn CMD
- `make smoke`: background port-forward + trap EXIT + curl PASS/FAIL as the standard reachability proof
- awk-powered `## description` inline help convention with `help` as default goal

### Key Lessons
1. Orphaned Helm `pending-upgrade` locks (from killed upgrades) are cleared safely with `helm rollback <release> <last-deployed-rev>` — the running workload is unaffected
2. Executor agents should commit their SUMMARY before a blocking human gate, or resume workflows must check leftover worktrees for uncommitted artifacts (this cost a reconciliation session)
3. Tick REQUIREMENTS.md traceability at each phase close, not at milestone close — stale bookkeeping compounds
4. kind clusters survive Docker Desktop restarts cleanly (containers auto-restart, pods self-heal) — restart resilience is free evidence worth capturing

### Cost Observations
- Model mix: not tracked this milestone
- Sessions: multiple across 4 days
- Notable: wave-based parallel execution with worktree executors worked well except at human gates (see lesson 2)

---

## Milestone: v1.1 — Product Dashboard

**Shipped:** 2026-07-14
**Phases:** 6 | **Plans:** 14 | **Sessions:** multiple (7-day span, 142 commits)

### What Was Built
- `apps/launchpad/` Flask platform app (app factory, lazy no-kubeconfig K8s client) with a hermetic 128-test suite at 100% coverage
- Server-rendered dashboard shell — Jinja2 + vendored htmx 2.0.10 + Pico CSS 2.1.1, fully offline, with visibility-guarded polling status cards
- Platform status contract: own-Mongo `/health` readiness (200/503), `/api/status` aggregation with graceful field-guide-api degradation, `/metrics` parity
- `charts/launchpad/` Helm chart with least-privilege RBAC + live K8s diagnostics page that never 500s (outside-cluster/403/unreachable all handled)
- Service catalog CRUD (CSRF-protected forms) + TTL-bounded events feed on launchpad's own in-cluster mongo:7
- `make up-all` / `make smoke-all` one-command bring-up of both apps; README browser demo with five real screenshots

### What Worked
- Mirroring proven v1.0 field-guide-api patterns verbatim (app factory, mongo singleton, chart structure, mongo:7 manifests) — Phases 5, 7, and 9 recorded "no structural deviation" and near-zero rework
- Contract-before-consumer phase ordering from research held up: LP_ Makefile namespace in Phase 5, `/health`-vs-`/api/status` separation in Phase 7 before the Phase 8 readinessProbe, TTL index before the first event write in Phase 9
- The milestone audit (gsd-audit-milestone) earned its keep: caught 9 stale REQUIREMENTS.md rows, confirmed all 24 cross-phase exports wired, and verified 4/4 E2E flows before close
- Gap-closure as a first-class plan (09-04 for CR-01 naive-datetime) kept verification honest instead of hand-waving the fix

### What Was Inefficient
- REQUIREMENTS.md checkboxes went stale again (9 Phase 9 rows still Pending at audit time) — v1.0 lesson 3 recurred; phase-close bookkeeping is still not habitual
- 10-VERIFICATION.md was left at `human_needed` after its sole item was actually resolved, re-flagging as an open artifact at milestone close and needing a manual status fix
- Automated accomplishment extraction injected two deviation-log lines ("[Rule 3 - Blocking]...") into MILESTONES.md, requiring manual curation — same tooling class as the v1.0 summary-extract garbage
- STATE.md per-plan metrics table was only partially maintained (Phase 5 P02, Phase 9, and Phase 10 rows missing; one "unrecorded")

### Patterns Established
- HX-Request header branch: same route serves an htmx fragment or a full page
- Module-attribute import discipline (`from app import k8s`) so conftest monkeypatches reach helpers
- Never-raise helper convention for I/O boundaries (catalog/events/get_cluster_state) — degrade, don't 500
- Per-app `.venv` + cd-into-app-dir isolation to avoid `app` package collisions in a multi-app monorepo
- Lazy K8s client with `(None, None)` disabled signal; exception-narrow in-cluster→kubeconfig fallback
- Per-chart embedded MongoDB (no shared instance) so each chart installs/uninstalls independently

### Key Lessons
1. Tick REQUIREMENTS.md at phase close, not milestone close — this is now a twice-verified lesson (v1.0 and v1.1 both paid an audit-time sync cost)
2. When a `human_needed` verification item gets resolved, update the VERIFICATION.md frontmatter in the same commit — stale statuses resurface as false blockers at milestone close
3. Auto-extracted summaries (accomplishments, one-liners) need a human curation pass before landing in MILESTONES.md — extraction tooling has misfired in both milestones
4. mongomock cannot exercise TTL expiry; documenting "verified live-only via `make verify-ttl`" up front (Phase 9 research flag) avoided a false test-coverage debate later

### Cost Observations
- Model mix: not tracked this milestone
- Sessions: multiple across 7 days
- Notable: pattern-mirroring from v1.0 kept per-plan durations short (9–34 min recorded); the one blocking deviation (worktree recreated after checkpoint teardown, Phase 9) echoes the v1.0 human-gate worktree lesson

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | multiple | 4 | Baseline: research → plan → execute → verify with human gates on live loops |
| v1.1 | multiple | 6 | Added pre-close milestone audit (requirements cross-reference + integration checker + E2E flows); pattern-mirroring from v1.0 as the default implementation strategy |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | 32 | 100% | registry wiring, smoke test, help system all stdlib/shell-only |
| v1.1 | 160 (32 + 128) | 100% both apps | vendored htmx/Pico (no CDN, no JS build), zero-JS deregister confirm, awk help extended to grouped sections |

### Top Lessons (Verified Across Milestones)

1. **Tick REQUIREMENTS.md traceability at phase close, not milestone close** — verified in both v1.0 (21 stale rows) and v1.1 (9 stale rows); stale bookkeeping compounds into audit-time work
2. **Auto-extraction tooling output needs human curation before it lands in permanent records** — v1.0 summary-extract placeholder garbage, v1.1 deviation-log lines in accomplishments
3. **Research-before-plan prevents stack reversals and mid-phase surprises** — v1.0 (Bitnami paywall, CRLF traps) and v1.1 (phase ordering held exactly; TTL/mongomock limitation flagged before it could burn a phase)
