FROM python:3.12-slim

ARG APP_VERSION=0.1.1

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_VERSION=${APP_VERSION}

LABEL org.opencontainers.image.title="alac-to-flac-docker" \
      org.opencontainers.image.version="${APP_VERSION}" \
      org.opencontainers.image.description="Convert ALAC (.m4a) files to FLAC and watch for updates" \
      org.opencontainers.image.licenses="MIT"

RUN apt-get update \
    && apt-get install --no-install-recommends -y ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY app.py ./

CMD ["python", "app.py"]
