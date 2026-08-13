FROM python:3.14-slim@sha256:ce40764625a4ff50df3548277632e7f96c4e77fe75fa848aae9885476e7df5a4 AS builder

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
