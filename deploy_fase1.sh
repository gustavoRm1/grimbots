#!/bin/bash
# Script Automatizado - Deploy Fase 1
# GRIMBOTS QI 500 - Correções Críticas

set -e  # Parar em caso de erro

echo "=========================================="
echo "  DEPLOY FASE 1 - GRIMBOTS QI 500"
echo "=========================================="
echo ""

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Funções auxiliares
success() {
    echo -e "${GREEN}✅ $1${NC}"
}

error() {
    echo -e "${RED}❌ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Verificar se está no diretório correto
if [ ! -f "wsgi.py" ]; then
    error "Execute este script do diretório raiz do projeto (onde está wsgi.py)"
    exit 1
fi

# Verificar se venv existe
if [ ! -d "venv" ]; then
    error "Ambiente virtual não encontrado. Crie com: python3 -m venv venv"
    exit 1
fi

echo "📋 Verificando pré-requisitos..."

# Ativar venv
source venv/bin/activate

# Verificar Python
python --version
success "Python encontrado"

# Verificar Redis
if ! redis-cli ping > /dev/null 2>&1; then
    error "Redis não está rodando. Inicie com: systemctl start redis"
    exit 1
fi
success "Redis rodando"

echo ""
echo "=========================================="
echo "  ETAPA 1: REDIS CONNECTION POOL"
echo "=========================================="
echo ""

# Verificar se redis_manager.py existe
if [ ! -f "redis_manager.py" ]; then
    error "redis_manager.py não encontrado!"
    exit 1
fi

# Testar redis_manager
echo "Testando Redis Manager..."
if python redis_manager.py; then
    success "Redis Manager funcionando"
else
    error "Redis Manager com problemas"
    exit 1
fi

# Perguntar se deve fazer backup
echo ""
read -p "Fazer backup do código antes de modificar? (s/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Ss]$ ]]; then
    BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    cp -r *.py "$BACKUP_DIR/"
    success "Backup criado em: $BACKUP_DIR"
fi

echo ""
echo "Refatorando código para usar Redis Pool..."

# Backup específico antes de modificar
cp bot_manager.py bot_manager.py.backup
cp tasks_async.py tasks_async.py.backup
cp start_rq_worker.py start_rq_worker.py.backup

# Adicionar import no bot_manager.py se não existir
if ! grep -q "from redis_manager import get_redis_connection" bot_manager.py; then
    sed -i '1i from redis_manager import get_redis_connection' bot_manager.py
    success "Import adicionado ao bot_manager.py"
fi

warning "ATENÇÃO: Modificações manuais necessárias em:"
warning "  - bot_manager.py (9 ocorrências)"
warning "  - tasks_async.py (2 ocorrências)"
warning "  - start_rq_worker.py (1 ocorrência)"
warning ""
warning "Substitua redis.Redis(host=...) por get_redis_connection()"
echo ""

read -p "Pressione ENTER após fazer as modificações manuais..."

echo ""
echo "=========================================="
echo "  ETAPA 2: SYSTEMD SERVICES"
echo "=========================================="
echo ""

# Verificar se arquivos systemd existem
if [ ! -f "deploy/systemd/grimbots.service" ]; then
    error "deploy/systemd/grimbots.service não encontrado!"
    exit 1
fi

# Copiar para /etc/systemd/system/
echo "Copiando arquivos systemd..."
sudo cp deploy/systemd/grimbots.service /etc/systemd/system/
sudo cp deploy/systemd/rq-worker@.service /etc/systemd/system/
success "Arquivos copiados"

# Editar configurações
warning "Edite os arquivos systemd para ajustar:"
warning "  - User e Group"
warning "  - WorkingDirectory"
warning "  - DATABASE_URL"
warning "  - SECRET_KEY"
echo ""
read -p "Pressione ENTER após editar os arquivos..."

# Recarregar systemd
echo "Recarregando systemd..."
sudo systemctl daemon-reload
success "Systemd recarregado"

# Parar processos antigos
echo ""
echo "Parando processos antigos..."
pkill -f gunicorn || true
pkill -f start_rq_worker.py || true
sleep 3
success "Processos antigos parados"

# Habilitar serviços
echo ""
echo "Habilitando serviços..."
sudo systemctl enable grimbots
for i in {1..5}; do sudo systemctl enable rq-worker@tasks-$i; done
for i in {1..3}; do sudo systemctl enable rq-worker@gateway-$i; done
for i in {1..3}; do sudo systemctl enable rq-worker@webhook-$i; done
success "Serviços habilitados"

# Iniciar serviços
echo ""
echo "Iniciando serviços..."
sudo systemctl start grimbots
for i in {1..5}; do sudo systemctl start rq-worker@tasks-$i; done
for i in {1..3}; do sudo systemctl start rq-worker@gateway-$i; done
for i in {1..3}; do sudo systemctl start rq-worker@webhook-$i; done
success "Serviços iniciados"

# Aguardar inicialização
echo ""
echo "Aguardando inicialização (10 segundos)..."
sleep 10

# Verificar status
echo ""
echo "Verificando status..."
if sudo systemctl is-active --quiet grimbots; then
    success "Gunicorn está rodando"
else
    error "Gunicorn NÃO está rodando!"
    sudo systemctl status grimbots -l
    exit 1
fi

# Contar workers
WORKER_COUNT=$(sudo systemctl status 'rq-worker@*' 2>/dev/null | grep -c "active (running)" || echo "0")
if [ "$WORKER_COUNT" -eq 11 ]; then
    success "11 RQ Workers rodando"
else
    warning "$WORKER_COUNT RQ Workers rodando (esperado: 11)"
fi

echo ""
echo "=========================================="
echo "  ETAPA 3: HEALTH CHECK"
echo "=========================================="
echo ""

echo "Testando health check..."
HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/health)

