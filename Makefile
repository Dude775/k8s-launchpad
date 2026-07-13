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

# launchpad image coordinates (namespaced LP_ prefix — never shadow field-guide-api)
LP_IMAGE   ?= localhost:5001/launchpad
LP_TAG     ?= dev
LP_RELEASE ?= launchpad
LP_CHART   ?= charts/launchpad

# ─── Targets ──────────────────────────────────────────────────────────────────
# Phase 1: test | Phase 2: cluster-up, cluster-down | Phase 3: build, load, deploy, undeploy | Phase 4: help, up, check-tools, port-forward, smoke, clean, clean-venv, reset-local | Phase 5: test-launchpad, build-launchpad, load-launchpad, deploy-launchpad, port-forward-launchpad, smoke-launchpad | Phase 10: up-all, smoke-all, undeploy-launchpad, verify-ttl
.PHONY: test cluster-up cluster-down build load deploy undeploy help up check-tools port-forward smoke clean clean-venv reset-local test-launchpad build-launchpad load-launchpad deploy-launchpad port-forward-launchpad smoke-launchpad up-all smoke-all undeploy-launchpad verify-ttl

.DEFAULT_GOAL := help

help: ## print this help message (default goal)
	@awk 'BEGIN {FS = ":.*##"; printf "Usage:\n  make \033[36m<target>\033[0m\n"} \
	  /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2 } \
	  /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) }' $(MAKEFILE_LIST)

##@ field-guide-api
test: ## create local venv (idempotent), install dev-deps, run pytest with coverage
	cd apps/field-guide-api && \
	{ [ -d .venv ] || $(PYTHON) -m venv .venv; } && \
	VENV_PY=$$([ -x .venv/bin/python ] && echo .venv/bin/python || echo .venv/Scripts/python) && \
	"$$VENV_PY" -m pip install -q -r requirements-dev.txt && \
	"$$VENV_PY" -m pytest

##@ launchpad
# ─── launchpad targets (Phase 5, filled in Phase 8/10) ────────────────────────
test-launchpad: ## create launchpad venv (idempotent), install dev-deps, run pytest with coverage
	cd apps/launchpad && \
	{ [ -d .venv ] || $(PYTHON) -m venv .venv; } && \
	VENV_PY=$$([ -x .venv/bin/python ] && echo .venv/bin/python || echo .venv/Scripts/python) && \
	"$$VENV_PY" -m pip install -q -r requirements-dev.txt && \
	"$$VENV_PY" -m pytest

build-launchpad: ## build the launchpad Docker image and tag it for the local registry
	docker build -t $(LP_IMAGE):$(LP_TAG) apps/launchpad

load-launchpad: ## push the built launchpad image to the local kind registry (localhost:5001)
	docker push $(LP_IMAGE):$(LP_TAG)

# LP_IMAGE/LP_TAG are forwarded to the chart so build-launchpad/load-launchpad/deploy-launchpad stay coordinated:
#   make build-launchpad LP_TAG=v1.0 && make load-launchpad LP_TAG=v1.0 && make deploy-launchpad LP_TAG=v1.0
deploy-launchpad: ## install or upgrade the launchpad Helm release (idempotent; helm upgrade --install)
	helm upgrade --install $(LP_RELEASE) $(LP_CHART) \
		--set image.repository=$(LP_IMAGE) --set image.tag=$(LP_TAG) \
		--wait --timeout 180s

port-forward-launchpad: ## forward svc/launchpad to localhost:8081 (Ctrl-C to stop)
	kubectl port-forward svc/$(LP_RELEASE) 8081:80

smoke-launchpad: ## background port-forward, curl /, /health, /api/status, PASS/FAIL, cleanup
	@echo "==> Starting launchpad smoke test..."; \
	pkill -f "kubectl port-forward svc/$(LP_RELEASE)" 2>/dev/null || true; \
	kubectl port-forward svc/$(LP_RELEASE) 8081:80 &>/dev/null & \
	PF_PID=$$!; \
	trap "kill $$PF_PID 2>/dev/null || true" EXIT; \
	sleep 3; \
	STATUS=0; \
	for endpoint in "" health api/status; do \
	  CODE=$$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8081/$$endpoint); \
	  if [ "$$CODE" = "200" ]; then \
	    echo "  PASS  /$$endpoint → $$CODE"; \
	  else \
	    echo "  FAIL  /$$endpoint → $$CODE"; \
	    STATUS=1; \
	  fi; \
	done; \
	if [ $$STATUS -eq 0 ]; then echo "==> launchpad smoke PASSED"; else echo "==> launchpad smoke FAILED"; exit 1; fi

