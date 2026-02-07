IMAGE := webos-remote-media-support
WORKDIR := /work

.PHONY: build build-dev build-prod clean all

build:
	docker run --rm -it -v "$(PWD):$(WORKDIR)" -w $(WORKDIR) -e PROFILE=$(PROFILE) $(IMAGE)

build-dev:
	$(MAKE) build PROFILE=dev

build-prod:
	$(MAKE) build PROFILE=prod

clean:
	rm -rf build/cmake
	rm -rf build/libraries
	rm -rf dist/bin

all: clean build-prod