if [ "$HEALTH_RESPONSE" = "200" ]; then
    success "Health check OK (200)"
    curl -s http://localhost:5000/health | python -m json.tool | head -20
else
    error "Health check FALHOU (HTTP $HEALTH_RESPONSE)"
    curl -s http://localhost:5000/health
fi

echo ""
echo "=========================================="
echo "  VALIDAÇÃO FINAL"
echo "=========================================="
echo ""

echo "Verificando componentes..."

# 1. Redis Pool
if python -c "from redis_manager import get_redis_connection; r = get_redis_connection(); r.ping()" 2>/dev/null; then
    success "Redis Pool OK"
else
    error "Redis Pool com problemas"
fi

# 2. Gunicorn
if sudo systemctl is-active --quiet grimbots; then
    success "Gunicorn OK"
else
    error "Gunicorn com problemas"
fi

# 3. RQ Workers
WORKER_COUNT=$(sudo systemctl status 'rq-worker@*' 2>/dev/null | grep -c "active (running)" || echo "0")
if [ "$WORKER_COUNT" -ge 10 ]; then
    success "RQ Workers OK ($WORKER_COUNT/11)"
else
    warning "RQ Workers insuficientes ($WORKER_COUNT/11)"
fi

# 4. Health Check
if [ "$HEALTH_RESPONSE" = "200" ]; then
    success "Health Check OK"
else
    error "Health Check com problemas"
fi

echo ""
echo "=========================================="
echo "  🎉 DEPLOY CONCLUÍDO"
echo "=========================================="
echo ""
echo "Status:"
if [ "$HEALTH_RESPONSE" = "200" ] && [ "$WORKER_COUNT" -ge 10 ]; then
    success "Sistema operacional e pronto para produção"
else
    warning "Sistema iniciado mas requer atenção"
fi
echo ""
echo "Próximos passos:"
echo "  1. Monitorar logs: sudo journalctl -u grimbots -f"
echo "  2. Testar carga: locust -f locustfile.py --headless -u 50 -r 10 -t 60s"
echo "  3. Validar métricas após 24h"
echo "  4. Iniciar Fase 2 (PostgreSQL)"
echo ""
echo "Comandos úteis:"
echo "  Status: sudo systemctl status grimbots 'rq-worker@*'"
echo "  Restart: sudo systemctl restart grimbots 'rq-worker@*'"
echo "  Logs: sudo journalctl -u grimbots -f"
echo "  Health: curl http://localhost:5000/health"
echo ""

