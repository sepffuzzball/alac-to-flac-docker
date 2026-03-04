# alac-to-flac-docker

Containerized watcher that converts `.m4a` (ALAC) files to lossless `.flac` files using FFmpeg.

## Versioning

- Application version is tracked in `VERSION`.
- Docker image labels include `org.opencontainers.image.version`.
- GitHub Actions publishes images to GHCR with branch/tag/SHA tags.

## Behavior

- Reads `path` environment variable (string): directory to scan.
- Reads `subfolder` environment variable (boolean): if `true`, scan and watch recursively.
- Reads `polldelayseconds` environment variable (positive number, default: `60`): polling interval for change detection.
- Also accepts `POLL_INTERVAL_SECONDS` as a backward-compatible alias.
- Reads `TZ` environment variable (string, optional): sets process timezone for logs and runtime behavior.
- Reads `PUID` and `PGID` environment variables (non-negative integers, optional): when both are set, the process switches user/group at startup to match host file ownership.
- Converts existing `.m4a` files at startup.
- Replaces each source file with `<same-name>.flac`.
- Continues watching for new/updated `.m4a` files and converts them automatically.
- Exposes an HTTP health endpoint at `/healthz` on port `80` for Kubernetes/container probes.

The converter preserves source audio characteristics by carrying through source sample rate and bit depth where available.

- `PUID` and `PGID` must be set together when used.
- If `PUID`/`PGID` differ from the container's current identity, the process must start as root to perform the identity switch.

## Run with Docker

```bash
docker build -t alac-to-flac-docker .
docker run --rm \
  -p 80:80 \
  -e TZ=America/New_York \
  -e PUID=1000 \
  -e PGID=1000 \
  -e path=/music \
  -e subfolder=true \
  -e polldelayseconds=60 \
  -v /host/music:/music \
  alac-to-flac-docker
```

## GitHub Actions publish

On `push`, the workflow builds and publishes to:

- `ghcr.io/<owner>/<repo>:<branch>`
- `ghcr.io/<owner>/<repo>:sha-<shortsha>`
- `ghcr.io/<owner>/<repo>:<tag>` (for git tags)
- `ghcr.io/<owner>/<repo>:latest` (when pushing the default branch)

On pull requests, it builds without pushing.

## Local run

```bash
TZ=America/New_York PUID=1000 PGID=1000 path=/absolute/path/to/music subfolder=true polldelayseconds=60 python app.py
```
