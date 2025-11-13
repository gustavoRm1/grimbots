#!/bin/bash
# Script completo para testar preservação do fbc

export PGPASSWORD=123sefudeu

echo "=========================================="
echo "  TESTE COMPLETO - PRESERVAÇÃO fbc"
echo "=========================================="
echo ""

echo "1. Fazer uma nova venda de teste:"
echo "----------------------------------------"
echo "💡 Acesse: https://app.grimbots.online/go/red1?fbclid=TEST123&grim=testecamu01"
echo "💡 Complete o fluxo até gerar PIX"
echo "💡 Aguarde pagamento ser confirmado"
echo ""
echo "Pressione ENTER após fazer a venda..."
read
echo ""

echo "2. Verificar logs do redirect (últimos 100 linhas):"
echo "----------------------------------------"
tail -n 100 logs/error.log | grep -E "Redirect.*fbc|fbc será salvo|fbc_cookie" | tail -10
echo ""

echo "3. Verificar último payment criado:"
echo "----------------------------------------"
LAST_PAYMENT=$(psql -U grimbots -d grimbots -t -c "SELECT payment_id FROM payments ORDER BY created_at DESC LIMIT 1;" 2>/dev/null | tr -d ' ')
if [ -n "$LAST_PAYMENT" ]; then
    echo "Último Payment ID: $LAST_PAYMENT"
    psql -U grimbots -d grimbots -c "SELECT payment_id, status, tracking_token, LEFT(fbclid, 50) as fbclid_preview FROM payments WHERE payment_id = '$LAST_PAYMENT';" 2>/dev/null
else
    echo "❌ Nenhum payment encontrado"
fi
echo ""

echo "4. Verificar tracking_token no Redis:"
echo "----------------------------------------"
if [ -n "$LAST_PAYMENT" ]; then
    TRACKING_TOKEN=$(psql -U grimbots -d grimbots -t -c "SELECT tracking_token FROM payments WHERE payment_id = '$LAST_PAYMENT';" 2>/dev/null | tr -d ' ')
    if [ -n "$TRACKING_TOKEN" ]; then
        echo "Token: $TRACKING_TOKEN"
        REDIS_DATA=$(redis-cli GET "tracking:$TRACKING_TOKEN" 2>/dev/null)
        if [ -n "$REDIS_DATA" ]; then
            echo "✅ Token encontrado no Redis"
            echo "$REDIS_DATA" | python3 -m json.tool 2>/dev/null | grep -E "fbc|fbp|fbclid|pageview_event_id" | head -10 || echo "$REDIS_DATA" | grep -oE '"fbc":"[^"]*"|"fbp":"[^"]*"|"fbclid":"[^"]*"|"pageview_event_id":"[^"]*"' | head -10
        else
            echo "❌ Token não encontrado no Redis"
        fi
    else
        echo "⚠️ Payment não tem tracking_token"
    fi
fi
echo ""

echo "5. Verificar logs do Purchase (últimas 500 linhas):"
echo "----------------------------------------"
tail -n 500 logs/celery.log | grep -E "Purchase.*tracking_data|fbc recuperado|fbc NÃO encontrado|🔍 Purchase" | tail -10
echo ""

echo "6. Verificar último payload do Purchase:"
echo "----------------------------------------"
LAST_PURCHASE=$(tail -n 1000 logs/celery.log | grep "META PAYLOAD COMPLETO (Purchase)" | tail -1)
if [ -n "$LAST_PURCHASE" ]; then
    echo "Último Purchase encontrado:"
    tail -n 1000 logs/celery.log | grep -A 50 "META PAYLOAD COMPLETO (Purchase)" | tail -55 | head -50
else
    echo "⚠️ Nenhum Purchase encontrado nos logs recentes"
    echo "💡 Aguarde o pagamento ser confirmado ou use o botão 'Verificar Pagamento' no bot"
fi
echo ""

echo "7. Verificar se fbc está no payload do Purchase:"
echo "----------------------------------------"
if [ -n "$LAST_PURCHASE" ]; then
    PURCHASE_PAYLOAD=$(tail -n 1000 logs/celery.log | grep -A 50 "META PAYLOAD COMPLETO (Purchase)" | tail -55)
    if echo "$PURCHASE_PAYLOAD" | grep -q '"fbc"'; then
        echo "✅ fbc está presente no payload do Purchase"
        echo "$PURCHASE_PAYLOAD" | grep -oE '"fbc":"[^"]*"' | head -1
    else
        echo "❌ fbc NÃO está presente no payload do Purchase"
    fi
fi
echo ""

echo "=========================================="
echo "  RESUMO DO TESTE"
echo "=========================================="
echo ""
if [ -n "$LAST_PAYMENT" ] && [ -n "$TRACKING_TOKEN" ]; then
    REDIS_DATA=$(redis-cli GET "tracking:$TRACKING_TOKEN" 2>/dev/null)
    if echo "$REDIS_DATA" | grep -q '"fbc"'; then
        echo "✅ fbc está no Redis"
    else
        echo "❌ fbc NÃO está no Redis"
    fi
    
    if [ -n "$LAST_PURCHASE" ]; then
        PURCHASE_PAYLOAD=$(tail -n 1000 logs/celery.log | grep -A 50 "META PAYLOAD COMPLETO (Purchase)" | tail -55)
        if echo "$PURCHASE_PAYLOAD" | grep -q '"fbc"'; then
            echo "✅ fbc está no payload do Purchase"
        else
            echo "❌ fbc NÃO está no payload do Purchase"
        fi
    fi
fi
echo ""

echo "📋 Próximos passos:"
echo "1. Se fbc não está no Redis, verifique os logs do redirect"
echo "2. Se fbc está no Redis mas não no Purchase, verifique os logs de recuperação"
echo "3. Se tudo está OK, valide no Meta Events Manager"

