#!/usr/bin/env bash
set -euo pipefail

# Optional debug mode: set DEBUG=true to enable shell tracing
if [[ "${DEBUG:-}" == "true" ]]; then
  set -x
fi

# Ensure python3 is available early
if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 not found. Install Python 3.8+ and try again."
  exit 1
fi

# ─── Config ─────────────────────────────────────
RUN_MIGRATIONS="${RUN_MIGRATIONS:-true}"
HEALTH_CHECK="${HEALTH_CHECK:-true}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"
UVICORN_WORKERS="${UVICORN_WORKERS:-1}"

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

# ──────────────────────────────────────────────
# 1) Python environment
# ──────────────────────────────────────────────
VENV_DIR=".venv"
CREATED_VENV=false
if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  if [[ ! -d "$VENV_DIR" ]]; then
    python3 -m venv "$VENV_DIR"
    CREATED_VENV=true
  fi
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
else
  echo "Detected active virtualenv; using it (VIRTUAL_ENV=${VIRTUAL_ENV})."
fi

# Use python -m pip to avoid ambiguity about which pip is run
python3 -m pip install --upgrade pip -q
if [[ "${CREATED_VENV:-false}" == "true" || "${FORCE_REINSTALL:-false}" == "true" ]]; then
  python3 -m pip install -r requirements.txt -q
else
  echo "Skipping requirements install (set FORCE_REINSTALL=true to force)."
fi

# ──────────────────────────────────────────────
# 2) System dependency checks
# ──────────────────────────────────────────────
if ! command -v ffmpeg &>/dev/null; then
  echo "ERROR: ffmpeg is required for video rendering."
  echo "  Install: brew install ffmpeg  (macOS)"
  echo "  Or:      apt install ffmpeg   (Linux)"
  exit 1
fi

# Clear stale Python cache to avoid old-code issues
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

# Ensure data directories exist
mkdir -p backend/data/clips backend/data/backgrounds backend/data/uploads

# ──────────────────────────────────────────────
# 3) Read .env settings
# ──────────────────────────────────────────────
ENV_FILE=".env"
if [[ ! -f "$ENV_FILE" ]]; then
  cp .env.example .env 2>/dev/null || touch .env
  echo "Created empty .env — edit it or use Setup page to configure."
fi

read_env() {
  grep -E "^${1}=" .env 2>/dev/null | head -n1 | cut -d'=' -f2- || true
}

# Check Whisper binary if configured
WHISPER_BIN="$(read_env WHISPER_BINARY_PATH)"
if [[ -n "$WHISPER_BIN" && ! -x "$WHISPER_BIN" ]]; then
  echo "Warning: WHISPER_BINARY_PATH=$WHISPER_BIN not found or not executable."
  echo "  Update .env or ensure Whisper.cpp is built at that path."
fi

OLLAMA_MODEL="$(read_env OLLAMA_MODEL)"
OLLAMA_ANALYST_MODEL="$(read_env OLLAMA_ANALYST_MODEL)"
OLLAMA_STYLE_MODEL="$(read_env OLLAMA_STYLE_MODEL)"
OLLAMA_FALLBACK_MODEL="$(read_env OLLAMA_FALLBACK_MODEL)"
DEV_RELOAD="$(read_env DEV_RELOAD)"
ANALYSIS_BACKEND="$(read_env ANALYSIS_BACKEND)"
AIRLLM_MODEL_ID="$(read_env AIRLLM_MODEL_ID)"
CAPTION_STYLE_MODE="$(read_env CAPTION_STYLE_MODE)"
PUBLIC_BASE_URL="$(read_env PUBLIC_BASE_URL)"

OLLAMA_MODEL="${OLLAMA_MODEL:-phi3}"
OLLAMA_FALLBACK_MODEL="${OLLAMA_FALLBACK_MODEL:-qwen2.5:0.5b}"
DEV_RELOAD="${DEV_RELOAD:-false}"
ANALYSIS_BACKEND="${ANALYSIS_BACKEND:-ollama}"
AIRLLM_MODEL_ID="${AIRLLM_MODEL_ID:-Qwen/Qwen2.5-3B-Instruct}"
CAPTION_STYLE_MODE="${CAPTION_STYLE_MODE:-hybrid}"

