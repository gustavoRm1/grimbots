#!/bin/bash
# Script para diagnosticar e corrigir workers RQ

echo "=========================================="
echo " Diagnóstico e Correção Workers RQ"
echo "=========================================="

echo ""
echo "1. Verificando logs do systemd:"
echo "--- rq-worker-tasks ---"
sudo journalctl -u rq-worker-tasks -n 50 --no-pager | tail -20

echo ""
echo "2. Verificando Redis:"
if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis está rodando"
else
    echo "❌ Redis NÃO está rodando"
    echo "   Iniciando Redis..."
    sudo systemctl start redis
    sleep 2
    redis-cli ping
fi

echo ""
echo "3. Verificando RQ instalado:"
if /root/grimbots/venv/bin/python -c "import rq" 2>/dev/null; then
    echo "✅ RQ está instalado"
else
    echo "❌ RQ NÃO está instalado"
    echo "   Instalando RQ..."
    /root/grimbots/venv/bin/pip install rq
fi

echo ""
echo "4. Testando execução manual:"
cd /root/grimbots
source venv/bin/activate
python start_rq_worker.py tasks &
WORKER_PID=$!
sleep 2
if ps -p $WORKER_PID > /dev/null; then
    echo "✅ Worker iniciou com sucesso (PID: $WORKER_PID)"
    kill $WORKER_PID
else
    echo "❌ Worker falhou ao iniciar"
    echo "   Verifique os erros acima"
fi

echo ""
echo "5. Reiniciando serviços systemd:"
sudo systemctl restart rq-worker-tasks
sudo systemctl restart rq-worker-gateway
sudo systemctl restart rq-worker-webhook

sleep 3

echo ""
echo "6. Status final:"
sudo systemctl status rq-worker-tasks --no-pager -l | head -15
sudo systemctl status rq-worker-gateway --no-pager -l | head -15
sudo systemctl status rq-worker-webhook --no-pager -l | head -15

