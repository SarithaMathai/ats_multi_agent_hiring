#!/usr/bin/env bash
# ── migrate.sh ────────────────────────────────────────────────────────────────
# Apply pending Alembic migrations.
# Usage:
#   bash scripts/migrate.sh              # upgrade to head
#   bash scripts/migrate.sh downgrade -1 # rollback one step
#   bash scripts/migrate.sh revision --autogenerate -m "add_candidates_table"

set -euo pipefail

ACTION="${1:-upgrade}"
TARGET="${2:-head}"

echo "==> Running: alembic ${ACTION} ${TARGET}"
poetry run alembic "${ACTION}" "${TARGET}"
echo "Done."
