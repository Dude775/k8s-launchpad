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
# Phase 1: test only | Phase 2: cluster-up, cluster-down | Phase 3: build, load, deploy, undeploy
.PHONY: test cluster-up cluster-down build load deploy undeploy

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

## build: build the field-guide-api Docker image and tag it for the local registry
build:
	docker build -t $(IMAGE):$(TAG) apps/field-guide-api

## load: push the built image to the local kind registry (localhost:5001)
load:
	docker push $(IMAGE):$(TAG)

## deploy: install or upgrade the Helm release (idempotent; helm upgrade --install)
deploy:
	helm upgrade --install $(RELEASE) $(CHART) --wait --timeout 180s

## undeploy: remove the Helm release and all chart-owned resources
undeploy:
	helm uninstall $(RELEASE)
