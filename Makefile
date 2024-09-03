CODE_ROOT := er_aws_rds
CONTAINER_ENGINE ?= $(shell which podman >/dev/null 2>&1 && echo podman || echo docker)
IMAGE_NAME := quay.io/app-sre/er-aws-rds
IMAGE_TAG := $(shell git describe --tags)
ifeq ($(IMAGE_TAG),)
	IMAGE_TAG = pre
endif
BUILD_ARGS := CODE_ROOT=$(CODE_ROOT) POETRY_VERSION=1.8.3 IMAGE_NAME=$(IMAGE_NAME) IMAGE_TAG=$(IMAGE_TAG)

.PHONY: format
format:
	poetry run ruff check
	poetry run ruff format

.PHONY: test
test: build
	$(CONTAINER_ENGINE) build -t $(IMAGE_NAME)-test $(foreach arg,$(BUILD_ARGS),--build-arg $(arg)) -f dockerfiles/Dockerfile.test .
	$(CONTAINER_ENGINE) run --rm --entrypoint poetry $(IMAGE_NAME)-test run ruff check --no-fix
	$(CONTAINER_ENGINE) run --rm --entrypoint poetry $(IMAGE_NAME)-test run ruff format --check
	$(CONTAINER_ENGINE) run --rm --entrypoint poetry $(IMAGE_NAME)-test run mypy
	$(CONTAINER_ENGINE) run --rm --entrypoint poetry $(IMAGE_NAME)-test run pytest -vv --cov=$(CODE_ROOT) --cov-report=term-missing --cov-report xml

.PHONY: build
build:
	$(CONTAINER_ENGINE) build -t $(IMAGE_NAME):${IMAGE_TAG} $(foreach arg,$(BUILD_ARGS),--build-arg $(arg)) -f dockerfiles/Dockerfile .

.PHONY: push
push:
	$(CONTAINER_ENGINE) push ${BASE_IMAGE}:${IMAGE_TAG}

.PHONY: deploy
deploy: build test push
