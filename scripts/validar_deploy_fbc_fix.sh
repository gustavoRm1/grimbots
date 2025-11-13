#!/bin/bash
# Script de validação pós-deploy para correção do fbc
# Nível: Meta Partner Engineering

export PGPASSWORD=123sefudeu

echo "=========================================="
echo "  VALIDAÇÃO PÓS-DEPLOY - CORREÇÃO fbc"
echo "  Nível: Meta Partner Engineering"
echo "=========================================="
echo ""

# Cores para output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Contador de sucessos/falhas
SUCCESS=0
FAIL=0

echo "1️⃣ VALIDAR MIGRAÇÃO DO BANCO"
echo "----------------------------------------"
if psql -U grimbots -d grimbots -c "\d+ bot_users" | grep -qE "fbp|fbc"; then
    echo -e "${GREEN}✅ Colunas fbp e fbc existem no bot_users${NC}"
    psql -U grimbots -d grimbots -c "\d+ bot_users" | grep -E "fbp|fbc"
    SUCCESS=$((SUCCESS + 1))
else
    echo -e "${RED}❌ Colunas fbp e fbc NÃO foram criadas${NC}"
    FAIL=$((FAIL + 1))
fi
echo ""

echo "2️⃣ VALIDAR CÓDIGO (models.py)"
echo "----------------------------------------"
if grep -q "fbp = db.Column" models.py && grep -q "fbc = db.Column" models.py; then
    echo -e "${GREEN}✅ Campos fbp e fbc definidos no modelo BotUser${NC}"
    grep -A 1 "fbp = db.Column\|fbc = db.Column" models.py | head -4
    SUCCESS=$((SUCCESS + 1))
else
    echo -e "${RED}❌ Campos fbp e fbc NÃO encontrados no models.py${NC}"
    FAIL=$((FAIL + 1))
fi
echo ""

echo "3️⃣ VALIDAR SALVAMENTO NO process_start_async (tasks_async.py)"
echo "----------------------------------------"
if grep -q "bot_user.fbp = tracking_elite.get('fbp')" tasks_async.py && \
   grep -q "bot_user.fbc = tracking_elite.get('fbc')" tasks_async.py; then
    echo -e "${GREEN}✅ Código para salvar fbp/fbc no bot_user presente${NC}"
    grep -B 2 -A 2 "bot_user.fbp = tracking_elite.get('fbp')\|bot_user.fbc = tracking_elite.get('fbc')" tasks_async.py | head -8
    SUCCESS=$((SUCCESS + 1))
else
    echo -e "${RED}❌ Código para salvar fbp/fbc NÃO encontrado${NC}"
    FAIL=$((FAIL + 1))
fi
echo ""

echo "4️⃣ VALIDAR FALLBACK NO Purchase (app.py)"
echo "----------------------------------------"
if grep -q "fbc_value = bot_user.fbc" app.py && \
   grep -q "fbc recuperado do bot_user" app.py; then
    echo -e "${GREEN}✅ Fallback para recuperar fbc do bot_user presente${NC}"
    grep -B 2 -A 2 "fbc recuperado do bot_user" app.py | head -6
    SUCCESS=$((SUCCESS + 1))
else
    echo -e "${RED}❌ Fallback para recuperar fbc NÃO encontrado${NC}"
    FAIL=$((FAIL + 1))
fi
echo ""

echo "5️⃣ VALIDAR ÚLTIMO PAYLOAD ENVIADO (se houver)"
echo "----------------------------------------"
LAST_PURCHASE=$(tail -n 1000 logs/celery.log | grep -A 30 "META PAYLOAD COMPLETO (Purchase)" | tail -35)
if [ -n "$LAST_PURCHASE" ]; then
    if echo "$LAST_PURCHASE" | grep -q '"fbc"'; then
        echo -e "${GREEN}✅ Último Purchase enviado CONTÉM fbc no user_data${NC}"
        echo "$LAST_PURCHASE" | grep -A 5 '"user_data"'
        SUCCESS=$((SUCCESS + 1))
    else
        echo -e "${YELLOW}⚠️ Último Purchase enviado NÃO contém fbc (pode ser venda antiga)${NC}"
        echo "$LAST_PURCHASE" | grep -A 5 '"user_data"'
        echo ""
        echo "💡 Isso é normal se a venda foi feita ANTES do deploy. Faça uma nova venda para validar."
    fi