# ──────────────────────────────────────────────
# 4) Database migrations
# ──────────────────────────────────────────────
if [[ "$RUN_MIGRATIONS" == "true" ]]; then
  echo "Checking database migrations..."
  if [[ -d "alembic" ]] && command -v alembic &>/dev/null; then
    CURRENT_HEAD=$(alembic heads 2>/dev/null | head -1 | awk '{print $1}' || echo "")
    if [[ -n "$CURRENT_HEAD" ]]; then
      alembic upgrade head 2>&1 || echo "  ⚠️  Alembic migration failed (non-fatal, DB may be up to date)"
    fi
  else
    echo "  ⬜ Alembic not available — skipping migrations"
  fi
fi

# ──────────────────────────────────────────────
# 5) Helper functions
# ──────────────────────────────────────────────
dev_reload_enabled() {
  case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in
    true|1|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

model_exists_local() {
  local model="$1"
  if [[ -z "$model" ]]; then return 1; fi
  ollama list 2>/dev/null | awk 'NR>1 {print $1}' | grep -Fxq "$model"
}

ensure_model_available() {
  local model="$1"
  local required="$2"
  if [[ -z "$model" ]]; then return 0; fi
  if model_exists_local "$model"; then
    echo "  Model '$model' already local."
    return 0
  fi
  echo "  Pulling model '$model'..."
  local attempts=3
  for ((i=1; i<=attempts; i++)); do
    if ollama pull "$model" >/dev/null 2>&1; then
      echo "  Model '$model' ready."
      return 0
    fi
    echo "  Pull attempt $i/$attempts failed. Retrying..."
    sleep 2
  done
  if [[ "$required" == "required" ]]; then
    echo "  FAILED to pull required model '$model'."
    return 1
  fi
  echo "  Warning: optional model '$model' unavailable. Continuing."
  return 0
}

normalize_lower() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

check_env_var() {
  local var="$1"
  local label="$2"
  local val="$(read_env "$var")"
  if [[ -n "$val" ]]; then
    echo "  ✅ $label"
  else
    echo "  ⬜ $label — not set (manual publish fallback)"
  fi
}

# ──────────────────────────────────────────────
# 6) Analysis backend setup
# ──────────────────────────────────────────────
BACKEND_LC="$(normalize_lower "$ANALYSIS_BACKEND")"
STYLE_MODE_LC="$(normalize_lower "$CAPTION_STYLE_MODE")"
NEED_OLLAMA=true
if [[ "$BACKEND_LC" == "airllm" && "$STYLE_MODE_LC" == "rule" ]]; then
  NEED_OLLAMA=false
fi

if [[ "$BACKEND_LC" == "airllm" ]]; then
  echo "Analysis backend: airllm ($AIRLLM_MODEL_ID)"
  if python -c "import importlib; raise SystemExit(0 if importlib.util.find_spec('airllm') else 1)" 2>/dev/null; then
    :
  else
    echo "Installing airllm..."
    pip install "airllm>=2.11.0" -q
  fi
fi

# ──────────────────────────────────────────────
# 7) Start Ollama (if needed and not running)
# ──────────────────────────────────────────────
OLLAMA_PID=""
if [[ "$NEED_OLLAMA" == "true" ]]; then
  if curl -sSf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    echo "Ollama already running."
  else
    echo "Starting Ollama server..."
    ollama serve >/tmp/nexus-ollama.log 2>&1 &
    OLLAMA_PID=$!
    sleep 3
  fi
fi

# ──────────────────────────────────────────────
# 8) Pull LLM models
# ──────────────────────────────────────────────
echo "Checking LLM models..."

if [[ "$BACKEND_LC" != "airllm" ]] && ! ensure_model_available "$OLLAMA_MODEL" required; then
  echo "Warning: primary model '$OLLAMA_MODEL' unavailable. Trying fallback '$OLLAMA_FALLBACK_MODEL'..."
  if ensure_model_available "$OLLAMA_FALLBACK_MODEL" required; then
    export OLLAMA_MODEL="$OLLAMA_FALLBACK_MODEL"
    if [[ -z "${OLLAMA_ANALYST_MODEL:-}" ]]; then
      export OLLAMA_ANALYST_MODEL="$OLLAMA_FALLBACK_MODEL"
    fi
    echo "Using fallback model '$OLLAMA_FALLBACK_MODEL'."
  else
    echo "ERROR: Could not pull any model. Check your Ollama installation."
    echo "  Set OLLAMA_MODEL to a smaller model in .env (e.g. qwen2.5:0.5b)"
    exit 1
  fi
fi

if [[ "$BACKEND_LC" != "airllm" && -n "${OLLAMA_ANALYST_MODEL:-}" ]]; then
  ensure_model_available "$OLLAMA_ANALYST_MODEL" optional || true
fi

if [[ "$NEED_OLLAMA" == "true" && -n "${OLLAMA_STYLE_MODEL:-}" ]]; then
  ensure_model_available "$OLLAMA_STYLE_MODEL" optional || true
fi

# ──────────────────────────────────────────────
# 9) Print feature summary
# ──────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  Nexus-UGC v2 — Startup Summary"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "  LLM Models"
echo "  ├─ Primary:    $OLLAMA_MODEL"
echo "  ├─ Analyst:    ${OLLAMA_ANALYST_MODEL:-$OLLAMA_MODEL}"
echo "  ├─ Style:      ${OLLAMA_STYLE_MODEL:-$OLLAMA_MODEL}"
echo "  ├─ Fallback:   $OLLAMA_FALLBACK_MODEL"
echo "  └─ Backend:    $ANALYSIS_BACKEND"
echo ""
echo "  Video Processing"
  echo "  ├─ FFmpeg:     $(ffmpeg -version 2>&1 | head -n1 | sed 's/.*version \([^ ]*\).*/\1/' || echo 'OK')"
echo "  ├─ Captions:   $CAPTION_STYLE_MODE"
echo "  └─ Encoder:    $(read_env VIDEO_ENCODER || echo auto)"
echo ""
echo "  Infrastructure"
echo "  ├─ Server:     http://${HOST}:${PORT}"
echo "  ├─ API docs:   http://${HOST}:${PORT}/api/v1/docs"
echo "  ├─ Metrics:    http://${HOST}:${PORT}/api/v1/metrics"
echo "  ├─ Workers:    ${UVICORN_WORKERS}"
echo "  ├─ Reload:     ${DEV_RELOAD}"
echo "  └─ DB:         $(read_env DATABASE_URL || echo 'SQLite (backend/data/nexus.db)')"
echo ""
echo "  Security"
echo "  ├─ CSP:        $(read_env CSP_REPORT_ONLY || echo 'true (report-only)')"
echo "  ├─ Rate limit: $(read_env RATE_LIMIT_BACKEND || echo memory)/$(read_env RATE_LIMIT_PER_MINUTE || echo 60) per min"
echo "  ├─ Max upload: $(read_env MAX_UPLOAD_SIZE_MB || echo 500) MB"
echo "  └─ Logs:       $(read_env LOG_FORMAT || echo human)"
echo ""
echo "  Billing"
STRIPE_ENABLED="$(read_env STRIPE_SECRET_KEY)"
if [[ -n "$STRIPE_ENABLED" ]]; then
  echo "  ├─ Stripe:     ✅ configured"
else
  echo "  ├─ Stripe:     ⬜ dev mode (mock checkout)"
fi
WHOP_ENABLED="$(read_env WHOP_WEBHOOK_SECRET)"
if [[ -n "$WHOP_ENABLED" ]]; then
  echo "  ├─ Whop:       ✅ configured"
else
  echo "  ├─ Whop:       ⬜ not configured"
fi
EMAIL_ENABLED="$(read_env RESEND_API_KEY)"
SMTP_ENABLED="$(read_env SMTP_HOST)"
if [[ -n "$EMAIL_ENABLED" ]]; then
  echo "  ├─ Email:      ✅ Resend"
elif [[ -n "$SMTP_ENABLED" ]]; then
  echo "  ├─ Email:      ✅ SMTP"
else
  echo "  ├─ Email:      ⬜ mock (set RESEND_API_KEY or SMTP_HOST)"
fi
SENTRY_DSN="$(read_env SENTRY_DSN)"
if [[ -n "$SENTRY_DSN" ]]; then
  echo "  └─ Sentry:     ✅ enabled"
else
  echo "  └─ Sentry:     ⬜ not configured"
fi
echo ""
echo "  Platform credentials:"
check_env_var "YOUTUBE_CLIENT_ID" "YouTube API"
check_env_var "TIKTOK_ACCESS_TOKEN" "TikTok API"
check_env_var "INSTAGRAM_ACCESS_TOKEN" "Instagram API"
check_env_var "TWITTER_API_KEY" "X/Twitter API"

if [[ -n "$(read_env PUBLISH_SCHEDULE_CRON)" ]]; then
  echo "  ✅ Auto-publish schedule configured"
else
  echo "  ⬜ Auto-publish: using default 60s poll interval"
fi

if [[ -z "$PUBLIC_BASE_URL" ]]; then
  echo "  ⬜ PUBLIC_BASE_URL not set — TikTok/Instagram publishing will show manual instructions"
  echo "     Set it to your ngrok URL if you need direct TikTok/IG publishing:"
  echo "     export PUBLIC_BASE_URL=https://your-ngrok-url.ngrok.io"
fi
echo ""

# ──────────────────────────────────────────────
# 10) Cleanup background processes on exit
# ──────────────────────────────────────────────
cleanup() {
  if [[ -n "${UVICORN_PID:-}" ]]; then
    echo "Stopping uvicorn (PID $UVICORN_PID)..."
    kill "$UVICORN_PID" >/dev/null 2>&1 || true
    wait "$UVICORN_PID" 2>/dev/null || true
  fi
  if [[ -n "${OLLAMA_PID:-}" ]]; then
    echo "Stopping Ollama (PID $OLLAMA_PID)..."
    kill "$OLLAMA_PID" >/dev/null 2>&1 || true
  fi
  if [[ -n "${PUBLISH_WORKER_PID:-}" ]]; then
    echo "Stopping publish worker (PID $PUBLISH_WORKER_PID)..."
    kill "$PUBLISH_WORKER_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

# ──────────────────────────────────────────────
# 11) Start auto-publish worker
# ──────────────────────────────────────────────
PUBLISH_WORKER_PID=""
if [[ "$(read_env DEV_PUBLISH_MOCK)" == "true" ]]; then
  echo "Starting dev publish mock worker..."
  python -m backend.app.services.publisher --mock &
  PUBLISH_WORKER_PID=$!
elif [[ -n "$(read_env PUBLISH_SCHEDULE_CRON)" ]]; then
  echo "Starting scheduled publish worker (cron: $PUBLISH_SCHEDULE_CRON)..."
  python -m backend.app.services.scheduler &
  PUBLISH_WORKER_PID=$!
else
  echo "Starting default publish scheduler (60s poll interval)..."
  python -m backend.app.services.scheduler &
  PUBLISH_WORKER_PID=$!
fi
if [[ "$JWT_SECRET_VAL" == "nexus-dev-secret-change-in-production" ]]; then
  echo "  Generating secure JWT secret..."
  NEW_SECRET="$(python3 -c "import secrets; print(secrets.token_hex(32))")"
  if grep -q "^JWT_SECRET=" .env; then
    if [[ "$(uname)" == "Darwin" ]]; then
      sed -i '' "s/^JWT_SECRET=.*/JWT_SECRET=$NEW_SECRET/" .env
    else
      sed -i "s/^JWT_SECRET=.*/JWT_SECRET=$NEW_SECRET/" .env
    fi
  else
    echo "JWT_SECRET=$NEW_SECRET" >> .env
  fi
  echo "  ✅ JWT secret updated in .env"
fi

ADMIN_MARKER="backend/data/.admin_created"
if [[ -f "$ADMIN_MARKER" ]]; then
  ADMIN_SETUP="✅ Admin created (lock active)"
else
  ADMIN_SETUP="⬜ First user will become admin"
fi
echo ""
echo "  ${ADMIN_SETUP}"
echo "  Admin:     http://${HOST}:${PORT}/admin-login.html"
echo "  Setup:     http://${HOST}:${PORT}/setup.html"
echo "═══════════════════════════════════════════════════════════════"
echo ""

WORKER_FLAG=""
if [[ "$UVICORN_WORKERS" -gt 1 ]] && ! dev_reload_enabled "$DEV_RELOAD"; then
  WORKER_FLAG="--workers ${UVICORN_WORKERS}"
fi

if dev_reload_enabled "$DEV_RELOAD"; then
  uvicorn backend.app.main:app --reload --host "$HOST" --port "$PORT" &
else
  uvicorn backend.app.main:app --host "$HOST" --port "$PORT" $WORKER_FLAG &
fi

UVICORN_PID=$!

# ──────────────────────────────────────────────
# 12) Health check
# ──────────────────────────────────────────────
if [[ "$HEALTH_CHECK" == "true" ]]; then
  echo "  Waiting for server to be ready..."
  for i in $(seq 1 30); do
    if curl -sSf "http://${HOST}:${PORT}/health" >/dev/null 2>&1; then
      echo "  ✅ Server is ready!"
      break
    fi
    if [[ $i -eq 30 ]]; then
      echo "  ⚠️  Server did not respond within 30s. Check logs for errors."
    fi
    sleep 1
  done
fi

echo ""
echo "  Nexus-UGC is running at http://${HOST}:${PORT}"
echo "  Press Ctrl+C to stop"
echo "═══════════════════════════════════════════════════════════════"

wait $UVICORN_PID $PUBLISH_WORKER_PID
