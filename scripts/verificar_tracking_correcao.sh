#!/bin/bash
# Verificar se as correções de tracking estão funcionando

export PGPASSWORD=123sefudeu

echo "=========================================="
echo "  VERIFICAÇÃO - CORREÇÕES DE TRACKING"
echo "=========================================="
echo ""

echo "1. Verificar logs recentes do bot_manager (últimas 50 linhas):"
echo "----------------------------------------"
tail -n 50 logs/error.log | grep -E "Tracking token|pageview_event_id|tracking_session_id" | tail -20
echo ""

echo "2. Verificar último payment criado:"
echo "----------------------------------------"
psql -U grimbots -d grimbots -c "SELECT payment_id, tracking_token, pageview_event_id, created_at FROM payments ORDER BY created_at DESC LIMIT 1;"
echo ""

echo "3. Verificar se o tracking_token do último payment tem pageview_event_id no Redis:"
echo "----------------------------------------"
LAST_TOKEN=$(psql -U grimbots -d grimbots -t -c "SELECT tracking_token FROM payments ORDER BY created_at DESC LIMIT 1;" | xargs)
if [ -n "$LAST_TOKEN" ] && [ "$LAST_TOKEN" != "" ]; then
    echo "Token: $LAST_TOKEN"
    REDIS_DATA=$(redis-cli GET "tracking:$LAST_TOKEN" 2>/dev/null)
    if [ -n "$REDIS_DATA" ]; then
        echo "$REDIS_DATA" | python3 -c "import sys, json; data=json.load(sys.stdin); print('pageview_event_id:', data.get('pageview_event_id', 'N/A'))" 2>/dev/null || echo "N/A"
    else
        echo "⚠️  Token não encontrado no Redis"
    fi
else
    echo "⚠️  Nenhum payment encontrado"
fi
echo ""

echo "4. Verificar bot_user do último payment:"
echo "----------------------------------------"
LAST_CUSTOMER=$(psql -U grimbots -d grimbots -t -c "SELECT customer_user_id FROM payments ORDER BY created_at DESC LIMIT 1;" | xargs)
LAST_BOT=$(psql -U grimbots -d grimbots -t -c "SELECT bot_id FROM payments ORDER BY created_at DESC LIMIT 1;" | xargs)
if [ -n "$LAST_CUSTOMER" ] && [ -n "$LAST_BOT" ]; then
    psql -U grimbots -d grimbots -c "SELECT telegram_user_id, tracking_session_id FROM bot_users WHERE bot_id=$LAST_BOT AND telegram_user_id='$LAST_CUSTOMER';"
else
    echo "⚠️  Customer ou Bot não encontrado"
fi
echo ""

echo "=========================================="
echo "  VERIFICAÇÃO CONCLUÍDA"
echo "=========================================="
echo ""
echo "📋 Próximos passos:"
echo "1. Faça uma nova venda de teste"
echo "2. Execute este script novamente para verificar se pageview_event_id está sendo salvo"
echo "3. Verifique os logs em tempo real: tail -f logs/error.log | grep -E 'Tracking|pageview'"

