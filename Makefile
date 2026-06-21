PORT ?= 8000

# Canonical version source: pyproject.toml `[project] version`. Override
# per-invocation via `VERSION=0.4.0-rc1 make build` without editing files.
VERSION    ?= $(shell awk -F\" '/^version *= *"/ {print $$2; exit}' pyproject.toml)
TAG        := v$(VERSION)
IMAGE_NAME := psyb0t/flickies

DEV_IMAGE       := psyb0t/flickies-dev:latest
CPU_IMAGE       := $(IMAGE_NAME):$(TAG)
CPU_IMAGE_LATEST := $(IMAGE_NAME):latest
CUDA_IMAGE      := $(IMAGE_NAME):$(TAG)-cuda
CUDA_IMAGE_LATEST := $(IMAGE_NAME):latest-cuda

PYPROJECT := pyproject.toml
BUMP_HOST := bash scripts/bump_exclude_newer.sh $(PYPROJECT)

UID := $(shell id -u)
GID := $(shell id -g)

# Sandboxed dev container — all dev-side commands run inside this so the host
# stays clean. Heavy ML deps (wav2lip, latentsync, gfpgan, torch) live ONLY in
# the prod images. Unit tests stub the engine backends.
DEV_RUN := docker run --rm \
	-u $(UID):$(GID) \
	-e HOME=/tmp \
	-v $(PWD):/work \
	-w /work \
	$(DEV_IMAGE)

DEV_RUN_TTY := docker run --rm -it \
	-u $(UID):$(GID) \
	-e HOME=/tmp \
	-v $(PWD):/work \
	-w /work \
	$(DEV_IMAGE)

.PHONY: help dev-image shell version \
        build build-cuda build-all \
        run run-cuda \
        test test-unit test-integration test-unit-cov-gate \
        lint format check clean \
        generate generate-models generate-check \
        generate-client-go generate-client-python \
        pkg-lock pkg-upgrade pkg-add pkg-remove pkg-update pkg-compile-heavy

help: ## Show this help
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

version: ## Print the canonical version (from pyproject.toml) — sanity-check before tagging
	@echo $(TAG)

# -----------------------------------------------------------------------------
# Dev container — every other target depends on this.
# -----------------------------------------------------------------------------

dev-image: ## Build/refresh the sandboxed dev image
	docker build -f Dockerfile.dev -t $(DEV_IMAGE) .

shell: dev-image ## Drop into a shell inside the dev container
	$(DEV_RUN_TTY) bash

# -----------------------------------------------------------------------------
# Package management — uv inside the dev container.
# Every mutation bumps [tool.uv] exclude-newer to today first so the
# supply-chain age gate is always anchored to the moment of the change.
# -----------------------------------------------------------------------------

pkg-lock: dev-image ## Refresh uv.lock (honors current exclude-newer)
	$(DEV_RUN) uv lock

pkg-upgrade: dev-image ## Bump exclude-newer + refresh lock with newest pins
	$(BUMP_HOST)
	$(DEV_RUN) uv lock --upgrade

pkg-add: dev-image ## Add a package (usage: make pkg-add PKG=name[==ver])
	@test -n "$(PKG)" || (echo "usage: make pkg-add PKG=name[==ver]" >&2; exit 1)
	$(BUMP_HOST)
	$(DEV_RUN) uv add --no-sync $(PKG)

pkg-remove: dev-image ## Remove a package (usage: make pkg-remove PKG=name)
	@test -n "$(PKG)" || (echo "usage: make pkg-remove PKG=name" >&2; exit 1)
	$(BUMP_HOST)
	$(DEV_RUN) uv remove --no-sync $(PKG)

pkg-update: dev-image ## Upgrade ONE package (usage: make pkg-update PKG=name)
	@test -n "$(PKG)" || (echo "usage: make pkg-update PKG=name" >&2; exit 1)
	$(BUMP_HOST)
	$(DEV_RUN) uv lock --upgrade-package $(PKG)

# Heavy ML stack used by the prod images is NOT part of the uv.lock resolution
# (different torch flavor per variant, fetched from the pytorch index). It
# lives in scripts/heavy-deps-{cpu,cuda}.in and is compiled to hash-locked
# requirements-heavy-{cpu,cuda}.txt — both committed and consumed by
# Dockerfile / Dockerfile.cuda via `uv pip install --require-hashes`.
# Re-run this after editing the .in files.
pkg-compile-heavy: dev-image ## Re-compile hash-locked requirements-heavy-{cpu,cuda}.txt
	$(BUMP_HOST)
	$(DEV_RUN) bash scripts/compile_heavy_deps.sh

# -----------------------------------------------------------------------------
# Production image builds.
# -----------------------------------------------------------------------------

build: ## Build the CPU production image (tags both :vX.Y.Z and :latest)
	docker build -f Dockerfile -t $(CPU_IMAGE) -t $(CPU_IMAGE_LATEST) .

build-cuda: ## Build the CUDA production image (tags both :vX.Y.Z-cuda and :latest-cuda)
	docker build -f Dockerfile.cuda -t $(CUDA_IMAGE) -t $(CUDA_IMAGE_LATEST) .

build-all: build build-cuda ## Build both production images

# -----------------------------------------------------------------------------
# Local run targets.
# -----------------------------------------------------------------------------

run: build ## Run CPU image locally (uses ~/.flickies-data for models + files)
	mkdir -p $$HOME/.flickies-data
	docker run --rm -it \
		-v $$HOME/.flickies-data:/data \
		-e FLICKIES_DEVICE=cpu \
		-e HF_HUB_OFFLINE=0 \
		-p $(PORT):8000 \
		$(CPU_IMAGE)

run-cuda: build-cuda ## Run CUDA image locally (requires --gpus all support)
	mkdir -p $$HOME/.flickies-data
	docker run --rm -it --gpus all \
		-v $$HOME/.flickies-data:/data \
		-e FLICKIES_DEVICE=cuda \
		-e HF_HUB_OFFLINE=0 \
		-p $(PORT):8000 \
		$(CUDA_IMAGE)

# -----------------------------------------------------------------------------
# Test / lint / format — all inside the dev container.
# -----------------------------------------------------------------------------

test: test-unit ## Run unit tests (fast, offline, no GPU)

test-unit: dev-image ## Run unit tests in the dev container with coverage
	$(DEV_RUN) pytest tests/ -v \
		--cov=src/flickies \
		--cov-report=term-missing:skip-covered

# Stricter gate: fail if line coverage on the support modules drops below 80%.
# Engine bodies (Wav2Lip._lipsync_sync / LatentSync._lipsync_sync / etc.)
# are NOT in this gate because they import heavy ML libs (torch, diffusers,
# mediapipe, insightface, basicsr) lazily and those libs aren't in the dev
# image — the dev image is intentionally lightweight. The integration suite
# under tests/integration/ covers engine inference end-to-end against the
# prod image. This gate covers the glue code.
test-unit-cov-gate: dev-image ## Enforce >=80% line coverage on support modules
	$(DEV_RUN) pytest tests/ \
		--cov=flickies.config \
		--cov=flickies.engines.base \
		--cov=flickies.engines._license_gate \
		--cov=flickies.engines._registry \
		--cov-fail-under=80

# Integration suite — runs on the host (NOT inside the dev container) because
# it spawns sibling docker containers and pokes the flickies HTTP port directly.
# The pytest session-scoped fixture (tests/integration/conftest.py) builds the
# CPU image first unless HARNESS_SKIP_BUILD=1, computes the union of engines
# needed by collected tests, spawns ONE container, and tears it down at
# session end.
#
# Markers + env knobs:
#   HARNESS_GPU=1                              run CUDA tests (gpu marker)
#   HARNESS_IMAGE=psyb0t/flickies:local-cuda   override the docker image
#   HF_TOKEN / HUGGINGFACE_TOKEN               unlock hf_gated tests
#   FLICKIES_ENABLE_NONCOMMERCIAL=1            unlock noncommercial (Wav2Lip)
#   HARNESS_KEEP=1                             leave container running on exit
#   HARNESS_SKIP_BUILD=1                       skip `make build` preflight
test-integration: ## Run integration tests (host-side; spawns docker containers via pytest)
	@pytest tests/integration/ -v

lint: dev-image ## Lint python sources
	$(DEV_RUN) ruff check src tests
	$(DEV_RUN) ruff format --check src tests
	$(DEV_RUN) pyright src

format: dev-image ## Format python sources
	$(DEV_RUN) ruff format src tests
	$(DEV_RUN) ruff check --fix src tests

check: lint test ## Lint + unit tests

# -----------------------------------------------------------------------------
# Code generation — every consumer derives from openapi.yaml.
# Re-run after every change to openapi.yaml. Generated files are committed to
# the repo (not built on container startup) so prod images don't need the
# generators installed.
#
# Umbrella `generate` runs everything: server-side Pydantic models, Go client,
# Python client. CI gate `generate-check` fails when generated files drift
# from the spec (catches "edited openapi.yaml but forgot to regenerate").
# -----------------------------------------------------------------------------

generate: generate-models generate-client-go generate-client-python ## Regenerate all consumers from openapi.yaml

generate-models: dev-image ## Regenerate src/flickies/schema/_generated.py from openapi.yaml
	$(DEV_RUN) bash scripts/generate_models.sh

# Go client. Output lands in pkg/clients/go/client.gen.go inside its own
# Go module (pkg/clients/go/go.mod) so other Go projects can:
#     go get github.com/psyb0t/docker-flickies/pkg/clients/go@latest
generate-client-go: dev-image ## Regenerate the typed Go client from openapi.yaml
	$(DEV_RUN) sh -c "oapi-codegen -config api/oapi-codegen-go.yaml openapi.yaml && \
		cd pkg/clients/go && go mod tidy"

# Python client. Output lands in pkg/clients/python/flickies-client/
#     pip install "git+https://github.com/psyb0t/docker-flickies.git#subdirectory=pkg/clients/python/flickies-client"
generate-client-python: dev-image ## Regenerate the typed Python client from openapi.yaml
	$(DEV_RUN) sh -c "rm -rf pkg/clients/python/flickies-client/* && \
		openapi-python-client generate --path openapi.yaml --output-path pkg/clients/python/flickies-client --overwrite"

# CI gate — fail loud when openapi.yaml was edited without re-running generators.
generate-check: generate ## CI gate — fail if generated files drift from openapi.yaml
	@git diff --exit-code src/flickies/schema pkg/clients || \
		(echo "Generated files drift from openapi.yaml — run 'make generate' and commit" >&2; exit 1)

clean: ## Remove build / cache artifacts (host-side)
	docker rmi $(CPU_IMAGE) $(CUDA_IMAGE) 2>/dev/null || true
	rm -rf build dist *.egg-info .pytest_cache .mypy_cache .ruff_cache .venv
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
