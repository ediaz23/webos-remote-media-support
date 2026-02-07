FROM gcc:13

RUN apt-get update && apt-get install -y --no-install-recommends \
  cmake ninja-build pkg-config python3 meson git ca-certificates \
  sudo passwd \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /work

RUN useradd -m -s /bin/bash webosbuilder
RUN usermod -aG sudo webosbuilder
RUN echo 'webosbuilder:123456' | chpasswd
USER webosbuilder

CMD ["bash", "/work/scripts/docker-helper.sh"]
