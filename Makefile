SHELL := /bin/bash
export MSYS_NO_PATHCONV=1

# ─── Targets ──────────────────────────────────────────────────────────────────
# Phase 1: test only (cluster-up, build, load, deploy added in Phase 4)
.PHONY: test

## test: install dev-deps and run the pytest suite with coverage
test:
	cd apps/field-guide-api && pip install -q -r requirements-dev.txt && pytest
