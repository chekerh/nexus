FROM python:3.13-slim@sha256:8c9a4a0a1fe1a4b265d9ec6eb4f89e7e8f7f1a4b8c9d8e7f6a5b4c3d2e1f0a1b AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg=7:* \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ backend/
COPY frontend/ frontend/
COPY prompts/ prompts/

RUN mkdir -p backend/data/clips backend/data/backgrounds && \
    addgroup --system --gid 1001 nexus && \
    adduser --system --uid 1001 --gid 1001 nexus && \
    chown -R nexus:nexus /app

USER nexus

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f --max-time 8 http://localhost:8000/health || exit 1

STOPSIGNAL SIGTERM

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
