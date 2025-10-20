#!/bin/bash

################################################################################
# DEPLOY COMPLETO - Recuperação Automática de Leads
################################################################################
# 
# Este script executa TODAS as etapas necessárias:
# 1. Backup do banco
# 2. Migração de welcome_tracking
# 3. Restart dos bots
# 4. Validação
# 5. Testes básicos
#
# EXECUTAR:
# ---------
# chmod +x deploy_all.sh
# ./deploy_all.sh
#
################################################################################

set -e  # Para na primeira falha

echo ""
echo "================================================================================"
echo "🚀 DEPLOY COMPLETO - RECUPERAÇÃO AUTOMÁTICA DE LEADS"
echo "================================================================================"
echo ""

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Verificar se está no diretório correto
if [ ! -f "app.py" ]; then
    echo -e "${RED}❌ ERRO: Execute este script no diretório do projeto (onde está app.py)${NC}"
    exit 1
fi

# Verificar se venv existe
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ ERRO: venv não encontrado. Execute: python3 -m venv venv${NC}"
    exit 1
fi

# Ativar venv
echo -e "${YELLOW}📦 Ativando ambiente virtual...${NC}"
source venv/bin/activate

# 1. BACKUP DO BANCO
echo ""
echo "================================================================================"
echo "1️⃣ BACKUP DO BANCO DE DADOS"
echo "================================================================================"
echo ""

BACKUP_FILE="instance/saas_bot_manager.db.backup_$(date +%Y%m%d_%H%M%S)"

if [ -f "instance/saas_bot_manager.db" ]; then
    cp instance/saas_bot_manager.db "$BACKUP_FILE"
    echo -e "${GREEN}✅ Backup criado: $BACKUP_FILE${NC}"
else
    echo -e "${RED}❌ ERRO: Banco não encontrado em instance/saas_bot_manager.db${NC}"
    exit 1
fi

# 2. MIGRAÇÃO DE WELCOME TRACKING
echo ""
echo "================================================================================"
echo "2️⃣ EXECUTANDO MIGRAÇÃO (Welcome Tracking)"
echo "================================================================================"
echo ""

if [ -f "migrate_add_welcome_tracking.py" ]; then
    python migrate_add_welcome_tracking.py
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Migração executada com sucesso${NC}"
    else
        echo -e "${RED}❌ ERRO na migração! Restaurando backup...${NC}"
        cp "$BACKUP_FILE" instance/saas_bot_manager.db
        echo -e "${YELLOW}⚠️ Backup restaurado. Sistema voltou ao estado anterior.${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}⚠️ migrate_add_welcome_tracking.py não encontrado. Pulando...${NC}"
fi

# 3. VALIDAR SCHEMA
echo ""
echo "================================================================================"
echo "3️⃣ VALIDANDO SCHEMA DO BANCO"
echo "================================================================================"
echo ""

echo "Verificando colunas adicionadas..."
sqlite3 instance/saas_bot_manager.db "PRAGMA table_info(bot_users);" | grep -E "(archived|welcome_sent)"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Schema validado - Colunas presentes${NC}"
else
    echo -e "${RED}❌ ERRO: Colunas não encontradas no banco${NC}"
    exit 1
fi

# 4. RESTART DOS BOTS
echo ""
echo "================================================================================"
echo "4️⃣ REINICIANDO BOTS"
echo "================================================================================"
echo ""

# Verificar se PM2 está instalado
if command -v pm2 &> /dev/null; then
    echo "Parando bots..."
    pm2 stop all || true
    
    echo "Aguardando 2 segundos..."
    sleep 2
    
    echo "Iniciando bots..."
    pm2 start all
    
    echo -e "${GREEN}✅ Bots reiniciados${NC}"
else
    echo -e "${YELLOW}⚠️ PM2 não encontrado. Reinicie manualmente:${NC}"
    echo "   pm2 restart all"
fi

# 5. TESTES BÁSICOS
echo ""
echo "================================================================================"
echo "5️⃣ TESTES BÁSICOS"
echo "================================================================================"
echo ""

echo "Verificando estatísticas de welcome_sent..."
sqlite3 instance/saas_bot_manager.db <<EOF
SELECT 
  'Total de usuários' as metrica,
  COUNT(*) as valor
FROM bot_users
UNION ALL
SELECT 
  'Com welcome enviado' as metrica,
  COUNT(*) as valor
FROM bot_users WHERE welcome_sent = 1
UNION ALL
SELECT 
  'Sem welcome (para recuperar)' as metrica,
  COUNT(*) as valor
FROM bot_users WHERE welcome_sent = 0;
EOF

echo ""
echo -e "${GREEN}✅ Testes básicos concluídos${NC}"

# 6. INSTRUÇÕES FINAIS
echo ""
echo "================================================================================"
echo "✅ DEPLOY CONCLUÍDO COM SUCESSO!"
echo "================================================================================"
echo ""
echo "📋 PRÓXIMOS PASSOS:"
echo ""
echo "1. Testar bot manualmente:"
echo "   • Abra qualquer bot no Telegram"
echo "   • Envie /start"
echo "   • Deve receber mensagem normalmente"
echo ""
echo "2. Verificar logs:"
echo "   pm2 logs --lines 50"
echo ""
echo "3. Monitorar recuperações automáticas:"
echo "   pm2 logs | grep 'RECUPERAÇÃO AUTOMÁTICA'"
echo ""
echo "4. Se algo der errado, restaurar backup:"
echo "   cp $BACKUP_FILE instance/saas_bot_manager.db"
echo "   pm2 restart all"
echo ""
echo "================================================================================"
echo "🎉 Sistema está pronto para recuperar leads automaticamente!"
echo "================================================================================"
echo ""

# Desativar venv
deactivate

