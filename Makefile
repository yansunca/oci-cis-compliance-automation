REGION_KEY ?= iad
TENANCY_NAMESPACE ?=
NAME_PREFIX ?= cis-auto
TAG ?= v1
CONTROLLER_PLATFORM ?= linux/amd64
RUNNER_PLATFORM ?= linux/arm64
INGESTER_PLATFORM ?= linux/amd64

ifeq ($(strip $(TENANCY_NAMESPACE)),)
$(error TENANCY_NAMESPACE is required, for example: make push REGION_KEY=iad TENANCY_NAMESPACE=mytenancynamespace)
endif

REGISTRY := $(REGION_KEY).ocir.io/$(TENANCY_NAMESPACE)
CONTROLLER_IMAGE := $(REGISTRY)/$(NAME_PREFIX)-controller:$(TAG)
RUNNER_IMAGE := $(REGISTRY)/$(NAME_PREFIX)-runner:$(TAG)
INGESTER_IMAGE := $(REGISTRY)/$(NAME_PREFIX)-ingester:$(TAG)

.PHONY: build push print-images

build:
	docker build --platform $(CONTROLLER_PLATFORM) -t $(CONTROLLER_IMAGE) functions/controller
	docker build --platform $(RUNNER_PLATFORM) -t $(RUNNER_IMAGE) container
	docker build --platform $(INGESTER_PLATFORM) -t $(INGESTER_IMAGE) functions/ingester

push: build
	docker push $(CONTROLLER_IMAGE)
	docker push $(RUNNER_IMAGE)
	docker push $(INGESTER_IMAGE)

print-images:
	@echo $(CONTROLLER_IMAGE)
	@echo $(RUNNER_IMAGE)
	@echo $(INGESTER_IMAGE)
