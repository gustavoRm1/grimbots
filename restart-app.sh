#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -d "venv" ]]; then
  echo "⚠️ Virtualenv 'venv' não encontrado. Abortando."
  exit 1
fi

# Exportar variáveis do .env (para SECRET_KEY, ENCRYPTION_KEY, REDIS_URL, etc.)
if [[ -f ".env" ]]; then
  set -a
  source .env
  set +a
fi

source venv/bin/activate

echo "🚫 Encerrando Gunicorn..."
if pgrep -f "gunicorn.*wsgi:app" >/dev/null; then
  pgrep -f "gunicorn.*wsgi:app" | xargs -r kill -9
fi
pkill -9 -f gunicorn 2>/dev/null || true
sleep 1

echo "🚫 Removendo arquivo PID stale..."
rm -f grimbots.pid
rm -f logs/gunicorn.pid

echo "🚫 Verificando porta 5000..."
if lsof -ti:5000 >/dev/null 2>&1; then
  echo "   ⚠️  Porta 5000 em uso, liberando..."
  lsof -ti:5000 | xargs kill -9 2>/dev/null || true
  sleep 1
fi

echo "🚫 Encerrando workers RQ..."
if pgrep -f start_rq_worker.py >/dev/null; then
  pgrep -f start_rq_worker.py | xargs -r kill -9
fi

echo "🧪 Testando importação do app..."
python -c "from app import app; print('✅ App OK')" || {
  echo "❌ ERRO: App não pode ser importado! Verifique os logs acima."
  exit 1
}

echo "🚀 Iniciando Gunicorn (1 worker eventlet)..."
EVENTLET_NO_GREENDNS=yes nohup gunicorn -w 1 -k eventlet -c gunicorn_config.py wsgi:app > logs/gunicorn.log 2>&1 &
GUNICORN_PID=$!
sleep 3

# Verificar se Gunicorn iniciou
if ps -p $GUNICORN_PID > /dev/null 2>&1; then
  echo "✅ Gunicorn iniciado (PID: $GUNICORN_PID)"
else
  echo "❌ ERRO: Gunicorn não iniciou! Verifique logs/gunicorn.log"
  tail -50 logs/gunicorn.log
  exit 1
fi

echo "⚙️ Iniciando workers RQ..."
nohup python3 start_rq_worker.py gateway > logs/rq-gateway.log 2>&1 &
nohup python3 start_rq_worker.py tasks   > logs/rq-tasks.log   2>&1 &
nohup python3 start_rq_worker.py webhook > logs/rq-webhook.log 2>&1 &

deactivate

echo "✅ Aplicação reiniciada com sucesso."

