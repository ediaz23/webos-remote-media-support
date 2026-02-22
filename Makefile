IMAGE := webos-remote-media-support
WORKDIR := /work

.PHONY: build build-dev build-prod clean all

build:
	docker run --rm -it -v "$(PWD):$(WORKDIR)" -w $(WORKDIR) -e PROFILE=$(PROFILE) $(IMAGE)
	mkdir -p dist/lib
	cp -v /lib/x86_64-linux-gnu/libuuid.so.1   dist/lib/
	cp -v /lib/x86_64-linux-gnu/libexpat.so.1  dist/lib/
	cp -v /lib/x86_64-linux-gnu/libpng16.so.16 dist/lib/
	cp -v /lib/x86_64-linux-gnu/libz.so.1	  dist/lib/
	cp -v /lib/x86_64-linux-gnu/libbz2.so.1.0  dist/lib/
	cp -f src/default.woff2 dist/bin/

build-dev:
	$(MAKE) build PROFILE=dev

build-prod:
	$(MAKE) build PROFILE=prod

clean:
	rm -rf build/cmake
	rm -rf build/libraries
	rm -rf dist/bin
	rm -rf dist/lib

all: clean build-prod
