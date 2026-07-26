REGION_KEY ?= iad
TENANCY_NAMESPACE ?=
NAME_PREFIX ?= cis-auto
TAG ?= v1
CONTROLLER_PLATFORM ?= linux/amd64
RUNNER_PLATFORM ?= linux/amd64
LOADER_PLATFORM ?= linux/amd64

ifeq ($(strip $(TENANCY_NAMESPACE)),)
$(error TENANCY_NAMESPACE is required, for example: make push REGION_KEY=iad TENANCY_NAMESPACE=mytenancynamespace)
endif

REGISTRY := $(REGION_KEY).ocir.io/$(TENANCY_NAMESPACE)
CONTROLLER_IMAGE := $(REGISTRY)/$(NAME_PREFIX)-controller:$(TAG)
RUNNER_IMAGE := $(REGISTRY)/$(NAME_PREFIX)-runner:$(TAG)
OBJECT_EVENT_LOADER_IMAGE := $(REGISTRY)/$(NAME_PREFIX)-object-event-loader:$(TAG)
ADB_SQL_LOADER_IMAGE := $(REGISTRY)/$(NAME_PREFIX)-adb-sql-loader:$(TAG)

.PHONY: build push build-runner push-runner print-images

build:
	docker build --platform $(CONTROLLER_PLATFORM) -t $(CONTROLLER_IMAGE) functions/controller
	docker build --platform $(RUNNER_PLATFORM) -t $(RUNNER_IMAGE) container
	docker build --platform $(LOADER_PLATFORM) -t $(OBJECT_EVENT_LOADER_IMAGE) -f functions/object-storage-event-loader/Dockerfile .
	docker build --platform $(LOADER_PLATFORM) -t $(ADB_SQL_LOADER_IMAGE) -f functions/adb-sql-loader/Dockerfile .

push: build
	docker push $(CONTROLLER_IMAGE)
	docker push $(RUNNER_IMAGE)
	docker push $(OBJECT_EVENT_LOADER_IMAGE)
	docker push $(ADB_SQL_LOADER_IMAGE)

build-runner:
	docker build --platform $(RUNNER_PLATFORM) -t $(RUNNER_IMAGE) container

push-runner: build-runner
	docker push $(RUNNER_IMAGE)

print-images:
	@echo $(CONTROLLER_IMAGE)
	@echo $(RUNNER_IMAGE)
	@echo $(OBJECT_EVENT_LOADER_IMAGE)
	@echo $(ADB_SQL_LOADER_IMAGE)
