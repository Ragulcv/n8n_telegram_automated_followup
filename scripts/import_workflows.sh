#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! docker info >/dev/null 2>&1; then
  echo "[FAIL] Docker daemon is not running"
  exit 1
fi

if ! docker compose ps n8n >/dev/null 2>&1; then
  echo "[FAIL] n8n container is not running. Run: docker compose up -d"
  exit 1
fi

for workflow in n8n/workflows/*.json; do
  echo "Importing $workflow"
  docker compose exec -T n8n n8n import:workflow --input="/workflows/$(basename "$workflow")" || {
    echo "[WARN] Import failed for $workflow"
  }
done

echo "Done importing workflows."
