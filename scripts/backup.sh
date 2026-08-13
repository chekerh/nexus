#!/usr/bin/env bash
# Nexus-UGC Backup Script
# Backs up SQLite/PostgreSQL database + uploads to a timestamped archive.
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_PATH="${BACKUP_DIR}/nexus-ugc_${TIMESTAMP}"

mkdir -p "$BACKUP_PATH"

echo "=== Nexus-UGC Backup: $TIMESTAMP ==="

# --- Database ---
if [[ -n "${DATABASE_URL:-}" ]]; then
  echo "Backing up PostgreSQL database..."
  pg_dump "${DATABASE_URL}" > "${BACKUP_PATH}/database.sql"
  echo "  → database.sql (PostgreSQL dump)"
elif [[ -f "backend/data/nexus.db" ]]; then
  echo "Backing up SQLite database..."
  cp "backend/data/nexus.db" "${BACKUP_PATH}/nexus.db"
  echo "  → nexus.db"
else
  echo "  ⚠️  No database file found"
fi

# --- Uploads ---
UPLOAD_DIR="${UPLOAD_DIR:-backend/data}"
if [[ -d "$UPLOAD_DIR" ]]; then
  echo "Backing up uploads from ${UPLOAD_DIR}..."
  tar czf "${BACKUP_PATH}/uploads.tar.gz" -C "$(dirname "$UPLOAD_DIR")" "$(basename "$UPLOAD_DIR")" 2>/dev/null || \
    cp -r "$UPLOAD_DIR" "${BACKUP_PATH}/uploads"
  echo "  → uploads archived"
else
  echo "  ⚠️  Upload directory not found: $UPLOAD_DIR"
fi

# --- .env (redacted) ---
if [[ -f ".env" ]]; then
  cp ".env" "${BACKUP_PATH}/.env"
  echo "  → .env (contains secrets — keep secure)"
fi

# --- Compress ---
echo "Compressing backup..."
tar czf "${BACKUP_DIR}/nexus-ugc_${TIMESTAMP}.tar.gz" -C "$BACKUP_DIR" "nexus-ugc_${TIMESTAMP}"
rm -rf "$BACKUP_PATH"
echo ""
echo "✅ Backup complete: ${BACKUP_DIR}/nexus-ugc_${TIMESTAMP}.tar.gz"
echo "   Size: $(du -h "${BACKUP_DIR}/nexus-ugc_${TIMESTAMP}.tar.gz" | cut -f1)"
