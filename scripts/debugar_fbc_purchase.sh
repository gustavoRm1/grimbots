#!/bin/bash
# Script para debugar por que fbc não está sendo enviado no Purchase

echo "=========================================="
echo "  DEBUG - fbc AUSENTE NO PURCHASE"
echo "=========================================="
echo ""

echo "1. Último payload completo do Purchase:"
echo "----------------------------------------"
tail -n 1000 logs/celery.log | grep -A 50 "META PAYLOAD COMPLETO (Purchase)" | tail -55 | head -50
echo ""

echo "2. Logs de recuperação de fbc no Purchase:"
echo "----------------------------------------"
tail -n 1000 logs/celery.log | grep -E "fbc recuperado|fbc não encontrado|fbc salvo|Purchase.*fbc" | tail -20
echo ""

echo "3. Logs do process_start_async (salvamento de fbc):"
echo "----------------------------------------"
tail -n 1000 logs/error.log | grep -E "process_start_async.*fbc|fbc salvo no bot_user" | tail -10
echo ""

echo "4. Verificar último payment_id do Purchase sem fbc:"
echo "----------------------------------------"
LAST_PURCHASE_ID=$(tail -n 1000 logs/celery.log | grep "Purchase ENVIADO" | tail -1 | grep -oE "BOT[0-9]+_[0-9]+_[a-z0-9]+" | head -1)
if [ -n "$LAST_PURCHASE_ID" ]; then
    echo "Payment ID: $LAST_PURCHASE_ID"
    echo ""
    echo "Verificando tracking_token do payment:"
    psql -U grimbots -d grimbots -c "SELECT payment_id, tracking_token, LEFT(fbclid, 50) as fbclid_preview FROM payments WHERE payment_id = '$LAST_PURCHASE_ID';" 2>/dev/null
    echo ""
    echo "Verificando se tracking_token tem fbc no Redis:"
    TRACKING_TOKEN=$(psql -U grimbots -d grimbots -t -c "SELECT tracking_token FROM payments WHERE payment_id = '$LAST_PURCHASE_ID';" 2>/dev/null | tr -d ' ')
    if [ -n "$TRACKING_TOKEN" ]; then
        echo "Token: $TRACKING_TOKEN"
        redis-cli GET "tracking:$TRACKING_TOKEN" | grep -oE '"fbc":"[^"]*"' | head -1 || echo "❌ fbc não encontrado no Redis"
    fi
fi
echo ""

echo "5. Verificar bot_user do último payment:"
echo "----------------------------------------"
if [ -n "$LAST_PURCHASE_ID" ]; then
    CUSTOMER_ID=$(psql -U grimbots -d grimbots -t -c "SELECT customer_user_id FROM payments WHERE payment_id = '$LAST_PURCHASE_ID';" 2>/dev/null | tr -d ' ')
    if [ -n "$CUSTOMER_ID" ]; then
        psql -U grimbots -d grimbots -c "SELECT telegram_user_id, LEFT(fbp, 30) as fbp_preview, LEFT(fbc, 50) as fbc_preview FROM bot_users WHERE telegram_user_id = '$CUSTOMER_ID';" 2>/dev/null
    fi
fi

