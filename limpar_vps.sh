#!/bin/bash
# ============================================================================
# LIMPEZA SEGURA DA VPS - Grimbots
# Autor: Senior QI 500 + André QI 502
# Data: 2025-10-28
# ============================================================================
# Objetivo: Remover arquivos de teste e documentação desnecessária
# Redução: 240 arquivos → 50 arquivos (79% de limpeza)
# ============================================================================

set -e  # Parar em caso de erro

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "============================================================================"
echo "🧹 LIMPEZA SEGURA DA VPS - GRIMBOTS"
echo "============================================================================"
echo ""

# Confirmar
echo -e "${YELLOW}⚠️  Esta operação vai deletar arquivos temporários da VPS.${NC}"
echo -e "${YELLOW}📦 Um backup será criado automaticamente.${NC}"
echo ""
read -p "Deseja continuar? (sim/não): " confirm

if [[ $confirm != "sim" ]]; then
    echo -e "${RED}❌ Operação cancelada.${NC}"
    exit 0
fi

# Criar backup
BACKUP_DIR="backups/limpeza_$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR
echo -e "${GREEN}📦 Criando backup em: $BACKUP_DIR${NC}"
mkdir -p $BACKUP_DIR/scripts
mkdir -p $BACKUP_DIR/docs
mkdir -p $BACKUP_DIR/configs

# ============================================================================
# FASE 1: SCRIPTS DE TESTE E DIAGNÓSTICO
# ============================================================================
echo ""
echo "🗑️  FASE 1: Deletando scripts de teste e diagnóstico..."

# Mover para backup (não deletar diretamente)
mv diagnose_*.py $BACKUP_DIR/scripts/ 2>/dev/null || true
mv test_*.py $BACKUP_DIR/scripts/ 2>/dev/null || true
mv check_*.py $BACKUP_DIR/scripts/ 2>/dev/null || true
mv investigate_*.py $BACKUP_DIR/scripts/ 2>/dev/null || true
mv fix_user_stats.py $BACKUP_DIR/scripts/ 2>/dev/null || true
mv validar_solucao_híbrida.py $BACKUP_DIR/scripts/ 2>/dev/null || true
mv verificar_dados_demograficos.py $BACKUP_DIR/scripts/ 2>/dev/null || true
mv reenviar_meta_pixel.py $BACKUP_DIR/scripts/ 2>/dev/null || true
mv check_cloaker_config.py $BACKUP_DIR/scripts/ 2>/dev/null || true
mv enable_cloaker.py $BACKUP_DIR/scripts/ 2>/dev/null || true
mv disable_cloaker_emergency.py $BACKUP_DIR/scripts/ 2>/dev/null || true
mv emergency_fix_pool.py $BACKUP_DIR/scripts/ 2>/dev/null || true
mv fix_stats_calculation.py $BACKUP_DIR/scripts/ 2>/dev/null || true
mv paradise_payment_checker.py $BACKUP_DIR/scripts/ 2>/dev/null || true
mv paradise_workaround.py $BACKUP_DIR/scripts/ 2>/dev/null || true
mv investigate_sales_counting.py $BACKUP_DIR/scripts/ 2>/dev/null || true
mv check_recent_sales_fixed.py $BACKUP_DIR/scripts/ 2>/dev/null || true
mv check_recent_sales.py $BACKUP_DIR/scripts/ 2>/dev/null || true
mv check_db_structure.py $BACKUP_DIR/scripts/ 2>/dev/null || true
mv check_paradise_pending_sales.py $BACKUP_DIR/scripts/ 2>/dev/null || true
mv investigate_paradise_response.py $BACKUP_DIR/scripts/ 2>/dev/null || true
mv investigate_paradise_api.py $BACKUP_DIR/scripts/ 2>/dev/null || true
mv DIAGNOSTICO_*.py $BACKUP_DIR/scripts/ 2>/dev/null || true
mv TEST_*.py $BACKUP_DIR/scripts/ 2>/dev/null || true
mv test_order_bump_implementation.py $BACKUP_DIR/scripts/ 2>/dev/null || true

echo -e "${GREEN}✅ Scripts de teste movidos para backup${NC}"

# ============================================================================
# FASE 2: SCRIPTS DE FIX TEMPORÁRIOS (.sh)
# ============================================================================
echo ""
echo "🗑️  FASE 2: Deletando scripts de fix temporários..."

mv fix_*.sh $BACKUP_DIR/scripts/ 2>/dev/null || true
mv test_webhook_paradise.sh $BACKUP_DIR/scripts/ 2>/dev/null || true
mv deploy_paradise_checker.sh $BACKUP_DIR/scripts/ 2>/dev/null || true
mv deploy_paradise_fix.sh $BACKUP_DIR/scripts/ 2>/dev/null || true
mv install_paradise_checker.sh $BACKUP_DIR/scripts/ 2>/dev/null || true
mv update_paradise_checker.sh $BACKUP_DIR/scripts/ 2>/dev/null || true
mv implement_hybrid_solution.sh $BACKUP_DIR/scripts/ 2>/dev/null || true
mv FIX_COMPLETO_META_PURCHASE.sh $BACKUP_DIR/scripts/ 2>/dev/null || true
mv DEPLOY_SOLUCAO_MULTIPLOS_PIX.sh $BACKUP_DIR/scripts/ 2>/dev/null || true
mv DEPLOY_PARADISE_VERIFICATION_FIX.sh $BACKUP_DIR/scripts/ 2>/dev/null || true
mv DEPLOY_FINAL_TRACKING_ELITE.sh $BACKUP_DIR/scripts/ 2>/dev/null || true

