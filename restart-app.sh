#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -d "venv" ]]; then
  echo "⚠️ Virtualenv 'venv' não encontrado. Abortando."
  exit 1
fi

source venv/bin/activate

echo "🚫 Encerrando Gunicorn..."
pgrep -f "gunicorn.*wsgi:app" | xargs -r kill -9

echo "🚫 Encerrando workers RQ..."
pgrep -f start_rq_worker.py | xargs -r kill -9

echo "🚀 Iniciando Gunicorn (1 worker eventlet)..."
EVENTLET_NO_GREENDNS=yes nohup gunicorn -w 1 -k eventlet -c gunicorn_config.py wsgi:app > logs/gunicorn.log 2>&1 &

echo "⚙️ Iniciando workers RQ..."
nohup python3 start_rq_worker.py gateway > logs/rq-gateway.log 2>&1 &
nohup python3 start_rq_worker.py tasks   > logs/rq-tasks.log   2>&1 &
nohup python3 start_rq_worker.py webhook > logs/rq-webhook.log 2>&1 &

deactivate

echo "✅ Aplicação reiniciada com sucesso."

