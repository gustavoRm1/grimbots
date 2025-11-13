#!/bin/bash
# Script de Deploy Final - Meta Pixel Tracking Hotfix
# Execute na VPS: chmod +x scripts/apply_patch_final.sh && ./scripts/apply_patch_final.sh

set -e

# Cores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

success() { echo -e "${GREEN}✅ $1${NC}"; }
warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; }

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
echo "1. Fazendo backup do banco..."
mkdir -p "$BACKUP_DIR"
pg_dump -U "$DB_USER" -d "$DB_NAME" -t payments > "$BACKUP_DIR/payments_backup.sql"
success "Backup criado em: $BACKUP_DIR/payments_backup.sql"
echo ""

# 2. Criar migration
echo "2. Criando migration..."
mkdir -p migrations
cat > "$MIGRATION_FILE" << 'EOF'
-- Migration: Adicionar pageview_event_id ao Payment
-- Data: 2025-11-13
-- Objetivo: Permitir deduplicação mesmo se Redis expirar

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
echo "3. Aplicando migration..."
read -p "⚠️  Deseja aplicar a migration agora? (s/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Ss]$ ]]; then
    psql -U "$DB_USER" -d "$DB_NAME" -f "$MIGRATION_FILE"
    success "Migration aplicada com sucesso"
else
    warning "Migration não aplicada. Execute manualmente depois:"
    echo "  psql -U $DB_USER -d $DB_NAME -f $MIGRATION_FILE"
fi
echo ""

# 4. Verificar se código já está atualizado
echo "4. Verificando código..."
if grep -q "db.session.commit()" app.py && grep -q "paid e commitado" app.py; then
    success "Código já está atualizado (commit antes de enviar Meta Pixel)"
else
    warning "Código pode não estar atualizado. Verifique se o hotfix foi aplicado."
fi
echo ""

# 5. Reiniciar serviços
echo "5. Reiniciando serviços..."
read -p "⚠️  Deseja reiniciar os serviços agora? (s/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Ss]$ ]]; then
    if [ -f "./restart-app.sh" ]; then
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

# 6. Resumo
echo "=========================================="
echo "  DEPLOY CONCLUÍDO"
echo "=========================================="
echo ""
success "Backup criado em: $BACKUP_DIR"
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
echo "🔄 Rollback (se necessário):"
echo "  psql -U $DB_USER -d $DB_NAME -c 'ALTER TABLE payments DROP COLUMN IF EXISTS pageview_event_id;'"
echo "  psql -U $DB_USER -d $DB_NAME -c 'DROP INDEX IF EXISTS idx_payments_pageview_event_id;'"
echo "  psql -U $DB_USER -d $DB_NAME < $BACKUP_DIR/payments_backup.sql"
echo ""

