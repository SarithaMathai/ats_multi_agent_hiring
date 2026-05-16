#!/usr/bin/env bash
# ── setup.sh ──────────────────────────────────────────────────────────────────
# One-time dev environment setup.
# Usage: bash scripts/setup.sh

set -euo pipefail

echo "==> Checking prerequisites..."
command -v python3 >/dev/null 2>&1 || { echo "Python 3 is required"; exit 1; }
command -v poetry  >/dev/null 2>&1 || { echo "Poetry is required — see https://python-poetry.org/docs/#installation"; exit 1; }
command -v docker  >/dev/null 2>&1 || { echo "Docker is required"; exit 1; }

echo "==> Installing Python dependencies..."
poetry install --no-interaction

echo "==> Setting up pre-commit hooks..."
poetry run pre-commit install

echo "==> Copying .env.example to .env (if not already present)..."
if [ ! -f .env ]; then
  cp .env.example .env
  echo "    Created .env — fill in your ANTHROPIC_API_KEY before running."
fi

echo "==> Starting Docker services (postgres, chromadb, redis)..."
docker compose up -d postgres chromadb redis

echo "==> Waiting for PostgreSQL to be ready..."
until docker compose exec postgres pg_isready -U ats_user -d ats_db > /dev/null 2>&1; do
  echo "    Waiting..."
  sleep 2
done

echo "==> Running database migrations..."
poetry run alembic upgrade head

echo ""
echo "Setup complete. Start the app with:"
echo "  poetry run uvicorn app.main:app --reload"
echo "  -- or --"
echo "  docker compose up"
