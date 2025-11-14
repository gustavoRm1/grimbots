#!/bin/bash
# Script de Deploy e Validação - Correções UmbrellaPay
# Data: 2025-11-14

set -e  # Parar em caso de erro

echo "=========================================="
echo "🚀 DEPLOY - CORREÇÕES UMBRELLAPAY"
echo "=========================================="
echo ""

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Função para imprimir mensagens
print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "ℹ️  $1"
}

# Verificar se está no diretório correto
if [ ! -f "app.py" ]; then
    print_error "Execute este script do diretório raiz do projeto (onde está app.py)"
    exit 1
fi

# Ativar venv
if [ -d "venv" ]; then
    print_info "Ativando venv..."
    source venv/bin/activate
else
    print_warning "venv não encontrado. Continuando sem ativar..."
fi

# PASSO 1: Backup
echo ""
echo "=========================================="
echo "📦 PASSO 1: BACKUP DO BANCO DE DADOS"
echo "=========================================="
echo ""

BACKUP_DIR="./backups"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Backup SQLite
if [ -f "instance/saas_bot_manager.db" ]; then
    print_info "Fazendo backup do SQLite..."
    cp instance/saas_bot_manager.db "$BACKUP_DIR/saas_bot_manager.db.backup_$TIMESTAMP"
    print_success "Backup SQLite criado: $BACKUP_DIR/saas_bot_manager.db.backup_$TIMESTAMP"
fi

# Backup PostgreSQL (se configurado)
if command -v pg_dump &> /dev/null; then
    print_info "PostgreSQL encontrado. Faça backup manualmente se necessário:"
    print_info "pg_dump -U usuario -d banco > backup_$TIMESTAMP.sql"
fi

# PASSO 2: Verificar Código
echo ""
echo "=========================================="
echo "🔍 PASSO 2: VERIFICAÇÃO DE CÓDIGO"
echo "=========================================="
echo ""

FILES_TO_CHECK=(
    "bot_manager.py"
    "tasks_async.py"
    "gateway_umbrellapag.py"
    "jobs/sync_umbrellapay.py"
)

for file in "${FILES_TO_CHECK[@]}"; do
    if [ -f "$file" ]; then
        print_info "Verificando $file..."
        if python3 -m py_compile "$file" 2>/dev/null; then
            print_success "$file - OK"
        else
            print_error "$file - ERRO DE SINTAXE"
            exit 1
        fi
    else
        print_error "$file não encontrado!"
        exit 1
    fi
done

# Verificar imports
print_info "Verificando imports..."
if python3 -c "from jobs.sync_umbrellapay import sync_umbrellapay_payments; print('✅ Import OK')" 2>/dev/null; then
    print_success "Imports OK"
else
    print_error "Erro nos imports!"
    exit 1
fi

# PASSO 3: Verificar Estrutura
echo ""
echo "=========================================="
echo "📁 PASSO 3: VERIFICAÇÃO DE ESTRUTURA"
echo "=========================================="
echo ""

if [ -f "jobs/__init__.py" ]; then
    print_success "jobs/__init__.py encontrado"
else
    print_error "jobs/__init__.py não encontrado!"
    exit 1
fi

if [ -f "jobs/sync_umbrellapay.py" ]; then
    print_success "jobs/sync_umbrellapay.py encontrado"
else
    print_error "jobs/sync_umbrellapay.py não encontrado!"
    exit 1
fi

# PASSO 4: Reiniciar Serviços
echo ""
echo "=========================================="
echo "🔄 PASSO 4: REINICIAR SERVIÇOS"
echo "=========================================="
echo ""

SERVICES=(
    "gunicorn"
    "rq-worker-tasks"
    "rq-worker-gateway"
    "rq-worker-webhook"
)

print_info "Parando serviços..."
for service in "${SERVICES[@]}"; do
    if systemctl is-active --quiet "$service" 2>/dev/null; then
        print_info "Parando $service..."
        sudo systemctl stop "$service" 2>/dev/null || print_warning "Não foi possível parar $service"
    else
        print_info "$service já está parado"
    fi
done

print_info "Aguardando 5 segundos..."
sleep 5

print_info "Verificando se processos foram finalizados..."
if pgrep -f "gunicorn|rq-worker" > /dev/null; then
    print_warning "Ainda há processos rodando. Matando processos..."
    pkill -f "gunicorn" || true
    pkill -f "rq-worker" || true
    sleep 2
fi

print_info "Iniciando serviços..."
for service in "${SERVICES[@]}"; do
    if systemctl list-unit-files | grep -q "$service.service"; then
        print_info "Iniciando $service..."
        sudo systemctl start "$service" 2>/dev/null || print_warning "Não foi possível iniciar $service"
        sleep 1
        
        if systemctl is-active --quiet "$service" 2>/dev/null; then
            print_success "$service iniciado"
        else
            print_error "$service não iniciou corretamente"
        fi
    else
        print_warning "$service não encontrado (pode não estar configurado)"
    fi
done

# PASSO 5: Validação
echo ""
echo "=========================================="
echo "✅ PASSO 5: VALIDAÇÃO"
echo "=========================================="
echo ""

print_info "Aguardando 3 segundos para serviços iniciarem..."
sleep 3

# Verificar se serviços estão rodando
print_info "Verificando status dos serviços..."
for service in "${SERVICES[@]}"; do
    if systemctl list-unit-files | grep -q "$service.service"; then
        if systemctl is-active --quiet "$service" 2>/dev/null; then
            print_success "$service está rodando"
        else
            print_error "$service não está rodando"
        fi
    fi
done

# Verificar logs
print_info "Verificando logs de inicialização..."
if [ -f "logs/error.log" ]; then
    ERROR_COUNT=$(tail -50 logs/error.log | grep -i "error\|critical\|exception" | wc -l)
    if [ "$ERROR_COUNT" -gt 0 ]; then
        print_warning "Encontrados $ERROR_COUNT erros nos últimos logs"
        print_info "Últimos erros:"
        tail -50 logs/error.log | grep -i "error\|critical\|exception" | tail -5
    else
        print_success "Nenhum erro crítico nos logs recentes"
    fi
fi

# Verificar se scheduler registrou o job
print_info "Verificando se scheduler registrou o job..."
if tail -100 logs/error.log 2>/dev/null | grep -q "sync_umbrellapay\|Job de sincronização UmbrellaPay"; then
    print_success "Job de sincronização registrado no scheduler"
else
    print_warning "Job de sincronização não encontrado nos logs (pode levar alguns segundos)"
fi

# Resumo Final
echo ""
echo "=========================================="
echo "📊 RESUMO FINAL"
echo "=========================================="
echo ""

print_success "Deploy concluído!"
echo ""
print_info "Próximos passos:"
echo "  1. Monitorar logs: tail -f logs/error.log | grep '\[VERIFY UMBRELLAPAY\]|\[WEBHOOK UMBRELLAPAY\]|\[SYNC UMBRELLAPAY\]|\[UMBRELLAPAY API\]'"
echo "  2. Aguardar 5 minutos para verificar se o job de sincronização executa"
echo "  3. Testar botão 'Verificar Pagamento' em um pagamento real"
echo "  4. Monitorar por 24 horas"
echo ""
print_info "Backup criado em: $BACKUP_DIR/saas_bot_manager.db.backup_$TIMESTAMP"
echo ""
print_success "✅ Deploy finalizado com sucesso!"

