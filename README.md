# alac-to-flac-docker

Containerized watcher that converts `.m4a` (ALAC) files to lossless `.flac` files using FFmpeg.

## Behavior

- Reads `path` environment variable (string): directory to scan.
- Reads `subfolder` environment variable (boolean): if `true`, scan and watch recursively.
- Converts existing `.m4a` files at startup.
- Replaces each source file with `<same-name>.flac`.
- Continues watching for new/updated `.m4a` files and converts them automatically.

The converter preserves source audio characteristics by carrying through source sample rate and bit depth where available.

## Run with Docker

```bash
docker build -t alac-to-flac-docker .
docker run --rm \
  -e path=/music \
  -e subfolder=true \
  -v /host/music:/music \
  alac-to-flac-docker
```

## Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
path=/absolute/path/to/music subfolder=true python app.py
```
