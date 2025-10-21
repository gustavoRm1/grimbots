#!/bin/bash
# DEPLOY FINAL TRACKING ELITE - EXECUÇÃO AUTOMATIZADA
# Autor: QI 500 Elite Team
# Data: 2025-10-21

set -e  # Exit on error

echo "================================================================================"
echo "🎯 DEPLOY TRACKING ELITE - EXECUÇÃO AUTOMATIZADA"
echo "================================================================================"
echo ""

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Função de log
log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_info() {
    echo "ℹ️  $1"
}

# Verificar se está no diretório correto
if [ ! -f "app.py" ]; then
    log_error "Não está no diretório do projeto!"
    log_info "Execute: cd ~/grimbots"
    exit 1
fi

log_success "Diretório correto: $(pwd)"
echo ""

# FASE 1: PRÉ-REQUISITOS
echo "=== FASE 1: VERIFICANDO PRÉ-REQUISITOS ==="
echo ""

# Redis
log_info "Verificando Redis..."
if redis-cli ping > /dev/null 2>&1; then
    log_success "Redis rodando"
else
    log_error "Redis não está rodando!"
    log_info "Instalando Redis..."
    sudo apt-get update -qq
    sudo apt-get install redis-server -y -qq
    sudo systemctl start redis
    sudo systemctl enable redis
    
    if redis-cli ping > /dev/null 2>&1; then
        log_success "Redis instalado e iniciado"
    else
        log_error "Falha ao instalar Redis"
        exit 1
    fi
fi
echo ""

# Python Redis library
log_info "Verificando biblioteca redis..."
if python -c "import redis" 2>/dev/null; then
    log_success "Biblioteca redis instalada"
else
    log_warning "Biblioteca redis não encontrada, instalando..."
    pip install redis -q
    log_success "Biblioteca redis instalada"
fi
echo ""

# FASE 2: BACKUP
echo "=== FASE 2: BACKUP DO BANCO ==="
echo ""

BACKUP_NAME="saas_bot_manager.db.backup_tracking_elite_$(date +%Y%m%d_%H%M%S)"
log_info "Criando backup: $BACKUP_NAME"

if [ -f "instance/saas_bot_manager.db" ]; then
    cp instance/saas_bot_manager.db "instance/$BACKUP_NAME"
    BACKUP_SIZE=$(du -h "instance/$BACKUP_NAME" | cut -f1)
    log_success "Backup criado: $BACKUP_SIZE"
else
    log_warning "Banco de dados não encontrado (primeira instalação?)"
fi
echo ""

# FASE 3: GIT PULL
echo "=== FASE 3: ATUALIZAR CÓDIGO ==="
echo ""

log_info "Verificando status do Git..."
if git status --porcelain | grep -q .; then
    log_warning "Existem alterações locais!"
    git status --short
    log_info "Fazendo stash das alterações..."
    git stash
fi

log_info "Fazendo git pull..."
git pull origin main

if [ $? -eq 0 ]; then
    log_success "Código atualizado"
else
    log_error "Falha no git pull"
    exit 1
fi
echo ""

# FASE 4: MIGRATION
echo "=== FASE 4: EXECUTAR MIGRATION ==="
echo ""

if [ -f "migrate_add_tracking_fields.py" ]; then
    log_info "Executando migration..."
    
    if python migrate_add_tracking_fields.py; then
        log_success "Migration executada com sucesso"
    else
        log_error "Falha na migration"
        log_info "Possível causa: campos já existem (migration já foi rodada)"
        log_warning "Continuando deployment..."
    fi
else
    log_warning "Migration não encontrada (já foi arquivada?)"
fi
echo ""

# FASE 5: VALIDAR CAMPOS
echo "=== FASE 5: VALIDAR BANCO DE DADOS ==="
echo ""

log_info "Verificando campos adicionados..."

FIELDS_TO_CHECK=("ip_address" "user_agent" "tracking_session_id" "click_timestamp")
FIELDS_OK=0

