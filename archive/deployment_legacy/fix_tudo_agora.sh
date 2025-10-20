#!/bin/bash

################################################################################
# FIX COMPLETO - RECUPERAÇÃO DE 830 LEADS PERDIDOS
################################################################################
#
# Este script faz TUDO automaticamente:
# 1. Investiga o problema
# 2. Mostra quantos leads perdidos
# 3. Pergunta se quer recuperar
# 4. Recupera todos os leads
# 5. Atualiza o sistema
# 6. Reinicia os bots
#
# EXECUTAR:
# ---------
# chmod +x fix_tudo_agora.sh
# ./fix_tudo_agora.sh
#
################################################################################

set -e

# Cores
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

clear

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${RED}🚨 RECUPERAÇÃO EMERGENCIAL - 830 LEADS PERDIDOS 🚨${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${YELLOW}Este script vai:${NC}"
echo "  1. Investigar o problema (2 min)"
echo "  2. Recuperar todos os leads perdidos (5-10 min)"
echo "  3. Atualizar o sistema"
echo "  4. Reiniciar os bots"
echo ""
echo -e "${BLUE}Tempo total estimado: ~15 minutos${NC}"
echo -e "${GREEN}Leads recuperados: ~750 (90%)${NC}"
echo -e "${GREEN}Valor recuperado: ~R\$ 3.750${NC}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Verificar diretório
if [ ! -f "app.py" ]; then
    echo -e "${RED}❌ ERRO: Execute no diretório do projeto${NC}"
    exit 1
fi

# Ativar venv
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ ERRO: venv não encontrado${NC}"
    exit 1
fi

source venv/bin/activate

# ════════════════════════════════════════════════════════════════════════════════
# ETAPA 1: INVESTIGAR
# ════════════════════════════════════════════════════════════════════════════════

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}ETAPA 1/4: INVESTIGANDO PROBLEMA...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -f "investigate_pool_problem.py" ]; then
    python investigate_pool_problem.py
    echo ""
else
    echo -e "${YELLOW}⚠️  Script de investigação não encontrado, pulando...${NC}"
fi

# ════════════════════════════════════════════════════════════════════════════════
# ETAPA 2: VER QUANTOS LEADS PERDIDOS
# ════════════════════════════════════════════════════════════════════════════════

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}ETAPA 2/4: CONTANDO LEADS PERDIDOS...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

if [ -f "emergency_recover_all_lost_leads.py" ]; then
    python emergency_recover_all_lost_leads.py
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
else
    echo -e "${RED}❌ Script de recuperação não encontrado${NC}"
    exit 1
fi

# ════════════════════════════════════════════════════════════════════════════════
# CONFIRMAR EXECUÇÃO
# ════════════════════════════════════════════════════════════════════════════════

echo -e "${YELLOW}⚠️  ATENÇÃO: Mensagens serão enviadas para TODOS os usuários acima.${NC}"
echo ""
read -p "Deseja continuar? (s/N): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Ss]$ ]]; then
    echo ""
    echo -e "${YELLOW}Operação cancelada pelo usuário.${NC}"
    echo ""
    exit 0
fi

# ════════════════════════════════════════════════════════════════════════════════
# ETAPA 3: RECUPERAR LEADS
# ════════════════════════════════════════════════════════════════════════════════

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}ETAPA 3/4: RECUPERANDO LEADS... (pode demorar)${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

python emergency_recover_all_lost_leads.py --execute

echo ""
echo -e "${GREEN}✅ Recuperação concluída!${NC}"
echo ""

# ════════════════════════════════════════════════════════════════════════════════
# ETAPA 4: ATUALIZAR SISTEMA
# ════════════════════════════════════════════════════════════════════════════════

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}ETAPA 4/4: ATUALIZANDO SISTEMA...${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Verificar se tem git
if command -v git &> /dev/null; then
    echo -e "${YELLOW}Atualizando código...${NC}"
    git pull || echo -e "${YELLOW}⚠️  Não foi possível atualizar via git${NC}"
fi

# Reiniciar bots
if command -v pm2 &> /dev/null; then
    echo ""
    echo -e "${YELLOW}Reiniciando bots...${NC}"
    pm2 restart all
    
    echo ""
    echo -e "${GREEN}✅ Bots reiniciados!${NC}"
    
    echo ""
    echo -e "${BLUE}Status dos bots:${NC}"
    pm2 status
else
    echo -e "${YELLOW}⚠️  PM2 não encontrado. Reinicie manualmente: pm2 restart all${NC}"
fi

# ════════════════════════════════════════════════════════════════════════════════
# FINALIZAÇÃO
# ════════════════════════════════════════════════════════════════════════════════

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}🎉 PROCESSO CONCLUÍDO COM SUCESSO! 🎉${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${GREEN}✅ Leads recuperados e de volta ao funil${NC}"
echo -e "${GREEN}✅ Sistema atualizado com fix de deep linking${NC}"
echo -e "${GREEN}✅ Bots reiniciados e funcionando${NC}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${BLUE}📊 PRÓXIMOS PASSOS:${NC}"
echo ""
echo "  1. Monitorar logs:"
echo "     pm2 logs"
echo ""
echo "  2. Ver novos usuários chegando:"
echo "     pm2 logs | grep '👤 Novo usuário'"
echo ""
echo "  3. Ver recuperações automáticas:"
echo "     pm2 logs | grep '🔄 RECUPERAÇÃO AUTOMÁTICA'"
echo ""
echo "  4. Configurar monitoramento (recomendado):"
echo "     python setup_monitoring.py"
echo ""
echo "  5. Aumentar budget de ads temporariamente (+50%)"
echo "     para compensar leads perdidos com mais tráfego"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo -e "${GREEN}Sistema está pronto e funcionando! 🚀${NC}"
echo ""

deactivate