undeploy-launchpad: ## remove the launchpad Helm release and all chart-owned resources
	helm uninstall $(LP_RELEASE)

verify-ttl: ## verify the events TTL index exists (default: index check; TTL_DEEP=1: slow live expiry round-trip, ~60-90s)
	@echo "==> Verifying events TTL index..."; \
	POD=$$(kubectl get pods -l app.kubernetes.io/name=launchpad-mongodb -o jsonpath='{.items[0].metadata.name}' 2>/dev/null); \
	if [ -z "$$POD" ]; then echo "  FAIL  launchpad mongodb pod not found"; exit 1; fi; \
	kubectl exec $$POD -- mongosh --quiet -u root -p launchpad-dev-password --authenticationDatabase admin launchpad \
	  --eval 'JSON.stringify(db.events.getIndexes())' | grep -q expireAfterSeconds \
	  && echo "  PASS  events.ts TTL index present" \
	  || { echo "  FAIL  no TTL index on events.ts"; exit 1; }; \
	if [ "$$TTL_DEEP" = "1" ]; then \
	  echo "==> TTL_DEEP=1: running live expiry round-trip (slow, ~60-90s)..."; \
	  kubectl exec $$POD -- mongosh --quiet -u root -p launchpad-dev-password --authenticationDatabase admin launchpad \
	    --eval 'db.events.insertOne({type: "ttl-deep-probe", service_name: null, ts: new Date()})' >/dev/null; \
	  TTL_OK=0; \
	  for i in $$(seq 1 18); do \
	    sleep 5; \
	    COUNT=$$(kubectl exec $$POD -- mongosh --quiet -u root -p launchpad-dev-password --authenticationDatabase admin launchpad \
	      --eval 'db.events.countDocuments({type: "ttl-deep-probe"})' 2>/dev/null | tail -1); \
	    if [ "$$COUNT" = "0" ]; then TTL_OK=1; break; fi; \
	  done; \
	  if [ "$$TTL_OK" = "1" ]; then \
	    echo "  PASS  TTL monitor expired the probe document"; \
	  else \
	    echo "  FAIL  probe document not expired within 90s"; \
	    exit 1; \
	  fi; \
	fi

##@ Cluster
cluster-up: ## create kind cluster + local registry (idempotent)
	bash scripts/cluster-setup.sh

cluster-down: ## tear down kind cluster + registry (idempotent)
	bash scripts/cluster-teardown.sh

##@ field-guide-api
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

up-all: up build-launchpad load-launchpad deploy-launchpad  ## bring up cluster + BOTH apps (up, then launchpad build/load/deploy)
	@echo ""
	@echo "==> up-all complete. Both apps deployed."
	@echo "==> Next: make port-forward-launchpad  (then open http://localhost:8081)"
	@echo "==> Then: make smoke-all"

smoke-all: smoke smoke-launchpad  ## smoke-test BOTH apps (field-guide-api on 8080, launchpad on 8081)

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

##@ Housekeeping
clean: ## remove local caches, coverage, and temp artifacts (SAFE — no cluster/image/venv changes)
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name .coverage -delete 2>/dev/null || true
	find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true

clean-venv: ## remove both apps' virtualenvs (re-run 'make test'/'make test-launchpad' to recreate)
	rm -rf apps/field-guide-api/.venv
	rm -rf apps/launchpad/.venv

reset-local: ## DESTRUCTIVE — undeploy BOTH releases + destroy cluster + registry (loses all data)
	@echo "!!"
	@echo "!! WARNING: This removes both Helm releases, the kind cluster, and the local registry."
	@echo "!! All in-cluster data (MongoDB PVC contents, both apps) will be lost."
	@echo "!!"
	@read -p "!! Type YES to continue: " confirm && [ "$$confirm" = "YES" ]
	$(MAKE) undeploy || true
	$(MAKE) undeploy-launchpad || true
	$(MAKE) cluster-down
