MACHINE := rancher

DEFAULT_PLATFORMS := linux/amd64,linux/arm64

TAG ?= dev
REPO ?= rancher
IMAGE ?= systemd-node
IMAGE_NAME ?= $(REPO)/$(IMAGE):$(TAG)

buildx-machine:
	@docker buildx ls | grep $(MACHINE) || \
		docker buildx create --name=$(MACHINE) --platform=$(DEFAULT_PLATFORMS)

.PHONY: push-image
push-image: buildx-machine
	docker buildx build \
		$(IID_FILE_FLAG) \
		$(BUILDX_ARGS) \
		--platform=$(TARGET_PLATFORMS) \
		--tag $(IMAGE_NAME) \
		--push \
		.
