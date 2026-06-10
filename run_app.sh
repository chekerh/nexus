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
OLLAMA_FALLBACK_MODEL="$(grep -E '^OLLAMA_FALLBACK_MODEL=' .env 2>/dev/null | head -n1 | cut -d'=' -f2- || true)"
DEV_RELOAD="$(grep -E '^DEV_RELOAD=' .env 2>/dev/null | head -n1 | cut -d'=' -f2- || true)"
ANALYSIS_BACKEND="$(grep -E '^ANALYSIS_BACKEND=' .env 2>/dev/null | head -n1 | cut -d'=' -f2- || true)"
AIRLLM_MODEL_ID="$(grep -E '^AIRLLM_MODEL_ID=' .env 2>/dev/null | head -n1 | cut -d'=' -f2- || true)"
CAPTION_STYLE_MODE="$(grep -E '^CAPTION_STYLE_MODE=' .env 2>/dev/null | head -n1 | cut -d'=' -f2- || true)"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:7b}"
OLLAMA_FALLBACK_MODEL="${OLLAMA_FALLBACK_MODEL:-qwen2.5:3b}"
DEV_RELOAD="${DEV_RELOAD:-false}"
ANALYSIS_BACKEND="${ANALYSIS_BACKEND:-ollama}"
AIRLLM_MODEL_ID="${AIRLLM_MODEL_ID:-Qwen/Qwen2.5-3B-Instruct}"
CAPTION_STYLE_MODE="${CAPTION_STYLE_MODE:-hybrid}"

dev_reload_enabled() {
  case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
    true|1|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

model_exists_local() {
  local model="$1"
  if [[ -z "$model" ]]; then
    return 1
  fi
  ollama list 2>/dev/null | awk 'NR>1 {print $1}' | grep -Fxq "$model"
}

ensure_model_available() {
  local model="$1"
  local required="$2"

  if [[ -z "$model" ]]; then
    return 0
  fi

  if model_exists_local "$model"; then
    echo "Model '$model' already local."
    return 0
  fi

  echo "Ensuring model '$model' is available..."
  local attempts=3
  local ok=0
  for ((i=1; i<=attempts; i++)); do
    if ollama pull "$model" >/dev/null; then
      ok=1
      break
    fi
    echo "Pull attempt $i/$attempts failed for '$model'. Retrying..."
    sleep 2
  done

  if [[ "$ok" -eq 1 ]] || model_exists_local "$model"; then
    return 0
  fi

  if [[ "$required" == "required" ]]; then
    return 1
  fi

  echo "Warning: optional model '$model' unavailable. Continuing."
  return 0
}

normalize_lower() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

require_airllm_python_package() {
  if python - <<'PY' >/dev/null 2>&1
import importlib
raise SystemExit(0 if importlib.util.find_spec('airllm') else 1)
PY
  then
    return 0
  fi

  echo "Installing airllm for ANALYSIS_BACKEND=airllm..."
  pip install "airllm>=2.11.0" >/dev/null
}

BACKEND_LC="$(normalize_lower "$ANALYSIS_BACKEND")"
STYLE_MODE_LC="$(normalize_lower "$CAPTION_STYLE_MODE")"
NEED_OLLAMA=true
if [[ "$BACKEND_LC" == "airllm" && "$STYLE_MODE_LC" == "rule" ]]; then
  NEED_OLLAMA=false
fi

if [[ "$BACKEND_LC" == "airllm" ]]; then
  echo "Analysis backend: airllm ($AIRLLM_MODEL_ID)"
  require_airllm_python_package
fi

# 3) Start Ollama only if not already running
if [[ "$NEED_OLLAMA" == "true" ]] && ! curl -sSf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
  echo "Starting Ollama server..."
  ollama serve >/tmp/nexus-ollama.log 2>&1 &
  OLLAMA_PID=$!
  sleep 2
else
  OLLAMA_PID=""
fi

# 4) Ensure models are available (with retry + fallback)
if [[ "$BACKEND_LC" != "airllm" ]] && ! ensure_model_available "$OLLAMA_MODEL" required; then
  echo "Warning: primary model '$OLLAMA_MODEL' unavailable. Trying fallback '$OLLAMA_FALLBACK_MODEL'..."
  if ensure_model_available "$OLLAMA_FALLBACK_MODEL" required; then
    export OLLAMA_MODEL="$OLLAMA_FALLBACK_MODEL"
    if [[ -z "${OLLAMA_ANALYST_MODEL:-}" ]]; then
      export OLLAMA_ANALYST_MODEL="$OLLAMA_FALLBACK_MODEL"
    fi
    echo "Using fallback model '$OLLAMA_FALLBACK_MODEL' for this run."
  else
    echo "Error: could not pull primary or fallback model."
    echo "Tip: set a smaller local model in .env (e.g. OLLAMA_MODEL=qwen2.5:3b)."
    exit 1
  fi
fi

if [[ "$BACKEND_LC" != "airllm" && -n "${OLLAMA_ANALYST_MODEL:-}" ]]; then
  ensure_model_available "$OLLAMA_ANALYST_MODEL" optional || true
fi

if [[ "$NEED_OLLAMA" == "true" && -n "${OLLAMA_STYLE_MODEL:-}" ]]; then
  ensure_model_available "$OLLAMA_STYLE_MODEL" optional || true
fi

# 5) Cleanup background ollama if this script started it
cleanup() {
  if [[ -n "${OLLAMA_PID:-}" ]]; then
    kill "$OLLAMA_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

# 6) Start app
echo "Starting Nexus-UGC v2 on http://127.0.0.1:8000"
echo "  Database: SQLite (set DATABASE_URL for PostgreSQL)"
echo "  API:       http://127.0.0.1:8000/api/v1/docs"
if dev_reload_enabled "$DEV_RELOAD"; then
  exec uvicorn backend.app.main:app --reload --port 8000
else
  exec uvicorn backend.app.main:app --port 8000
fi
