#!/usr/bin/env bash
set -euo pipefail

echo "[INFO] Revertendo alteraÃ§Ãµes para origin/main" >&2

git checkout main
git fetch origin
git reset --hard origin/main

if [ -x ./restart-app.sh ]; then
  ./restart-app.sh
fi

pkill -f start_rq_worker.py || true
nohup python start_rq_worker.py webhook > logs/rq-webhook.log 2>&1 &
nohup python start_rq_worker.py gateway > logs/rq-gateway.log 2>&1 &
nohup python start_rq_worker.py tasks > logs/rq-tasks.log 2>&1 &
pkill -f celery || true
nohup celery -A celery_app worker -l info > logs/celery.log 2>&1 &

echo "[OK] Rollback concluido." >&2
