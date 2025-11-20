#!/bin/bash

echo "🔍 VERIFICAR VENDA EM TEMPO REAL"
echo "================================="
echo ""

# Verificar última venda
LAST_PAYMENT=$(psql -U postgres -d grimbots -t -c "
SELECT payment_id 
FROM payments 
WHERE status = 'paid'
ORDER BY paid_at DESC 
LIMIT 1;
" 2>/dev/null | xargs)

if [ -z "$LAST_PAYMENT" ]; then
    echo "❌ Nenhuma venda encontrada"
    exit 1
fi

echo "📊 Última venda: $LAST_PAYMENT"
echo ""

# Buscar detalhes da venda
psql -U postgres -d grimbots -c "
SELECT 
    payment_id,
    bot_id,
    status,
    gateway_type,
    CASE WHEN delivery_token IS NOT NULL THEN '✅' ELSE '❌' END as has_delivery_token,
    CASE WHEN meta_purchase_sent THEN '✅' ELSE '❌' END as purchase_sent,
    TO_CHAR(created_at, 'DD/MM/YYYY HH24:MI:SS') as created,
    TO_CHAR(paid_at, 'DD/MM/YYYY HH24:MI:SS') as paid,
    TO_CHAR(meta_purchase_sent_at, 'DD/MM/YYYY HH24:MI:SS') as purchase_sent_at
FROM payments 
WHERE payment_id = '$LAST_PAYMENT';
" 2>/dev/null

echo ""
echo "🔍 Buscando logs relacionados a esta venda..."
echo ""

# Buscar logs da última venda
tail -500 logs/gunicorn.log | grep -iE "$LAST_PAYMENT|META DELIVERY.*Delivery|Purchase.*$LAST_PAYMENT" | tail -20

echo ""
echo "📋 Para monitorar em tempo real, execute:"
echo "   bash monitorar_purchase_tempo_real.sh"
echo ""

