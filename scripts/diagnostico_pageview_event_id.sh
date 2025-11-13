#!/bin/bash
# Diagnóstico completo do pageview_event_id

export PGPASSWORD=123sefudeu

echo "=========================================="
echo "  DIAGNÓSTICO - pageview_event_id"
echo "=========================================="
echo ""

# Payment específico
PAYMENT_ID="BOT44_1763053810_030edbde"
TOKEN="tracking_446bf80b326e52088176bc86"

echo "1. Dados do Payment:"
psql -U grimbots -d grimbots -c "SELECT payment_id, tracking_token, pageview_event_id, fbclid, customer_user_id, bot_id FROM payments WHERE payment_id='$PAYMENT_ID';"
echo ""

echo "2. Verificar Redis (token do payment):"
REDIS_DATA=$(redis-cli GET "tracking:$TOKEN" 2>/dev/null)
if [ -n "$REDIS_DATA" ]; then
    echo "$REDIS_DATA" | python3 -m json.tool 2>/dev/null || echo "$REDIS_DATA"
    echo ""
    echo "✅ pageview_event_id no Redis:"
    echo "$REDIS_DATA" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('pageview_event_id', 'N/A'))" 2>/dev/null || echo "N/A"
else
    echo "⚠️  Token não encontrado no Redis (pode ter expirado)"
fi
echo ""

echo "3. Verificar BotUser:"
CUSTOMER_ID=$(psql -U grimbots -d grimbots -t -c "SELECT customer_user_id FROM payments WHERE payment_id='$PAYMENT_ID';" | xargs)
BOT_ID=$(psql -U grimbots -d grimbots -t -c "SELECT bot_id FROM payments WHERE payment_id='$PAYMENT_ID';" | xargs)

if [ -n "$CUSTOMER_ID" ] && [ -n "$BOT_ID" ]; then
    echo "Customer ID: $CUSTOMER_ID | Bot ID: $BOT_ID"
    psql -U grimbots -d grimbots -c "SELECT telegram_user_id, tracking_session_id, fbclid FROM bot_users WHERE bot_id=$BOT_ID AND telegram_user_id='$CUSTOMER_ID';"
    echo ""
    
    # Verificar Redis com tracking_session_id do bot_user
    TRACKING_SESSION=$(psql -U grimbots -d grimbots -t -c "SELECT tracking_session_id FROM bot_users WHERE bot_id=$BOT_ID AND telegram_user_id='$CUSTOMER_ID';" | xargs)
    if [ -n "$TRACKING_SESSION" ] && [ "$TRACKING_SESSION" != "" ]; then
        echo "4. Verificar Redis (tracking_session_id do bot_user):"
        echo "Token: $TRACKING_SESSION"
        redis-cli GET "tracking:$TRACKING_SESSION" | python3 -m json.tool 2>/dev/null || redis-cli GET "tracking:$TRACKING_SESSION"
        echo ""
    fi
fi
echo ""

echo "5. Verificar últimos PageViews (últimas 2 horas):"
psql -U grimbots -d grimbots -c "SELECT payment_id, tracking_token, pageview_event_id, created_at FROM payments WHERE created_at >= NOW() - INTERVAL '2 hours' ORDER BY created_at DESC LIMIT 5;"
echo ""

echo "=========================================="
echo "  DIAGNÓSTICO CONCLUÍDO"
echo "=========================================="

