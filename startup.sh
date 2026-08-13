#!/usr/bin/env bash
# Azure App Service startup script for Nexus-UGC
set -euo pipefail

echo "Nexus-UGC starting on Azure App Service..."

# Auto-generate JWT secret if still using default
if grep -q "^JWT_SECRET=nexus-dev-secret-change-in-production" .env 2>/dev/null; then
  NEW_SECRET="$(python3 -c "import secrets; print(secrets.token_hex(32))")"
  if [[ -f .env ]]; then
    sed -i "s/^JWT_SECRET=.*/JWT_SECRET=$NEW_SECRET/" .env
  else
    echo "JWT_SECRET=$NEW_SECRET" >> .env
  fi
  echo "✅ Auto-generated JWT secret"
fi

# Ensure data directories exist
mkdir -p backend/data/clips backend/data/backgrounds

# Clear stale Python cache
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

echo "Using database: ${DATABASE_URL:-sqlite:///backend/data/nexus.db}"
echo "Public URL: ${PUBLIC_BASE_URL:-not set}"

exec uvicorn backend.app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
