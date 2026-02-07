# webos-remote-media-support
A local companion server for legacy LG webOS TVs that offloads heavy media-related processing from the TV browser and exposes lightweight HTTP endpoints for on-demand assets, improving playback stability and performance.

## Docker

### Build image

```bash
docker build -t webos-remote-media-support .  --no-cache --network=host
```

### Compile (DEV)

```bash
docker run --rm -it -v "$PWD:/work" -w /work webos-remote-media-support bash -lc "cmake -S . -B build -DPROFILE=dev && cmake --build build -j"
```

### Compile (PROD)

```bash
docker run --rm -it -v "$PWD:/work" -w /work webos-remote-media-support bash -lc "cmake -S . -B build -DPROFILE=prod && cmake --build build -j"
```
