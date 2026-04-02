#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

# 1) Python environment
if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -r requirements.txt >/dev/null

# 2) Read model settings from .env (fallbacks if missing)
OLLAMA_MODEL="$(grep -E '^OLLAMA_MODEL=' .env 2>/dev/null | head -n1 | cut -d'=' -f2- || true)"
OLLAMA_ANALYST_MODEL="$(grep -E '^OLLAMA_ANALYST_MODEL=' .env 2>/dev/null | head -n1 | cut -d'=' -f2- || true)"
OLLAMA_STYLE_MODEL="$(grep -E '^OLLAMA_STYLE_MODEL=' .env 2>/dev/null | head -n1 | cut -d'=' -f2- || true)"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:7b}"

# 3) Start Ollama only if not already running
if ! curl -sSf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "Starting Ollama server..."
  ollama serve >/tmp/nexus-ollama.log 2>&1 &
  OLLAMA_PID=$!
  sleep 2
else
  OLLAMA_PID=""
fi

# 4) Ensure model is available
echo "Ensuring model '$OLLAMA_MODEL' is available..."
ollama pull "$OLLAMA_MODEL" >/dev/null

if [[ -n "${OLLAMA_ANALYST_MODEL:-}" ]]; then
  echo "Ensuring analyst model '$OLLAMA_ANALYST_MODEL' is available..."
  ollama pull "$OLLAMA_ANALYST_MODEL" >/dev/null
fi

if [[ -n "${OLLAMA_STYLE_MODEL:-}" ]]; then
  echo "Ensuring style model '$OLLAMA_STYLE_MODEL' is available..."
  ollama pull "$OLLAMA_STYLE_MODEL" >/dev/null
fi

# 5) Cleanup background ollama if this script started it
cleanup() {
  if [[ -n "${OLLAMA_PID:-}" ]]; then
    kill "$OLLAMA_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

# 6) Start app
echo "Starting Nexus-UGC on http://127.0.0.1:8000"
exec uvicorn backend.app.main:app --reload --port 8000