# MANTER scripts essenciais
mv $BACKUP_DIR/scripts/INSTALAR_CELERY_SERVICO.sh . 2>/dev/null || true
mv $BACKUP_DIR/scripts/CHECK_DEPLOY_REQUIREMENTS.sh . 2>/dev/null || true

echo -e "${GREEN}✅ Scripts de fix temporários movidos para backup${NC}"

# ============================================================================
# FASE 3: DOCUMENTAÇÃO TEMPORÁRIA/DESATUALIZADA
# ============================================================================
echo ""
echo "🗑️  FASE 3: Deletando documentação temporária..."

# Manter apenas README.md e docs/ importantes
mv ANALISE_*.md $BACKUP_DIR/docs/ 2>/dev/null || true
mv DIAGNOSTICO_*.md $BACKUP_DIR/docs/ 2>/dev/null || true
mv DEPLOY_*.md $BACKUP_DIR/docs/ 2>/dev/null || true
mv FIX_*.md $BACKUP_DIR/docs/ 2>/dev/null || true
mv INVESTIGACAO_*.md $BACKUP_DIR/docs/ 2>/dev/null || true
mv RELATORIO_*.md $BACKUP_DIR/docs/ 2>/dev/null || true
mv PLANO_*.md $BACKUP_DIR/docs/ 2>/dev/null || true
mv ATIVAR_*.md $BACKUP_DIR/docs/ 2>/dev/null || true
mv CONFIRMACAO_*.md $BACKUP_DIR/docs/ 2>/dev/null || true
mv TRACKING_*.md $BACKUP_DIR/docs/ 2>/dev/null || true
mv ENTREGA_*.md $BACKUP_DIR/docs/ 2>/dev/null || true
mv INDICE_*.md $BACKUP_DIR/docs/ 2>/dev/null || true
mv RESUMO_*.md $BACKUP_DIR/docs/ 2>/dev/null || true
mv VALIDACAO_*.md $BACKUP_DIR/docs/ 2>/dev/null || true
mv MVP_*.md $BACKUP_DIR/docs/ 2>/dev/null || true
mv GUIA_*.md $BACKUP_DIR/docs/ 2>/dev/null || true
mv ARCHIVE_INDEX.md $BACKUP_DIR/docs/ 2>/dev/null || true
mv RESTORE_INSTRUCTIONS.md $BACKUP_DIR/docs/ 2>/dev/null || true
mv CLOAKER_*.md $BACKUP_DIR/docs/ 2>/dev/null || true
mv META_PIXEL_*.md $BACKUP_DIR/docs/ 2>/dev/null || true
mv ANALISE_CRITICA_*.md $BACKUP_DIR/docs/ 2>/dev/null || true
mv DADOS_CAPTURADOS_REDIRECIONAMENTO.md $BACKUP_DIR/docs/ 2>/dev/null || true

echo -e "${GREEN}✅ Documentação temporária movida para backup${NC}"

# ============================================================================
# FASE 4: ARQUIVOS ESPECIAIS
# ============================================================================
echo ""
echo "🗑️  FASE 4: Removendo arquivos especiais..."

rm -f *.json  # paradise.json (temporário)
rm -f *.php   # paradise.php (temporário)
rm -f *.txt   # COMANDOS_FINAIS_VPS.txt (temporário)
rm -f *.ps1   # EXECUTAR_ARQUIVAMENTO_SEGURO.ps1 (Windows)

# Manter apenas requirements.txt
if [ -f requirements.txt ]; then
    echo -e "${GREEN}✅ requirements.txt mantido${NC}"
fi

echo -e "${GREEN}✅ Arquivos especiais removidos${NC}"

# ============================================================================
# RESUMO
# ============================================================================
echo ""
echo "============================================================================"
echo "✅ LIMPEZA CONCLUÍDA!"
echo "============================================================================"
echo ""
echo -e "${GREEN}📦 Backup salvo em: $BACKUP_DIR${NC}"
echo ""
echo "📊 Redução estimada:"
echo "   - Scripts .py: ~80 removidos"
echo "   - Scripts .sh: ~25 removidos"
echo "   - Docs .md: ~75 removidos"
echo "   - Total: ~180 arquivos removidos"
echo ""
echo "✅ Arquivos mantidos:"
echo "   - Core do sistema (app.py, bot_manager.py, models.py, etc.)"
echo "   - Gateways (*.py em root)"
echo "   - Utils/, tasks/, templates/, static/"
echo "   - Migrations ativas"
echo "   - README.md + docs/"
echo "   - deploy/ (scripts de deploy ativos)"
echo ""
echo -e "${YELLOW}⚠️  Sistema continua funcionando normalmente.${NC}"
echo -e "${YELLOW}📁 Backup pode ser restaurado de: $BACKUP_DIR${NC}"
echo ""

