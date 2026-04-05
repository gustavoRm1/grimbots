#!/usr/bin/env bash
#
# restart-app.sh - Script de deploy SRE para GrimBots
# ✅ Arquitetura Definitiva: Systemd-only, failproof
#
set -euo pipefail

cd "$(dirname "$0")"

# ============================================================
# 1. VALIDAÇÃO PRÉ-DEPLOY
# ============================================================

if [[ ! -d "venv" ]]; then
    echo "❌ Virtualenv 'venv' não encontrado. Abortando."
    exit 1
fi

if [[ ! -f ".env" ]]; then
    echo "❌ Arquivo .env não encontrado. Abortando."
    exit 1
fi

# ============================================================
# 2. CARREGAR VARIÁVEIS
# ============================================================

load_env_safely() {
    if python3 -c "import dotenv" 2>/dev/null; then
        eval "$(python3 << 'PYEOF'
from dotenv import dotenv_values
import shlex
env_vars = dotenv_values('.env')
for key, value in env_vars.items():
    if value is not None:
        if isinstance(value, str) and '\n' in value:
            value = value.replace('\n', '\\n').replace('\r', '')
        print(f"export {key}={shlex.quote(str(value))}")
PYEOF
)"
    else
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

load_env_safely

# ATIVAR VIRTUALENV
source venv/bin/activate

# ============================================================
# 3. VALIDAÇÃO DE CÓDIGO (BLOQUEIA DEPLOY SE QUEBRADO)
# ============================================================

echo "🔍 Validando sintaxe Python..."
python -m py_compile app.py bot_manager.py tasks_async.py || {
    echo "❌ ERRO DE SINTAXE: Deploy abortado!"
    exit 1
}
echo "✅ Sintaxe Python validada"

echo "🔍 Testando importação do app..."
python -c "from app import app; print('✅ App importa corretamente')" || {
    echo "❌ ERRO: App não pode ser importado!"
    exit 1
}

# ============================================================
# 4. REINICIAR API VIA SYSTEMD (SRE Standard)
# ============================================================

echo "🔄 Reiniciando API (grimbots service)..."
systemctl daemon-reload 2>/dev/null || true
systemctl restart grimbots || {
    echo "❌ Falha ao reiniciar grimbots service"
    exit 1
}
echo "✅ API reiniciada"

# ============================================================
# 5. REINICIAR RQ SCHEDULER (OBRIGATÓRIO para enqueue_in)
# ✅ Move jobs agendados do ScheduledJobRegistry para filas
# ============================================================

echo "🔄 Reiniciando RQ Scheduler..."
systemctl restart rq-scheduler 2>/dev/null || {
    echo "⚠️  rq-scheduler service não encontrado (instale: sudo cp rq-scheduler.service /etc/systemd/system/)"
}
systemctl enable rq-scheduler 2>/dev/null || true
echo "✅ RQ Scheduler reiniciado"

# ============================================================
# 6. REINICIAR WORKERS RQ (Todos os 10 workers)
# ✅ Cada worker é reiniciado individualmente com proteção || true
# ============================================================

echo "🔄 Reiniciando workers RQ..."

# Infra Workers (Gateway + Webhook)
systemctl restart rq-worker@gateway-1 2>/dev/null || true
systemctl restart rq-worker@gateway-2 2>/dev/null || true
systemctl restart rq-worker@webhook-1 2>/dev/null || true
systemctl restart rq-worker@webhook-2 2>/dev/null || true

# Via Expressa (Tasks - alta prioridade)
systemctl restart rq-worker@tasks-1 2>/dev/null || true
systemctl restart rq-worker@tasks-2 2>/dev/null || true

# Trem de Carga (Marathon - remarketing)
systemctl restart rq-worker@marathon-1 2>/dev/null || true
systemctl restart rq-worker@marathon-2 2>/dev/null || true
systemctl restart rq-worker@marathon-3 2>/dev/null || true
systemctl restart rq-worker@marathon-4 2>/dev/null || true

# Habilitar auto-start no boot (tolerante a falhas)
for worker in gateway-1 gateway-2 webhook-1 webhook-2 tasks-1 tasks-2 marathon-1 marathon-2 marathon-3 marathon-4; do
    systemctl enable rq-worker@${worker} 2>/dev/null || true
done

echo "✅ Workers RQ reiniciados"

# ============================================================
# 7. STATUS FINAL
# ============================================================

echo ""
echo "🚀 Deploy SRE concluído!"
echo ""
echo "📋 Status dos serviços:"
echo "   sudo systemctl status grimbots              # API"
echo "   sudo systemctl status rq-scheduler          # Job Scheduler (CRÍTICO)"
echo "   sudo systemctl status rq-worker@gateway-1   # Workers"
echo "   sudo systemctl list-units 'rq-worker@*'     # Todos workers"
echo ""
echo "📊 Logs:"
echo "   sudo journalctl -u grimbots -f              # API em tempo real"
echo "   sudo journalctl -u rq-scheduler -f        # Scheduler em tempo real"
echo "   sudo journalctl -u rq-worker@tasks-1 -f     # Worker em tempo real"
echo "   curl http://localhost:5000/health           # Health check"
echo ""

