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

up: cluster-up build load deploy  ## bring up the full local stack (cluster-up → build → load → deploy)

check-tools: ## verify required tools are on PATH and print versions
	@echo "==> Checking required tools..."; \
	PASS=1; \
	for tool in docker kind helm kubectl bash; do \
	  if command -v $$tool >/dev/null 2>&1; then \
	    echo "  ok  $$tool  ($$($$tool --version 2>&1 | head -1))"; \
	  else \
	    echo "  MISSING  $$tool"; \
	    PASS=0; \
	  fi; \
	done; \
	if [ $$PASS -eq 0 ]; then echo "==> check-tools FAILED — install missing tools"; exit 1; fi; \
	echo "==> check-tools PASSED"

port-forward: ## forward svc/field-guide-api to localhost:8080 (Ctrl-C to stop)
	kubectl port-forward svc/$(RELEASE) 8080:80

smoke: ## background port-forward, curl /health + /entries + /metrics, PASS/FAIL, cleanup
	@echo "==> Starting smoke test..."; \
	pkill -f "kubectl port-forward svc/$(RELEASE)" 2>/dev/null || true; \
	kubectl port-forward svc/$(RELEASE) 8080:80 &>/dev/null & \
	PF_PID=$$!; \
	trap "kill $$PF_PID 2>/dev/null || true" EXIT; \
	sleep 3; \
	STATUS=0; \
	for endpoint in health entries metrics; do \
	  CODE=$$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/$$endpoint); \
	  if [ "$$CODE" = "200" ]; then \
	    echo "  PASS  /$$endpoint → $$CODE"; \
	  else \
	    echo "  FAIL  /$$endpoint → $$CODE"; \
	    STATUS=1; \
	  fi; \
	done; \
	if [ $$STATUS -eq 0 ]; then echo "==> smoke PASSED"; else echo "==> smoke FAILED"; exit 1; fi

clean: ## remove local caches, coverage, and temp artifacts (SAFE — no cluster/image/venv changes)
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name .coverage -delete 2>/dev/null || true
	find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true

clean-venv: ## remove the app virtualenv (re-run 'make test' to recreate)
	rm -rf apps/field-guide-api/.venv

reset-local: ## DESTRUCTIVE — undeploy + destroy cluster + registry (loses all data)
	@echo "!!"
	@echo "!! WARNING: This removes the Helm release, kind cluster, and local registry."
	@echo "!! All in-cluster data (MongoDB PVC contents) will be lost."
	@echo "!!"
	@read -p "!! Type YES to continue: " confirm && [ "$$confirm" = "YES" ]
	$(MAKE) undeploy || true
	$(MAKE) cluster-down
