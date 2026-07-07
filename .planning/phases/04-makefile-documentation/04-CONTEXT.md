# Phase 4: Makefile + Documentation - Context

**Gathered:** 2026-07-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase 4 delivers the complete developer experience for PRD-1: the Makefile gains its final required target (`clean`, MAKE-01) plus developer-experience wiring, the full `make cluster-up && make build && make load && make deploy` chain is verified end-to-end in Git Bash and WSL2 (MAKE-02), and the README becomes portfolio-grade documentation that lets a new developer reproduce clone → make → curl with zero assistance (DOCS-01).

**Scope guardrail (user-stated):** Phase 4 is Makefile + Documentation ONLY. No dashboard/UI implementation (that is PRD-3). No new app features. Do not run Docker prune, Docker Desktop reset, or enter the docker-desktop VM.

</domain>

<decisions>
## Implementation Decisions

### `make clean` semantics
- **D-01:** `make clean` is SAFE and NON-DESTRUCTIVE by default — removes only local caches, coverage files, `__pycache__`, and temporary test artifacts.
- **D-02:** `make clean` must NEVER remove: Docker images, Docker volumes, the kind cluster, the local registry, Helm releases, MongoDB PVCs, or anything that destroys demo/runtime state. The venv is also kept (venv removal is a separate explicit target, e.g. `clean-venv`).
- **D-03:** Deeper cleanup lives in explicit, separately-named targets (`clean-venv`, existing `undeploy`, existing `cluster-down`, new `reset-local`) with clear warnings.
- **D-04:** Add `reset-local` — chains `undeploy` → `cluster-down` with a loud echo warning before running. Non-default; never invoked by `clean`.

### Makefile developer experience
- **D-05:** Add `make help` auto-generated from the existing `## target: description` comments (awk/grep one-liner) so it stays in sync as targets are added in later PRDs. `help` becomes the default goal — bare `make` prints help.
- **D-06:** Add `make up` aggregate target chaining cluster-up → build → load → deploy. The raw four-command `&&` chain remains the verified success criterion (MAKE-02); `up` is a convenience on top, not a replacement.
- **D-07:** Add `make port-forward` (foreground kubectl port-forward, Ctrl+C to stop) AND `make smoke` (background port-forward → curl /health + /entries → PASS/FAIL report → cleanup). `smoke` doubles as the Phase 4 end-to-end verification tool.
- **D-08:** Add `make check-tools` doctor target — verifies docker, kind, helm, kubectl, and bash are on PATH and prints found versions vs required minimums. It is the first command the README tells a new developer to run.

### README & documentation structure
- **D-09:** README + `docs/` split. README carries the hook: what-this-is, architecture diagram, quickstart, demo flow, "what this proves". Deep material (troubleshooting, known limitations, Windows setup detail) goes to `docs/*.md` pages linked from the README. `docs/` is currently empty — this gives it purpose.
- **D-10:** README is portfolio-grade and must cover (user-stated list): architecture, developer loop, demo flow, troubleshooting, known limitations, screenshots plan, and "what this proves".
- **D-11:** Architecture diagram in Mermaid (renders natively on GitHub, text-editable, diffs cleanly). Flow: developer → make → local registry → kind → Helm → app/MongoDB.
- **D-12:** Capture REAL terminal output in this phase as fenced code blocks (`make up`, `make smoke`, curl responses) — no image files. Include a short checklist of UI screenshots to add later when the PRD-3 dashboard exists.

### Prerequisites & Windows story
- **D-13:** Git Bash is the PRIMARY documented path on Windows; WSL2 is documented as optional/secondary.
- **D-14:** README prerequisites table (tool, minimum version, install link) points to `make check-tools` as the verification step.
- **D-15:** All documentation and artifacts in English.

### Claude's Discretion
- Exact `help` target implementation (awk vs grep/sed) and formatting.
- `smoke` target failure behavior details (timeout values, retry count, cleanup trap mechanics).
- docs/ page naming and exact split of content between README and docs pages.
- Whether the README mentions the committed dev password guard (WR-07 NOTES.txt warning from Phase 3) — recommended to echo it in troubleshooting/known-limitations, wording at Claude's discretion.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements & prior verification
- `.planning/REQUIREMENTS.md` — MAKE-01, MAKE-02, DOCS-01 definitions (the three requirements this phase closes)
- `.planning/phases/03-containerization-helm-deployment/03-VERIFICATION.md` — live-verified end-to-end flow (port-forward smoke test commands, WR-07 dev-password guard) that the README demo flow and `make smoke` must match
- `.planning/phases/03-containerization-helm-deployment/03-03-PLAN.md` — how build/load/deploy targets were designed (TAG coordination, no `--atomic`)

### Existing artifacts this phase extends
- `Makefile` — existing targets (test, cluster-up, cluster-down, build, load, deploy, undeploy), `## comment` convention, `SHELL := /bin/bash` + `MSYS_NO_PATHCONV=1` header, IMAGE/TAG/RELEASE/CHART variables
- `README.md` — current 15-line stub (description + repository layout table) to be expanded, layout table content should be preserved/absorbed
- `scripts/cluster-setup.sh`, `scripts/cluster-teardown.sh` — idempotent lifecycle scripts wrapped by cluster-up/cluster-down
- `charts/field-guide-api/templates/NOTES.txt` — WR-07 dev-password warning; README security note should stay consistent with it

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `Makefile` already has `## target: description` comments on every target — the auto-generated `help` target can parse these directly with zero rework.
- `scripts/cluster-setup.sh` self-verifies push+pull-from-pod — `make smoke` follows the same self-verifying script pattern.
- Phase 3 verification (03-VERIFICATION.md) documents the exact working port-forward + curl commands — reuse verbatim for `make smoke` and README demo flow.
- Test suite (32 tests, 100% coverage) runs via existing `make test` — README quickstart can include it.

### Established Patterns
- Makefile header: `SHELL := /bin/bash`, `export MSYS_NO_PATHCONV=1`, `?=` overridable variables (PYTHON, IMAGE, TAG, RELEASE, CHART) — new targets must follow.
- `$$` escaping for shell variables inside recipes (see `test` target's VENV_PY detection).
- Idempotency as a norm: cluster-up/down, deploy (`helm upgrade --install`) are all safe to re-run — new targets (clean, smoke, check-tools) should be too.
- LF-only line endings enforced by `.gitattributes` — any new shell snippets must respect this.
- Small lowercase conventional commits.

### Integration Points
- `Makefile` `.PHONY` list and the phase comment banner (line 16) need updating with new targets.
- `README.md` stub is replaced/expanded in place; `docs/` directory (currently empty) receives the deep-dive pages.
- App reachability: Service is ClusterIP; port-forward is the access path (Ingress/NodePort are out of scope per REQUIREMENTS.md).

</code_context>

<specifics>
## Specific Ideas

- README must answer "what this proves" — it's a portfolio piece for platform-engineering thinking; framing matters as much as instructions.
- Demo flow section should read as a copy-paste session: commands + real captured output.
- `make smoke` output should be an explicit PASS/FAIL so it reads well in captured terminal output.
- `make check-tools` is positioned as step zero of the quickstart ("run this first").

</specifics>

<deferred>
## Deferred Ideas

- UI screenshots for the README — deferred until the PRD-3 dashboard exists; Phase 4 only writes the checklist of what to capture.
- Dashboard/UI implementation — PRD-3, explicitly out of scope per user guardrail.

</deferred>

---

*Phase: 4-Makefile + Documentation*
*Context gathered: 2026-07-07*
