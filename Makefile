VENV_CMD := . venv/bin/activate &&
BASE_IMAGE=quay.io/app-sre/er-aws-rds

IMAGE_TAG := $(shell git describe --tags)
ifeq ($(IMAGE_TAG),)
	IMAGE_TAG = 0.0.1
endif

.PHONY: deploy
deploy: build test push

.PHONY: build
build:
	docker build -t ${BASE_IMAGE}:${IMAGE_TAG} -f dockerfiles/Dockerfile .

.PHONY: push
push:
	docker push ${BASE_IMAGE}:${IMAGE_TAG}

.PHONY: test
test: build
	docker build -t ${BASE_IMAGE}-test --build-arg="IMAGE_TAG=${IMAGE_TAG}" -f dockerfiles/Dockerfile.test .
	docker run --rm --entrypoint python3 ${BASE_IMAGE}-test -m pytest -v

.PHONY: dev-venv
dev-venv:
	python3.11 -m venv venv
	@$(VENV_CMD) pip install --upgrade pip
	@$(VENV_CMD) pip install -r requirements.txt
	@$(VENV_CMD) pip install -r requirements_dev.txt
	@$(VENV_CMD) pip install -r requirements_test.txt
