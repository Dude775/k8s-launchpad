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

## Cross-Milestone Trends

### Process Evolution

| Milestone | Sessions | Phases | Key Change |
|-----------|----------|--------|------------|
| v1.0 | multiple | 4 | Baseline: research → plan → execute → verify with human gates on live loops |

### Cumulative Quality

| Milestone | Tests | Coverage | Zero-Dep Additions |
|-----------|-------|----------|-------------------|
| v1.0 | 32 | 100% | registry wiring, smoke test, help system all stdlib/shell-only |

### Top Lessons (Verified Across Milestones)

1. (Single milestone so far — candidates: research-before-plan prevents stack reversals; human-verify gates keep live claims honest)
