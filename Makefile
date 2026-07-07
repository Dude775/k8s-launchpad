SHELL := /bin/bash
export MSYS_NO_PATHCONV=1

# Interpreter used to CREATE the project venv — override per host:
#   make test PYTHON="py -3.12"    (Windows Git Bash)
#   make test PYTHON=python3.11    (WSL2 / native Linux)
PYTHON ?= python3

# Image coordinates — override with: make build TAG=v1.0
IMAGE   ?= localhost:5001/field-guide-api
TAG     ?= dev
RELEASE ?= field-guide-api
CHART   ?= charts/field-guide-api

# ─── Targets ──────────────────────────────────────────────────────────────────
# Phase 1: test | Phase 2: cluster-up, cluster-down | Phase 3: build, load, deploy, undeploy | Phase 4: help, up, check-tools, port-forward, smoke, clean, clean-venv, reset-local
.PHONY: test cluster-up cluster-down build load deploy undeploy help up check-tools port-forward smoke clean clean-venv reset-local

.DEFAULT_GOAL := help

help: ## print this help message (default goal)
	@awk 'BEGIN {FS = ":.*##"; printf "Usage:\n  make \033[36m<target>\033[0m\n\nTargets:\n"} \
	  /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

test: ## create local venv (idempotent), install dev-deps, run pytest with coverage
	cd apps/field-guide-api && \
	{ [ -d .venv ] || $(PYTHON) -m venv .venv; } && \
	VENV_PY=$$([ -x .venv/bin/python ] && echo .venv/bin/python || echo .venv/Scripts/python) && \
	"$$VENV_PY" -m pip install -q -r requirements-dev.txt && \
	"$$VENV_PY" -m pytest

cluster-up: ## create kind cluster + local registry (idempotent)
	bash scripts/cluster-setup.sh

cluster-down: ## tear down kind cluster + registry (idempotent)
	bash scripts/cluster-teardown.sh

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
