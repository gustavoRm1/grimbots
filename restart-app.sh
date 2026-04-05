#!/usr/bin/env bash
#
# restart-app.sh - Script de deploy para GrimBots
# Versão limpa e robusta para produção
#
set -euo pipefail

cd "$(dirname "$0")"

# VALIDAÇÃO PRÉ-DEPLOY
if [[ ! -d "venv" ]]; then
  echo " Virtualenv 'venv' não encontrado. Abortando."
  exit 1
fi

if [[ ! -f ".env" ]]; then
  echo " Arquivo .env não encontrado. Abortando."
  exit 1
fi

# FUNÇÃO: Carregar .env de forma segura
load_env_safely() {
  # Usar python-dotenv se disponível (mais seguro para chaves multilinha)
  if python3 -c "import dotenv" 2>/dev/null; then
    eval "$(python3 << 'PYEOF'
from dotenv import dotenv_values
import os, shlex

env_vars = dotenv_values('.env')
for key, value in env_vars.items():
    if value is not None:
        # Preservar \n literal como string
        if isinstance(value, str) and '\n' in value:
            value = value.replace('\n', '\\n').replace('\r', '')
        print(f"export {key}={shlex.quote(str(value))}")
PYEOF
)"
  else
    # Fallback: carregar manualmente
    set -a
    while IFS= read -r line || [[ -n "$line" ]]; do
      [[ "$line" =~ ^[[:space:]]*# ]] && continue
      [[ -z "${line// }" ]] && continue
      [[ ! "$line" =~ ^[[:space:]]*[A-Za-z_][A-Za-z0-9_]*= ]] && continue
      export "$line"
    done < <(grep -v "^[[:space:]]*#" .env)
    set +a
  fi
}

# CARREGAR VARIÁVEIS
load_env_safely

# ATIVAR VIRTUALENV
source venv/bin/activate

# VERIFICAÇÃO DE SINTAXE (BLOQUEIA DEPLOY SE QUEBRADO)
echo " Validando sintaxe Python..."
python -m py_compile app.py bot_manager.py tasks_async.py || {
  echo " ERRO DE SINTAXE: Arquivos Python contêm erros. Deploy abortado!"
  exit 1
}
echo " Sintaxe Python validada"

# VALIDAR IMPORTAÇÃO (CRÍTICO - evita deploy quebrado)
echo " Testando importação do app..."
python -c "from app import app; print(' App importa corretamente')" || {
  echo " ERRO: App não pode ser importado! Verifique as dependências."
  exit 1
}

# LIBERAR PORTA 5000 (portável: não depende de lsof)
echo " Verificando porta 5000..."
PORT_PID=""
if command -v ss >/dev/null 2>&1; then
    PORT_PID=$(ss -tlnp 2>/dev/null | grep ':5000' | grep -oP 'pid=\K[0-9]+' | head -1)
elif command -v netstat >/dev/null 2>&1; then
    PORT_PID=$(netstat -tlnp 2>/dev/null | grep ':5000' | awk '{print $7}' | cut -d'/' -f1 | head -1)
elif command -v lsof >/dev/null 2>&1; then
    PORT_PID=$(lsof -ti:5000 2>/dev/null | head -1)
fi

if [[ -n "$PORT_PID" ]]; then
    echo "   Porta 5000 em uso (PID: $PORT_PID), liberando..."
    kill -9 "$PORT_PID" 2>/dev/null || true
    sleep 1
fi

# ENCERRAR WORKERS RQ
echo " Encerrando workers RQ..."
if pgrep -f start_rq_worker.py >/dev/null 2>&1; then
    pgrep -f start_rq_worker.py | xargs -r kill -9 2>/dev/null || true
fi

# INICIAR WORKERS RQ
echo " Iniciando workers RQ..."
mkdir -p logs

# Workers de Infra
nohup python3 start_rq_worker.py gateway > logs/rq-gateway.log 2>&1 &
nohup python3 start_rq_worker.py webhook > logs/rq-webhook.log 2>&1 &

# Via Expressa (Alta Prioridade)
nohup python3 start_rq_worker.py tasks > logs/rq-tasks-1.log 2>&1 &
nohup python3 start_rq_worker.py tasks > logs/rq-tasks-2.log 2>&1 &

# Trem de Carga (Remarketing)
nohup python3 start_rq_worker.py marathon > logs/rq-marathon-1.log 2>&1 &
nohup python3 start_rq_worker.py marathon > logs/rq-marathon-2.log 2>&1 &
nohup python3 start_rq_worker.py marathon > logs/rq-marathon-3.log 2>&1 &
nohup python3 start_rq_worker.py marathon > logs/rq-marathon-4.log 2>&1 &

echo ""
echo " Workers RQ reiniciados com sucesso!"
echo ""
echo " Comandos úteis:"
echo "   sudo systemctl status grimbots    # Status do serviço"
echo "   tail -f logs/rq-*.log             # Logs dos workers"
echo "   curl http://localhost:5000/health # Health check"
echo ""
