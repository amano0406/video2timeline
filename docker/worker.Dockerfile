FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/workspace/worker/src
ENV TIMELINE_FOR_VIDEO_IN_DOCKER=1

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY worker/pyproject.toml /workspace/worker/pyproject.toml
COPY worker/src /workspace/worker/src

RUN pip install --no-cache-dir -e /workspace/worker

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 CMD ["python", "-m", "timeline_for_video_worker", "health", "--json"]

ENTRYPOINT ["python", "-m", "timeline_for_video_worker"]
CMD ["serve"]