else
    echo -e "${YELLOW}⚠️ Nenhum Purchase encontrado nos logs recentes${NC}"
    echo "💡 Faça uma nova venda para validar o envio do fbc"
fi
echo ""

echo "6️⃣ VALIDAR BOT_USERS COM fbc SALVO (amostra)"
echo "----------------------------------------"
# Verificar se as colunas existem antes de consultar
COLUMNS_EXIST=$(psql -U grimbots -d grimbots -t -c "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = 'bot_users' AND column_name IN ('fbp', 'fbc');" | tr -d ' ')
if [ "$COLUMNS_EXIST" = "2" ]; then
    BOT_USERS_WITH_FBC=$(psql -U grimbots -d grimbots -t -c "SELECT COUNT(*) FROM bot_users WHERE fbc IS NOT NULL;" 2>/dev/null | tr -d ' ')
    if [ -n "$BOT_USERS_WITH_FBC" ] && [ "$BOT_USERS_WITH_FBC" -gt 0 ] 2>/dev/null; then
        echo -e "${GREEN}✅ Encontrados $BOT_USERS_WITH_FBC bot_users com fbc salvo${NC}"
        echo "Amostra (últimos 3):"
        psql -U grimbots -d grimbots -c "SELECT telegram_user_id, LEFT(fbp, 30) as fbp_preview, LEFT(fbc, 50) as fbc_preview FROM bot_users WHERE fbc IS NOT NULL ORDER BY id DESC LIMIT 3;"
        SUCCESS=$((SUCCESS + 1))
    else
        echo -e "${YELLOW}⚠️ Nenhum bot_user com fbc salvo ainda${NC}"
        echo "💡 Isso é normal se nenhum /start foi processado após o deploy"
    fi
else
    echo -e "${RED}❌ Colunas fbp/fbc NÃO existem no banco. Execute a migração primeiro:${NC}"
    echo "   psql -U grimbots -d grimbots -f scripts/migration_add_fbp_fbc_bot_users.sql"
    FAIL=$((FAIL + 1))
fi
echo ""

echo "7️⃣ VALIDAR ERROS 2804019 (creationTime)"
echo "----------------------------------------"
ERRORS_2804019=$(tail -n 1000 logs/celery.log | grep -c "2804019\|creationTime\|Invalid parameter")
if [ "$ERRORS_2804019" -eq 0 ]; then
    echo -e "${GREEN}✅ Nenhum erro 2804019 encontrado nos logs recentes${NC}"
    SUCCESS=$((SUCCESS + 1))
else
    echo -e "${RED}❌ Encontrados $ERRORS_2804019 erros relacionados a creationTime${NC}"
    tail -n 1000 logs/celery.log | grep -iE "2804019|creationTime|Invalid parameter" | tail -5
    FAIL=$((FAIL + 1))
fi
echo ""

echo "=========================================="
echo "  RESUMO DA VALIDAÇÃO"
echo "=========================================="
echo -e "${GREEN}✅ Sucessos: $SUCCESS${NC}"
if [ $FAIL -gt 0 ]; then
    echo -e "${RED}❌ Falhas: $FAIL${NC}"
else
    echo -e "${GREEN}❌ Falhas: $FAIL${NC}"
fi
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}🎉 VALIDAÇÃO COMPLETA: Patch aplicado com sucesso!${NC}"
    echo ""
    echo "📋 Próximos passos:"
    echo "1. Faça uma nova venda de teste"
    echo "2. Execute: tail -n 500 logs/celery.log | grep -A 30 'META PAYLOAD COMPLETO (Purchase)'"
    echo "3. Verifique se 'fbc' está presente no user_data"
    echo "4. Valide no Meta Events Manager se o matching melhorou"
else
    echo -e "${YELLOW}⚠️ Algumas validações falharam. Revise os erros acima.${NC}"
fi

