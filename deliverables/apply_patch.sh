#!/usr/bin/env bash
set -euo pipefail

PATCH_PATH="deliverables/hotfix_tracking.patch"

if ! git apply --check "$PATCH_PATH" >/dev/null 2>&1; then
  echo "[INFO] Patch already applied or conflicts detected. Skipping git apply." >&2
else
  git apply "$PATCH_PATH"
  echo "[OK] Patch aplicado com sucesso."
fi
