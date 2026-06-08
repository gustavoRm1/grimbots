#!/bin/bash
# ============================================================================
# RESTART COMPLETO — Grimbots v2 (alinhado com commit 3ca35cd+)
# ============================================================================
# Uso: sudo bash restart-system.sh
# Mata workers antigos → Atualiza Redis → Sobe Nginx → Sobe Gunicorn → Sobe RQ
# ============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

VENV_PYTHON="$SCRIPT_DIR/venv/bin/python"

echo "🔄 [1/7] Garantindo Redis..."
sudo systemctl start redis
sleep 1
if redis-cli ping 2>/dev/null | grep -q PONG; then
    echo "   ✅ Redis online."
else
    echo "   ❌ Redis não respondeu!" >&2
    exit 1
fi

echo "🌐 [2/7] Reiniciando Nginx..."
if systemctl is-active --quiet nginx 2>/dev/null; then
    sudo nginx -t && sudo systemctl reload nginx
    echo "   ✅ Nginx recarregado."
else
    echo "   ⚠️ Nginx não está instalado/ativo — pule se for usar Cloudflare Tunnel."
fi

echo "💀 [3/7] Derrubando workers RQ antigos com grace period..."
for unit in $(systemctl list-units --type=service --state=running 2>/dev/null | grep 'rq-worker' | awk '{print $1}'); do
    sudo systemctl stop "$unit"
    echo "   ⏹️  $unit parado."
done
# Fallback: matar qualquer processo RQ solto (nohup, testes, etc)
pkill -f "start_rq_worker.py" 2>/dev/null || true
sleep 2

echo "🌐 [4/7] Reiniciando Servidor Web (Gunicorn + Painel)..."
sudo systemctl restart grimbots
sleep 3
if systemctl is-active --quiet grimbots; then
    echo "   ✅ Web Server reiniciado (127.0.0.1:5000)."
else
    echo "   ❌ Web Server FALHOU! Logs:" >&2
    sudo journalctl -u grimbots -n 20 --no-pager || true
    exit 1
fi

echo "🔍 [4b/7] Health check..."
for i in 1 2 3; do
    if curl -sf http://127.0.0.1:5000/health > /dev/null 2>&1; then
        echo "   ✅ Health check OK (tentativa $i)."
        break
    fi
    echo "   ⏳ Aguardando Gunicorn (tentativa $i)..."
    sleep 2
done
if ! curl -sf http://127.0.0.1:5000/health > /dev/null 2>&1; then
    echo "   ❌ Health check falhou após restart!" >&2
    exit 1
fi

echo "🤖 [5/7] Levantando Workers RQ via systemd..."
# tasks=5, gateway=3, webhook=3, marathon=1 — escala para 200k visitas/dia
declare -A WORKER_COUNTS=(
    ["tasks"]=5
    ["gateway"]=3
    ["webhook"]=3
    ["marathon"]=1
)
QUEUES=("tasks" "gateway" "webhook" "marathon")
for q in "${QUEUES[@]}"; do
    count=${WORKER_COUNTS[$q]}
    for i in $(seq 1 $count); do
        sudo systemctl start "rq-worker@${q}-${i}" 2>/dev/null || {
            echo "   ⚠️  rq-worker@${q}-${i} não encontrado como template — subindo via nohup..."
            nohup "$VENV_PYTHON" start_rq_worker.py "$q" > "worker_${q}_${i}.log" 2>&1 &
        }
    done
    echo "   ✅ Worker: $q ($count instâncias)."
done

echo "📅 [6/7] Reiniciando RQ Scheduler..."
sudo systemctl restart rq-scheduler 2>/dev/null || {
    echo "   ⚠️  rq-scheduler.service não encontrado — ignorado."
}

echo "🚀 [7/7] Sistema 100% operacional!"
echo "   📊 Gunicorn:  http://127.0.0.1:5000/health"
echo "   🤖 Workers:   ${QUEUES[*]}"
echo "   🗄️  Redis:     $(redis-cli ping 2>/dev/null || echo 'offline')"
