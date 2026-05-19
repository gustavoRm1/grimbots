#!/bin/bash
# INICIO MANUAL - SEM SYSTEMD PARA RQ WORKERS
# Gunicorn via systemd, Workers via nohup

echo "=========================================="
echo "  INICIO MANUAL - GRIMBOTS QI 500"
echo "=========================================="
echo ""

cd ~/grimbots || cd /root/grimbots || exit 1
source venv/bin/activate

# 1. Matar tudo
echo "💀 Matando processos..."
pkill -9 python 2>/dev/null || true
pkill -9 gunicorn 2>/dev/null || true
fuser -k 5000/tcp 2>/dev/null || true
sleep 3
echo "✅ Processos mortos"

# 2. Iniciar Gunicorn via systemd
echo ""
echo "🚀 Iniciando Gunicorn (systemd)..."
sudo systemctl daemon-reload
sudo systemctl enable grimbots 2>/dev/null || true
sudo systemctl start grimbots

sleep 5

if sudo systemctl is-active --quiet grimbots; then
    echo "✅ Gunicorn RODANDO"
else
    echo "❌ Gunicorn FALHOU"
    sudo journalctl -u grimbots -n 20
    exit 1
fi

# 3. Iniciar RQ Workers manualmente (nohup)
echo ""
echo "🚀 Iniciando RQ Workers (nohup)..."

# Tasks (5 workers)
for i in {1..5}; do 
    nohup python start_rq_worker.py tasks > logs/rq-tasks-$i.log 2>&1 &
    echo "  ✅ tasks-$i iniciado (PID: $!)"
done

# Gateway (3 workers)
for i in {1..3}; do 
    nohup python start_rq_worker.py gateway > logs/rq-gateway-$i.log 2>&1 &
    echo "  ✅ gateway-$i iniciado (PID: $!)"
done

# Webhook (3 workers)
for i in {1..3}; do 
    nohup python start_rq_worker.py webhook > logs/rq-webhook-$i.log 2>&1 &
    echo "  ✅ webhook-$i iniciado (PID: $!)"
done

sleep 5

# 4. Verificar
echo ""
echo "🔍 Verificando processos..."

GUNICORN_COUNT=$(ps aux | grep -c "[g]unicorn" || echo "0")
WORKER_COUNT=$(ps aux | grep -c "[s]tart_rq_worker" || echo "0")

echo "  Gunicorn processes: $GUNICORN_COUNT"
echo "  RQ Worker processes: $WORKER_COUNT"

# 5. Health check
echo ""
echo "🏥 Health check..."
sleep 3

HEALTH=$(curl -s http://localhost:5000/health 2>/dev/null)
STATUS=$(echo "$HEALTH" | grep -o '"status": "[^"]*"' | cut -d'"' -f4)

echo "Status: $STATUS"

if [ "$STATUS" = "healthy" ]; then
    echo "✅ Sistema SAUDÁVEL"
else
    echo "⚠️  Sistema DEGRADADO"
    echo "$HEALTH" | python3 -m json.tool 2>/dev/null || echo "$HEALTH"
fi

# 6. Resumo
echo ""
echo "=========================================="
echo "  RESUMO"
echo "=========================================="
echo ""
echo "✅ Gunicorn: $(sudo systemctl is-active grimbots)"
echo "✅ RQ Workers: $WORKER_COUNT/11"
echo "✅ Health: $STATUS"
echo ""
echo "Comandos úteis:"
echo "  sudo systemctl status grimbots"
echo "  ps aux | grep start_rq_worker"
echo "  curl http://localhost:5000/health"
echo "  tail -f logs/error.log"
echo ""