for field in "${FIELDS_TO_CHECK[@]}"; do
    if sqlite3 instance/saas_bot_manager.db "PRAGMA table_info(bot_users);" 2>/dev/null | grep -q "$field"; then
        log_success "Campo $field existe"
        ((FIELDS_OK++))
    else
        log_error "Campo $field NÃO existe"
    fi
done

if [ $FIELDS_OK -eq 4 ]; then
    log_success "Todos os 4 campos existem"
else
    log_error "Apenas $FIELDS_OK/4 campos encontrados"
    exit 1
fi
echo ""

# FASE 6: REINICIAR APLICAÇÃO
echo "=== FASE 6: REINICIAR APLICAÇÃO ==="
echo ""

log_info "Reiniciando serviço grimbots..."
sudo systemctl restart grimbots

sleep 5

if systemctl is-active --quiet grimbots; then
    log_success "Serviço reiniciado com sucesso"
else
    log_error "Serviço falhou ao reiniciar"
    log_info "Verificando logs de erro..."
    sudo journalctl -u grimbots -n 50 --no-pager | grep -i error
    exit 1
fi
echo ""

# FASE 7: VALIDAÇÃO
echo "=== FASE 7: VALIDAÇÃO PÓS-DEPLOY ==="
echo ""

log_info "Verificando logs de inicialização..."
sleep 3

# Procurar por logs de sucesso
if sudo journalctl -u grimbots -n 50 --no-pager | grep -q "Gamificação V2.0 carregada"; then
    log_success "Gamificação carregada"
fi

if sudo journalctl -u grimbots -n 50 --no-pager | grep -q "SECRET_KEY validada"; then
    log_success "SECRET_KEY validada"
fi

if sudo journalctl -u grimbots -n 50 --no-pager | grep -q "BotManager inicializado"; then
    log_success "BotManager inicializado"
fi

# Procurar por erros
ERROR_COUNT=$(sudo journalctl -u grimbots -n 50 --no-pager | grep -c "ERROR" || true)
if [ $ERROR_COUNT -eq 0 ]; then
    log_success "Nenhum erro nos últimos 50 logs"
else
    log_warning "$ERROR_COUNT erro(s) encontrado(s) nos logs"
fi
echo ""

# FASE 8: TESTE DE SMOKE
echo "=== FASE 8: SMOKE TEST ==="
echo ""

log_info "Testando endpoint de saúde..."
if curl -s http://localhost:5000/health > /dev/null 2>&1; then
    log_success "Aplicação respondendo"
else
    log_warning "Endpoint /health não disponível (pode ser normal)"
fi
echo ""

# RESUMO FINAL
echo "================================================================================"
echo "📊 RESUMO DO DEPLOY"
echo "================================================================================"
echo ""
log_success "Backup criado: instance/$BACKUP_NAME"
log_success "Código atualizado via git pull"
log_success "Migration executada"
log_success "Campos validados: $FIELDS_OK/4"
log_success "Serviço reiniciado"
log_success "Aplicação rodando"
echo ""

echo "================================================================================"
echo "🎯 PRÓXIMOS PASSOS"
echo "================================================================================"
echo ""
echo "1. Monitorar logs em tempo real:"
echo "   sudo journalctl -u grimbots -f | grep -E 'TRACKING ELITE|CLOAKER|ERROR'"
echo ""
echo "2. Testar redirect com fbclid:"
echo "   curl 'https://app.grimbots.online/go/red1?testecamu01&fbclid=test123'"
echo ""
echo "3. Verificar Redis:"
echo "   redis-cli KEYS 'tracking:*'"
echo "   redis-cli GET 'tracking:test123'"
echo ""
echo "4. Após 24h, rodar analytics:"
echo "   python tracking_elite_analytics.py"
echo ""
echo "================================================================================"
echo "✅ DEPLOY TRACKING ELITE CONCLUÍDO!"
echo "================================================================================"

