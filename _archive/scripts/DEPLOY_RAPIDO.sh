#!/bin/bash
# DEPLOY RÁPIDO - SEM TRAVAMENTO
# Inicia serviços em background e não aguarda

set -e

echo "=========================================="
echo "  DEPLOY RÁPIDO QI 500"
echo "=========================================="
echo ""

CURRENT_USER=$(whoami)
CURRENT_DIR=$(pwd)
VENV_PATH="$CURRENT_DIR/venv"

echo "📋 Configuração:"
echo "  Usuário: $CURRENT_USER"
echo "  Diretório: $CURRENT_DIR"
echo ""

# 1. Configurar systemd
echo "⚙️  Configurando systemd..."
if [ -f "setup_systemd.sh" ]; then
    chmod +x setup_systemd.sh
    ./setup_systemd.sh > /dev/null 2>&1
    echo "✅ Systemd configurado"
else
    echo "⚠️  setup_systemd.sh não encontrado, pulando..."
fi

# 2. Matar processos
echo ""
echo "💀 Matando processos antigos..."
pkill -9 python 2>/dev/null || true
pkill -9 gunicorn 2>/dev/null || true
fuser -k 5000/tcp 2>/dev/null || true
sleep 3
echo "✅ Processos mortos"

# 3. Iniciar Gunicorn
echo ""
echo "🚀 Iniciando Gunicorn..."
sudo systemctl daemon-reload
sudo systemctl enable grimbots 2>/dev/null || true
sudo systemctl start grimbots 2>/dev/null || true
sleep 3

if sudo systemctl is-active --quiet grimbots; then
    echo "✅ Gunicorn RODANDO"
else
    echo "❌ Gunicorn NÃO está rodando"
    echo "Ver erro: sudo journalctl -u grimbots -n 20"
    exit 1
fi

# 4. Iniciar RQ Workers (SEM AGUARDAR - background)
echo ""
echo "🚀 Iniciando RQ Workers (background)..."

# Tasks
for i in {1..5}; do 
    sudo systemctl enable rq-worker@tasks-$i 2>/dev/null || true
    sudo systemctl start rq-worker@tasks-$i 2>/dev/null &
done

# Gateway
for i in {1..3}; do 
    sudo systemctl enable rq-worker@gateway-$i 2>/dev/null || true
    sudo systemctl start rq-worker@gateway-$i 2>/dev/null &
done

# Webhook
for i in {1..3}; do 
    sudo systemctl enable rq-worker@webhook-$i 2>/dev/null || true
    sudo systemctl start rq-worker@webhook-$i 2>/dev/null &
done

echo "✅ Comandos de start enviados (iniciando em background)"

# 5. Aguardar workers iniciarem
echo ""
echo "⏳ Aguardando workers iniciarem (10 segundos)..."
sleep 10

# 6. Verificar workers
WORKER_COUNT=$(sudo systemctl status 'rq-worker@*' 2>/dev/null | grep -c "active (running)" || echo "0")
echo "✅ Workers ativos: $WORKER_COUNT/11"

# 7. Testar health check
echo ""
echo "🏥 Testando health check..."
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/health 2>/dev/null || echo "000")

if [ "$HEALTH" = "200" ]; then
    echo "✅ Health check: OK"
else
    echo "⚠️  Health check: HTTP $HEALTH"
fi

# 8. Resumo
echo ""
echo "=========================================="
echo "  ✅ DEPLOY CONCLUÍDO"
echo "=========================================="
echo ""
echo "Status:"
echo "  Gunicorn: $(sudo systemctl is-active grimbots)"
echo "  RQ Workers: $WORKER_COUNT/11"
echo "  Health: HTTP $HEALTH"
echo ""
echo "Comandos úteis:"
echo "  sudo systemctl status grimbots"
echo "  sudo systemctl status 'rq-worker@*'"
echo "  curl http://localhost:5000/health"
echo "  sudo journalctl -u grimbots -f"
echo ""

if sudo systemctl is-active --quiet grimbots; then
    echo "✅ Sistema operacional!"
    exit 0
else
    echo "⚠️  Verificar logs"
    exit 1
fi

