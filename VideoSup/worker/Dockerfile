FROM debian:bookworm-slim AS ffmpeg

ARG TARGETARCH
ARG FFMPEG_TAG=autobuild-2026-05-24-13-16
ARG FFMPEG_FILE_AMD64=ffmpeg-N-124616-g3baab604db-linux64-gpl.tar.xz
ARG FFMPEG_SHA256_AMD64=eb94f4fc292d3c14b18213f2749436aba50d4e1d408329fbc4425f0e14c8f276
ARG FFMPEG_FILE_ARM64=ffmpeg-N-124616-g3baab604db-linuxarm64-gpl.tar.xz
ARG FFMPEG_SHA256_ARM64=8b5d6c2ab52de360b6686bd4be8f871e2a66e981d9d5b49867d2de2890e55c9a

RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates curl xz-utils \
  && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
  if [ "$TARGETARCH" = "amd64" ]; then file="$FFMPEG_FILE_AMD64"; sha="$FFMPEG_SHA256_AMD64"; \
  elif [ "$TARGETARCH" = "arm64" ]; then file="$FFMPEG_FILE_ARM64"; sha="$FFMPEG_SHA256_ARM64"; \
  else echo "unsupported TARGETARCH=$TARGETARCH" >&2; exit 1; fi; \
  curl -fsSL -o /tmp/ffmpeg.tar.xz "https://github.com/BtbN/FFmpeg-Builds/releases/download/${FFMPEG_TAG}/${file}"; \
  echo "${sha}  /tmp/ffmpeg.tar.xz" | sha256sum -c -; \
  mkdir -p /opt/ffmpeg; \
  tar -xJf /tmp/ffmpeg.tar.xz -C /opt/ffmpeg; \
  ffmpeg_path="$(find /opt/ffmpeg -type f -name ffmpeg | head -n 1)"; \
  ffprobe_path="$(find /opt/ffmpeg -type f -name ffprobe | head -n 1)"; \
  install -m 0755 "$ffmpeg_path" /usr/local/bin/ffmpeg; \
  install -m 0755 "$ffprobe_path" /usr/local/bin/ffprobe; \
  /usr/local/bin/ffmpeg -version >/dev/null; \
  /usr/local/bin/ffprobe -version >/dev/null

FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
  && apt-get install -y --no-install-recommends fontconfig fonts-dejavu-core fonts-noto-cjk \
  && rm -rf /var/lib/apt/lists/*

COPY --from=ffmpeg /usr/local/bin/ffmpeg /usr/local/bin/ffmpeg
COPY --from=ffmpeg /usr/local/bin/ffprobe /usr/local/bin/ffprobe

WORKDIR /app/worker

COPY requirements.txt /app/worker/requirements.txt
RUN pip install --no-cache-dir -r /app/worker/requirements.txt

COPY . /app/worker

ENV PYTHONPATH=/app/worker

CMD ["sh", "-lc", "if [ \"${VIDEOSUP_RUN_TESTS:-0}\" = \"1\" ]; then python -m videosup_worker.tools.wait_for_http && python -m unittest discover -s tests -p 'test_*.py'; else uvicorn videosup_service.app:app --host 0.0.0.0 --port ${PORT:-9010}; fi"]
