SHELL := /bin/bash
export MSYS_NO_PATHCONV=1

# Interpreter used to CREATE the project venv — override per host:
#   make test PYTHON="py -3.12"    (Windows Git Bash)
#   make test PYTHON=python3.11    (WSL2 / native Linux)
PYTHON ?= python3

# ─── Targets ──────────────────────────────────────────────────────────────────
# Phase 1: test only | Phase 2: cluster-up, cluster-down | Phase 3+: build, load, deploy
.PHONY: test cluster-up cluster-down

## test: create local venv (idempotent), install dev-deps, run pytest with coverage
test:
	cd apps/field-guide-api && \
	{ [ -d .venv ] || $(PYTHON) -m venv .venv; } && \
	VENV_PY=$$([ -x .venv/bin/python ] && echo .venv/bin/python || echo .venv/Scripts/python) && \
	"$$VENV_PY" -m pip install -q -r requirements-dev.txt && \
	"$$VENV_PY" -m pytest

## cluster-up: create kind cluster + local registry (idempotent)
cluster-up:
	bash scripts/cluster-setup.sh

## cluster-down: tear down kind cluster + registry (idempotent)
cluster-down:
	bash scripts/cluster-teardown.sh
