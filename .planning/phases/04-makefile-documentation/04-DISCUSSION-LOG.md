# Phase 4: Makefile + Documentation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-07-07
**Phase:** 4-Makefile + Documentation
**Areas discussed:** clean target scope, Makefile DX extras, README depth & structure, Prerequisites & Windows story

---

## Area Selection (with user guardrails)

User selected all four proposed areas and supplied guardrails up front:
- `make clean` safe and non-destructive by default (caches, coverage, pycache, temp test artifacts only)
- `make clean` must never remove Docker images/volumes, kind cluster, registry, Helm releases, MongoDB PVCs
- Deeper cleanup via explicit separate targets (`clean-venv`, `undeploy`, `cluster-down`, `reset-local`) with warnings
- No Docker prune / Docker Desktop reset / docker-desktop VM entry
- Phase 4 scope is Makefile + Documentation only — no dashboard/UI work
- Git Bash primary on Windows, WSL2 optional
- README portfolio-grade: architecture, developer loop, demo flow, troubleshooting, known limitations, screenshots plan, "what this proves"
- Everything in English

---

## clean target scope

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, add reset-local | Explicit target chaining undeploy → cluster-down with loud echo warning; non-default, never called by clean | ✓ |
| No, manual only | Document `make undeploy && make cluster-down` in README instead | |

**User's choice:** Yes, add reset-local (Recommended)
**Notes:** clean semantics themselves were fixed by the user's guardrails before questioning.

---

## Makefile DX extras

### make help

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, auto-generated | Parse existing `##` comments; help as default goal so bare `make` prints it | ✓ |
| Yes, but static text | Hand-written help text; can drift | |
| No help target | README covers targets | |

**User's choice:** Yes, auto-generated (Recommended)

### Aggregate target

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, `make up` | Chains cluster-up → build → load → deploy; raw && chain remains the verified criterion | ✓ |
| No aggregate | README documents the four-command chain verbatim | |

**User's choice:** Yes, `make up` (Recommended)

### App access

| Option | Description | Selected |
|--------|-------------|----------|
| port-forward + smoke | `make port-forward` (foreground) + `make smoke` (background port-forward, curl /health + /entries, PASS/FAIL, cleanup) | ✓ |
| port-forward only | Convenience target only; verification manual | |
| Neither | Raw kubectl command documented in README | |

**User's choice:** port-forward + smoke (Recommended)

---

## README depth & structure

### Doc layout

| Option | Description | Selected |
|--------|-------------|----------|
| README + docs/ pages | README holds the hook; deep material in docs/*.md linked from README | ✓ |
| Single comprehensive README | Everything in one file with TOC | |

**User's choice:** README + docs/ pages (Recommended)

### Diagram format

| Option | Description | Selected |
|--------|-------------|----------|
| Mermaid | Renders natively on GitHub; text-editable; diffs cleanly | ✓ |
| ASCII art | Works everywhere but dated for portfolio | |
| Both | Mermaid + small ASCII version | |

**User's choice:** Mermaid (Recommended)

### Screenshots

| Option | Description | Selected |
|--------|-------------|----------|
| Real output as code blocks | Actual captured terminal output as fenced code blocks; checklist of UI screenshots for PRD-3 | ✓ |
| Plan only | docs/screenshots-plan.md checklist; no captured output | |
| Actual image screenshots | PNG screenshots committed under docs/images/ | |

**User's choice:** Real output as code blocks (Recommended)

---

## Prerequisites & Windows story

### check-tools

| Option | Description | Selected |
|--------|-------------|----------|
| check-tools target | `make check-tools` verifies docker, kind, helm, kubectl, bash on PATH with versions vs minimums | ✓ |
| Table only | README table with tool/version/install link, no Makefile logic | |

**User's choice:** check-tools target (Recommended)
**Notes:** Git Bash-primary / WSL2-optional was fixed by user guardrail before questioning.

---

## Claude's Discretion

- Exact `help` implementation (awk vs grep/sed) and formatting
- `smoke` failure behavior details (timeouts, retries, cleanup trap)
- docs/ page naming and content split between README and docs pages
- Whether/how README echoes the WR-07 dev-password guard from chart NOTES.txt

## Deferred Ideas

- UI screenshots for README — wait for PRD-3 dashboard; Phase 4 writes only the capture checklist
- Dashboard/UI implementation — PRD-3, out of scope per user guardrail
