#!/bin/bash
# Verificar payment específico

export PGPASSWORD=123sefudeu

echo "=========================================="
echo "  VERIFICAR PAYMENT ESPECÍFICO"
echo "=========================================="
echo ""

# Payment do log
PAYMENT_ID="BOT44_1763053810_030edbde"

echo "1. Dados do Payment:"
psql -U grimbots -d grimbots -c "SELECT payment_id, status, tracking_token, fbclid, pageview_event_id, meta_purchase_sent, meta_event_id, created_at, paid_at FROM payments WHERE payment_id='$PAYMENT_ID';"
echo ""

echo "2. Verificar Redis (se tiver tracking_token):"
TOKEN=$(psql -U grimbots -d grimbots -t -c "SELECT tracking_token FROM payments WHERE payment_id='$PAYMENT_ID';" | xargs)

if [ -n "$TOKEN" ] && [ "$TOKEN" != "" ]; then
    echo "Token encontrado: $TOKEN"
    redis-cli GET "tracking:$TOKEN" | python3 -m json.tool 2>/dev/null || redis-cli GET "tracking:$TOKEN"
else
    echo "⚠️  Payment não tem tracking_token"
fi
echo ""

echo "3. Verificar BotUser:"
CUSTOMER_ID=$(psql -U grimbots -d grimbots -t -c "SELECT customer_user_id FROM payments WHERE payment_id='$PAYMENT_ID';" | xargs)
BOT_ID=$(psql -U grimbots -d grimbots -t -c "SELECT bot_id FROM payments WHERE payment_id='$PAYMENT_ID';" | xargs)

if [ -n "$CUSTOMER_ID" ] && [ -n "$BOT_ID" ]; then
    psql -U grimbots -d grimbots -c "SELECT telegram_user_id, tracking_session_id, fbclid, utm_source, utm_campaign FROM bot_users WHERE bot_id=$BOT_ID AND telegram_user_id='$CUSTOMER_ID';"
else
    echo "⚠️  Customer ID ou Bot ID não encontrado"
fi
echo ""

echo "=========================================="
echo "  DIAGNÓSTICO CONCLUÍDO"
echo "=========================================="

