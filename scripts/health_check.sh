#!/usr/bin/env bash
# ── health_check.sh ───────────────────────────────────────────────────────────
# Verify all services are reachable before running the app.
# Usage: bash scripts/health_check.sh

set -euo pipefail

APP_HOST="${APP_HOST:-localhost}"
APP_PORT="${APP_PORT:-8080}"
PG_HOST="${POSTGRES_HOST:-localhost}"
PG_PORT="${POSTGRES_PORT:-5432}"
CHROMA_HOST="${CHROMA_HOST:-localhost}"
CHROMA_PORT="${CHROMA_PORT:-8001}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"

check() {
  local name=$1 host=$2 port=$3
  if nc -z "$host" "$port" 2>/dev/null; then
    echo "  [OK]  $name at $host:$port"
  else
    echo "  [FAIL] $name at $host:$port — not reachable"
    FAILED=1
  fi
}

FAILED=0
echo "==> Health check..."
check "PostgreSQL" "$PG_HOST"     "$PG_PORT"
check "ChromaDB"  "$CHROMA_HOST"  "$CHROMA_PORT"
check "Redis"     "$REDIS_HOST"   "$REDIS_PORT"
check "App"       "$APP_HOST"     "$APP_PORT"

if [ "$FAILED" -eq 1 ]; then
  echo ""
  echo "One or more services are not reachable. Run: docker compose up -d"
  exit 1
fi

echo ""
echo "All services healthy."
