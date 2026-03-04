#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <target-dir>"
  echo "Example: $0 /tmp/sheets"
  exit 1
fi

TARGET_DIR="$1"
mkdir -p "$TARGET_DIR"
cp sheets/templates/*.csv "$TARGET_DIR/"

echo "Copied templates to $TARGET_DIR"
