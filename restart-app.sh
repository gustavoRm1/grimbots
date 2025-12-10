#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ ! -d "venv" ]]; then
  echo "⚠️ Virtualenv 'venv' não encontrado. Abortando."
  exit 1
fi

# Exportar variáveis do .env (para SECRET_KEY, ENCRYPTION_KEY, REDIS_URL, etc.)
# ✅ CORREÇÃO: Usar python-dotenv para carregar .env de forma segura
# Isso evita problemas quando VAPID_PRIVATE_KEY tem quebras de linha
if [[ -f ".env" ]]; then
  # Tentar usar python-dotenv se disponível (mais seguro)
  if python3 -c "import dotenv" 2>/dev/null; then
    # Usar dotenv para carregar e exportar
    eval "$(python3 << 'PYEOF'
from dotenv import dotenv_values
import os

env_vars = dotenv_values('.env')
for key, value in env_vars.items():
    if value is not None:
        # Escapar para bash de forma segura
        import shlex
        # Preservar \n literal como string
        if isinstance(value, str) and '\n' in value:
            # Substituir quebras reais por \n literal para export
            value = value.replace('\n', '\\n').replace('\r', '')
        print(f"export {key}={shlex.quote(str(value))}")
PYEOF
)"
  else
    # Fallback: carregar manualmente, mas pular linhas problemáticas
    set -a
    while IFS= read -r line || [ -n "$line" ]; do
      # Ignorar comentários, linhas vazias e linhas que não são KEY=VALUE
      [[ "$line" =~ ^[[:space:]]*# ]] && continue
      [[ -z "${line// }" ]] && continue
      [[ ! "$line" =~ ^[[:space:]]*[A-Za-z_][A-Za-z0-9_]*= ]] && continue
      
      # ✅ Pular VAPID_PRIVATE_KEY aqui (será carregada via Python se necessário)
      [[ "$line" =~ ^[[:space:]]*VAPID_PRIVATE_KEY= ]] && continue
      
      # Exportar outras variáveis normalmente
      export "$line"
    done < <(grep -v "^VAPID_PRIVATE_KEY=" .env | grep -v "^[[:space:]]*#")
    set +a
    
    # ✅ Carregar VAPID_PRIVATE_KEY separadamente se existir
    if grep -q "^VAPID_PRIVATE_KEY=" .env; then
      VAPID_PRIVATE_KEY_VALUE=$(python3 -c "
import re
with open('.env', 'r') as f:
    content = f.read()
    match = re.search(r'^VAPID_PRIVATE_KEY=(.*?)(?=^[A-Z_]|$)', content, re.MULTILINE | re.DOTALL)
    if match:
        value = match.group(1).strip()
        # Se contém \n literal, manter; se tem quebras reais, converter para \n literal
        if '\n' in value and '\\n' not in value:
            value = value.replace('\n', '\\n')
        print(value)
" 2>/dev/null)
      if [ -n "$VAPID_PRIVATE_KEY_VALUE" ]; then
        export VAPID_PRIVATE_KEY="$VAPID_PRIVATE_KEY_VALUE"
      fi
    fi
  fi
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

