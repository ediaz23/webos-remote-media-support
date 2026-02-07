FROM gcc:13

RUN apt-get update && apt-get install -y --no-install-recommends \
  cmake ninja-build pkg-config python3 meson git ca-certificates \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /work

COPY scripts/docker-helper.sh /usr/local/bin/build-webos

RUN chmod +x /usr/local/bin/build-webos

CMD ["build-webos"]
