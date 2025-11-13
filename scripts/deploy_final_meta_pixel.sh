#!/bin/bash
# Script de Deploy Final - Meta Pixel Tracking Hotfix
# Execute na VPS: chmod +x scripts/deploy_final_meta_pixel.sh && ./scripts/deploy_final_meta_pixel.sh

set -e

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

success() { echo -e "${GREEN}✅ $1${NC}"; }
warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; }
info() { echo -e "${BLUE}ℹ️  $1${NC}"; }

echo "=========================================="
echo "  DEPLOY FINAL - META PIXEL TRACKING"
echo "=========================================="
echo ""

# Configurações
export PGPASSWORD="${PGPASSWORD:-123sefudeu}"
DB_USER="${DB_USER:-grimbots}"
DB_NAME="${DB_NAME:-grimbots}"
BACKUP_DIR="./backups/$(date +%Y%m%d_%H%M%S)"
MIGRATION_FILE="./migrations/002_add_pageview_event_id.sql"

# 1. Backup do banco
echo "=========================================="
echo "1. BACKUP DO BANCO"
echo "=========================================="
mkdir -p "$BACKUP_DIR"
if pg_dump -U "$DB_USER" -d "$DB_NAME" -t payments > "$BACKUP_DIR/payments_backup.sql" 2>/dev/null; then
    success "Backup criado em: $BACKUP_DIR/payments_backup.sql"
    info "Tamanho do backup: $(du -h "$BACKUP_DIR/payments_backup.sql" | cut -f1)"
else
    error "Falha ao criar backup"
    exit 1
fi
echo ""

# 2. Criar migration
echo "=========================================="
echo "2. CRIAR MIGRATION"
echo "=========================================="
mkdir -p migrations
cat > "$MIGRATION_FILE" << 'EOF'
-- Migration: Adicionar pageview_event_id ao Payment
-- Data: 2025-11-13
-- Objetivo: Permitir deduplicação Meta Pixel mesmo se Redis expirar

BEGIN;

-- Adicionar coluna pageview_event_id
ALTER TABLE payments ADD COLUMN IF NOT EXISTS pageview_event_id VARCHAR(256);

-- Criar índice para busca rápida
CREATE INDEX IF NOT EXISTS idx_payments_pageview_event_id ON payments(pageview_event_id);

COMMIT;
EOF
success "Migration criada: $MIGRATION_FILE"
echo ""

# 3. Aplicar migration
echo "=========================================="
echo "3. APLICAR MIGRATION"
echo "=========================================="
read -p "⚠️  Deseja aplicar a migration agora? (s/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Ss]$ ]]; then
    if psql -U "$DB_USER" -d "$DB_NAME" -f "$MIGRATION_FILE" 2>/dev/null; then
        success "Migration aplicada com sucesso"
        
        # Verificar se coluna foi criada
        if psql -U "$DB_USER" -d "$DB_NAME" -c "\d+ payments" 2>/dev/null | grep -q "pageview_event_id"; then
            success "Coluna pageview_event_id verificada no banco"
        else
            warning "Coluna pode não ter sido criada - verificar manualmente"
        fi
    else
        error "Falha ao aplicar migration"
        exit 1
    fi
else
    warning "Migration não aplicada. Execute manualmente depois:"
    echo "  psql -U $DB_USER -d $DB_NAME -f $MIGRATION_FILE"
fi
echo ""

# 4. Atualizar código
echo "=========================================="
echo "4. ATUALIZAR CÓDIGO"
echo "=========================================="
if [ -d ".git" ]; then
    info "Fazendo pull do repositório..."
    if git pull origin main 2>&1 | grep -q "Already up to date\|Updating\|Fast-forward"; then
        success "Código atualizado"
    else
        warning "Git pull pode ter falhado - verificar manualmente"
    fi
else
    warning "Diretório não é um repositório git - código deve ser atualizado manualmente"
fi
echo ""

# 5. Verificar código
echo "=========================================="
echo "5. VERIFICAR CÓDIGO"
echo "=========================================="
if grep -q "pageview_event_id.*db.Column" models.py; then
    success "pageview_event_id encontrado no model Payment"
else
    error "pageview_event_id NÃO encontrado no model Payment"
    exit 1
fi

if grep -q "pageview_event_id=pageview_event_id" bot_manager.py; then
    success "pageview_event_id sendo salvo no Payment (bot_manager.py)"
else
    error "pageview_event_id NÃO está sendo salvo no Payment"
    exit 1
fi

if grep -q "payment.pageview_event_id" app.py; then
    success "Fallback para payment.pageview_event_id encontrado (app.py)"
else
    warning "Fallback para payment.pageview_event_id pode não estar implementado"
fi

if grep -q "paid e commitado" app.py; then
    success "Commit antes de enviar Meta Pixel confirmado"
else
    warning "Commit antes de enviar Meta Pixel pode não estar implementado"
fi
echo ""

# 6. Reiniciar serviços
echo "=========================================="
echo "6. REINICIAR SERVIÇOS"
echo "=========================================="
read -p "⚠️  Deseja reiniciar os serviços agora? (s/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Ss]$ ]]; then
    if [ -f "./restart-app.sh" ]; then
        info "Dando permissão de execução ao restart-app.sh..."
        chmod +x ./restart-app.sh
        info "Executando restart-app.sh..."
        ./restart-app.sh
        success "Serviços reiniciados"
    else
        warning "restart-app.sh não encontrado. Reinicie manualmente:"
        echo "  systemctl restart start_rq_worker.service"
        echo "  systemctl restart celery.service"
        echo "  systemctl restart grimbots.service"
    fi
else
    warning "Serviços não reiniciados. Reinicie manualmente depois."
fi
echo ""

# 7. Resumo final
echo "=========================================="
echo "  DEPLOY CONCLUÍDO"
echo "=========================================="
echo ""
success "Backup criado em: $BACKUP_DIR/payments_backup.sql"
if [[ $REPLY =~ ^[Ss]$ ]]; then
    success "Migration aplicada"
    success "Serviços reiniciados"
fi
echo ""
echo "📋 Próximos passos:"
echo "  1. Monitorar logs: tail -f logs/rq-webhook.log logs/celery.log"
echo "  2. Testar uma venda real"
echo "  3. Verificar no Meta Events Manager se aparece 'Navegador + Servidor'"
echo ""
echo "🔍 Validação rápida:"
echo "  psql -U $DB_USER -d $DB_NAME -c \"SELECT column_name FROM information_schema.columns WHERE table_name='payments' AND column_name='pageview_event_id';\""
echo ""
echo "🔄 Rollback (se necessário):"
echo "  psql -U $DB_USER -d $DB_NAME -c 'ALTER TABLE payments DROP COLUMN IF EXISTS pageview_event_id;'"
echo "  psql -U $DB_USER -d $DB_NAME -c 'DROP INDEX IF EXISTS idx_payments_pageview_event_id;'"
echo "  psql -U $DB_USER -d $DB_NAME < $BACKUP_DIR/payments_backup.sql"
echo "  git checkout HEAD~1 app.py bot_manager.py models.py"
echo "  ./restart-app.sh"
echo ""

