#!/bin/bash
# ✅ QI 500: Script para corrigir workers duplicados e limpar sistema

echo "=========================================="
echo "🔧 CORREÇÃO QI 500 - Workers Duplicados"
echo "=========================================="
echo ""

# PASSO 1: Matar todos os workers duplicados
echo "📋 PASSO 1: Verificando workers ativos..."
ps aux | grep "start_rq_worker" | grep -v grep

echo ""
echo "⚠️  Matando todos os workers RQ..."
pkill -f "start_rq_worker.py" || echo "Nenhum worker encontrado"
sleep 2

# Verificar se ainda há workers
REMAINING=$(ps aux | grep "start_rq_worker" | grep -v grep | wc -l)
if [ "$REMAINING" -gt 0 ]; then
    echo "⚠️  Ainda há workers ativos, forçando kill..."
    pkill -9 -f "start_rq_worker.py"
    sleep 1
fi

echo "✅ Workers parados"
echo ""

# PASSO 2: Limpar filas Redis
echo "📋 PASSO 2: Limpando filas Redis..."
redis-cli FLUSHALL
echo "✅ Filas Redis limpas"
echo ""

# PASSO 3: Criar diretório de logs se não existir
echo "📋 PASSO 3: Preparando ambiente..."
cd /root/grimbots || cd ~/grimbots || exit 1
mkdir -p logs
source venv/bin/activate || echo "⚠️  Virtualenv não encontrado, continuando..."

echo "✅ Ambiente preparado"
echo ""

# PASSO 4: Iniciar workers via systemd
echo "📋 PASSO 4: Iniciando workers via systemd..."
echo ""

# Verificar se os serviços systemd existem
if [ -f /etc/systemd/system/rq-worker-tasks.service ] && \
   [ -f /etc/systemd/system/rq-worker-gateway.service ] && \
   [ -f /etc/systemd/system/rq-worker-webhook.service ]; then
    
    echo "🔄 Recarregando systemd..."
    systemctl daemon-reload
    
    echo "🔄 Iniciando serviço rq-worker-tasks..."
    systemctl enable rq-worker-tasks > /dev/null 2>&1
    systemctl start rq-worker-tasks
    sleep 1
    
    echo "🔄 Iniciando serviço rq-worker-gateway..."
    systemctl enable rq-worker-gateway > /dev/null 2>&1
    systemctl start rq-worker-gateway
    sleep 1
    
    echo "🔄 Iniciando serviço rq-worker-webhook..."
    systemctl enable rq-worker-webhook > /dev/null 2>&1
    systemctl start rq-worker-webhook
    sleep 1
    
    echo ""
    echo "✅ Workers iniciados via systemd"
    echo ""
    
    # Verificar status
    echo "📊 Status dos serviços:"
    systemctl status rq-worker-tasks --no-pager -l | head -5
    systemctl status rq-worker-gateway --no-pager -l | head -5
    systemctl status rq-worker-webhook --no-pager -l | head -5
else
    echo "⚠️  Serviços systemd não encontrados, iniciando manualmente..."
    echo ""
    
    # Worker Gateway
    echo "🔄 Iniciando worker gateway..."
    nohup python start_rq_worker.py gateway > logs/gateway.log 2>&1 &
    GATEWAY_PID=$!
    echo "✅ Worker gateway iniciado (PID: $GATEWAY_PID)"
    
    # Worker Webhook
    echo "🔄 Iniciando worker webhook..."
    nohup python start_rq_worker.py webhook > logs/webhook.log 2>&1 &
    WEBHOOK_PID=$!
    echo "✅ Worker webhook iniciado (PID: $WEBHOOK_PID)"
    
    # Worker Tasks
    echo "🔄 Iniciando worker tasks..."
    nohup python start_rq_worker.py tasks > logs/tasks.log 2>&1 &
    TASKS_PID=$!
    echo "✅ Worker tasks iniciado (PID: $TASKS_PID)"
fi

echo ""
echo "=========================================="
echo "✅ CORREÇÃO CONCLUÍDA!"
echo "=========================================="
echo ""
echo "Workers ativos:"
ps aux | grep "start_rq_worker" | grep -v grep
echo ""
echo "Verificar logs (systemd):"
echo "  sudo journalctl -u rq-worker-tasks -f"
echo "  sudo journalctl -u rq-worker-gateway -f"
echo "  sudo journalctl -u rq-worker-webhook -f"
echo ""
echo "Verificar status:"
echo "  sudo systemctl status rq-worker-tasks"
echo "  sudo systemctl status rq-worker-gateway"
echo "  sudo systemctl status rq-worker-webhook"
echo "  ps aux | grep start_rq_worker"
echo ""

