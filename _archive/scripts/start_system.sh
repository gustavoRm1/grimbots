#!/bin/bash
# Script DEFINITIVO para iniciar sistema com systemd
# Mata tudo e inicia limpo

echo "=========================================="
echo "  INICIAR SISTEMA - GRIMBOTS QI 500"
echo "=========================================="
echo ""

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

success() { echo -e "${GREEN}✅ $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; }
warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }

# 1. Matar todos os processos
echo "💀 Matando processos antigos..."
pkill -9 python 2>/dev/null || true
pkill -9 python3 2>/dev/null || true
pkill -9 gunicorn 2>/dev/null || true
fuser -k 5000/tcp 2>/dev/null || true
sleep 3
success "Processos mortos"

# 2. Limpar porta 5000
echo ""
echo "🔓 Liberando porta 5000..."
fuser -k 5000/tcp 2>/dev/null || true
lsof -ti:5000 | xargs kill -9 2>/dev/null || true
sleep 2

# Verificar se porta está livre
if lsof -i:5000 > /dev/null 2>&1; then
    error "Porta 5000 ainda está em uso!"
    echo "Execute manualmente: sudo fuser -k 5000/tcp"
    exit 1
fi
success "Porta 5000 livre"

# 3. Configurar systemd (se ainda não configurado)
echo ""
echo "⚙️  Configurando systemd..."
if [ ! -f "/etc/systemd/system/grimbots.service" ] || [ ! -f "/etc/systemd/system/rq-worker@.service" ]; then
    warning "Services não encontrados, configurando automaticamente..."
    if [ -f "setup_systemd.sh" ]; then
        chmod +x setup_systemd.sh
        ./setup_systemd.sh
    else
        error "setup_systemd.sh não encontrado!"
        exit 1
    fi
else
    success "Services já configurados"
fi

# 4. Recarregar systemd
sudo systemctl daemon-reload

# 5. Habilitar services
echo ""
echo "📝 Habilitando services..."
sudo systemctl enable grimbots 2>/dev/null || true
for i in {1..5}; do sudo systemctl enable rq-worker@tasks-$i 2>/dev/null || true; done
for i in {1..3}; do sudo systemctl enable rq-worker@gateway-$i 2>/dev/null || true; done
for i in {1..3}; do sudo systemctl enable rq-worker@webhook-$i 2>/dev/null || true; done
success "Services habilitados"

# 6. Iniciar Gunicorn
echo ""
echo "🚀 Iniciando Gunicorn..."
sudo systemctl start grimbots

# Aguardar
sleep 5

# Verificar
if sudo systemctl is-active --quiet grimbots; then
    success "Gunicorn está rodando"
else
    error "Gunicorn NÃO está rodando!"
    echo ""
    echo "Ver logs:"
    sudo journalctl -u grimbots -n 30
    exit 1
fi

# 7. Iniciar RQ Workers
echo ""
echo "🚀 Iniciando RQ Workers..."

# Tasks (5 workers)
for i in {1..5}; do 
    sudo systemctl start rq-worker@tasks-$i
done

# Gateway (3 workers)
for i in {1..3}; do 
    sudo systemctl start rq-worker@gateway-$i
done

# Webhook (3 workers)
for i in {1..3}; do 
    sudo systemctl start rq-worker@webhook-$i
done

# Aguardar
sleep 5

# Contar workers
WORKER_COUNT=$(sudo systemctl status 'rq-worker@*' 2>/dev/null | grep -c "active (running)" || echo "0")
if [ "$WORKER_COUNT" -eq 11 ]; then
    success "11 RQ Workers rodando"
elif [ "$WORKER_COUNT" -gt 0 ]; then
    warning "$WORKER_COUNT RQ Workers rodando (esperado: 11)"
else
    error "Nenhum RQ Worker rodando!"
fi

# 8. Testar health check
echo ""
echo "🏥 Testando health check..."
sleep 2  # Aguardar aplicação inicializar

HEALTH_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/health 2>/dev/null || echo "000")

if [ "$HEALTH_CODE" = "200" ]; then
    success "Health check OK (200)"
    curl -s http://localhost:5000/health 2>/dev/null | python3 -m json.tool 2>/dev/null || curl -s http://localhost:5000/health
elif [ "$HEALTH_CODE" = "503" ]; then
    warning "Health check retornou 503 (unhealthy)"
    curl -s http://localhost:5000/health 2>/dev/null
else
    error "Health check não está acessível (HTTP $HEALTH_CODE)"
fi

# 9. Resumo
echo ""
echo "=========================================="
echo "  RESUMO"
echo "=========================================="
echo ""

# Status de serviços
echo "📊 Status de Serviços:"
if sudo systemctl is-active --quiet grimbots; then
    success "Gunicorn: RODANDO"
else
    error "Gunicorn: PARADO"
fi

echo "RQ Workers: $WORKER_COUNT/11"

# Porta
if lsof -i:5000 > /dev/null 2>&1; then
    PORT_PID=$(lsof -ti:5000)
    success "Porta 5000: EM USO (PID: $PORT_PID)"
else
    error "Porta 5000: LIVRE (Gunicorn não está escutando)"
fi

# Health
if [ "$HEALTH_CODE" = "200" ]; then
    success "Health Check: OK"
elif [ "$HEALTH_CODE" = "503" ]; then
    warning "Health Check: UNHEALTHY"
else
    error "Health Check: INACESSÍVEL"
fi

echo ""
echo "=========================================="
echo "  COMANDOS ÚTEIS"
echo "=========================================="
echo ""
echo "Ver logs:"
echo "  sudo journalctl -u grimbots -f"
echo "  sudo journalctl -u 'rq-worker@*' -f"
echo ""
echo "Status:"
echo "  sudo systemctl status grimbots"
echo "  sudo systemctl status 'rq-worker@*'"
echo ""
echo "Restart:"
echo "  sudo systemctl restart grimbots"
echo "  sudo systemctl restart 'rq-worker@*'"
echo ""
echo "Health check:"
echo "  curl http://localhost:5000/health"
echo ""

# Exit code baseado no sucesso
if sudo systemctl is-active --quiet grimbots && [ "$WORKER_COUNT" -ge 10 ]; then
    echo "✅ SISTEMA OPERACIONAL"
    exit 0
else
    echo "⚠️  SISTEMA COM PROBLEMAS - Verifique logs"
    exit 1
fi

