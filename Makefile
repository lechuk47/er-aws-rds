BASE_IMAGE=quay.io/app-sre/er-aws-rds

VERSION := $(shell git describe --tags)
ifeq ($(VERSION),)
	VERSION = 0.0.1
endif

IMAGE=${BASE_IMAGE}:${VERSION}

.PHONY: all
all: build push

.PHONY: build
build:
	VERSION=$(git describe --abbrev=0 --tags)
	docker build -t ${IMAGE} -f dockerfiles/Dockerfile .

.PHONY: push
push:
	docker push ${IMAGE}

.PHONY: test
test: build
	docker build -t ${IMAGE}-test -f dockerfiles/Dockerfile.test .
	docker run --rm --entrypoint python3 ${IMAGE}-test -m pytest -v
