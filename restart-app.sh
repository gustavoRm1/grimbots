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

# REINICIAR WORKERS VIA SYSTEMD (SRE: Resiliência garantida pelo systemd)
echo "🔄 Reiniciando workers RQ via systemctl..."

# Parar todas as instâncias de workers primeiro
for i in gateway-1 gateway-2 webhook-1 webhook-2 tasks-1 tasks-2 marathon-1 marathon-2 marathon-3 marathon-4; do
    systemctl stop rq-worker@$i 2>/dev/null || true
done

# Pequena pausa para garantir liberação de recursos
sleep 2

# Iniciar workers na ordem correta: Infra → Via Expressa → Trem de Carga
systemctl start rq-worker@gateway-1
systemctl start rq-worker@gateway-2
systemctl start rq-worker@webhook-1
systemctl start rq-worker@webhook-2
systemctl start rq-worker@tasks-1
systemctl start rq-worker@tasks-2
systemctl start rq-worker@marathon-1
systemctl start rq-worker@marathon-2
systemctl start rq-worker@marathon-3
systemctl start rq-worker@marathon-4

# Recarregar daemon do systemd (caso o arquivo .service tenha mudado)
systemctl daemon-reload 2>/dev/null || true

# Habilitar auto-start no boot
for i in gateway-1 gateway-2 webhook-1 webhook-2 tasks-1 tasks-2 marathon-1 marathon-2 marathon-3 marathon-4; do
    systemctl enable rq-worker@$i 2>/dev/null || true
done

echo ""
echo "✅ Workers RQ reiniciados via systemctl!"
echo ""
echo "📋 Comandos úteis:"
echo "   sudo systemctl status rq-worker@tasks-1   # Status de um worker"
echo "   sudo journalctl -u rq-worker@marathon-1 -f # Logs em tempo real"
echo "   sudo systemctl list-units 'rq-worker@*'    # Listar todos os workers"
echo "   curl http://localhost:5000/health         # Health check da API"
echo ""
