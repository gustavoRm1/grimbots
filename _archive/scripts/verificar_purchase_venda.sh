#!/bin/bash

# Recebe payment_id como argumento
PAYMENT_ID=$1

if [ -z "$PAYMENT_ID" ]; then
    echo "❌ Uso: bash verificar_purchase_venda.sh <payment_id>"
    echo ""
    echo "Exemplo: bash verificar_purchase_venda.sh BOT2_1763652057_bf9d998e"
    exit 1
fi

echo "🔍 VERIFICANDO PURCHASE PARA VENDA: $PAYMENT_ID"
echo "================================================"
echo ""

# 1. Verificar dados da venda
echo "1️⃣ DADOS DA VENDA:"
echo "==================="
psql -U postgres -d grimbots -c "
SELECT 
    id,
    payment_id,
    bot_id,
    status,
    gateway_type,
    CASE WHEN delivery_token IS NOT NULL THEN '✅' ELSE '❌' END as has_delivery_token,
    CASE WHEN meta_purchase_sent THEN '✅ SIM' ELSE '❌ NÃO' END as purchase_sent,
    TO_CHAR(created_at, 'DD/MM/YYYY HH24:MI:SS') as created,
    TO_CHAR(paid_at, 'DD/MM/YYYY HH24:MI:SS') as paid,
    TO_CHAR(meta_purchase_sent_at, 'DD/MM/YYYY HH24:MI:SS') as purchase_sent_at,
    pageview_event_id
FROM payments 
WHERE payment_id = '$PAYMENT_ID';
" 2>/dev/null

echo ""

# 2. Verificar pool do bot
echo "2️⃣ POOL DO BOT:"
echo "================"
BOT_ID=$(psql -U postgres -d grimbots -t -c "
SELECT bot_id FROM payments WHERE payment_id = '$PAYMENT_ID';
" 2>/dev/null | xargs)

if [ -n "$BOT_ID" ]; then
    psql -U postgres -d grimbots -c "
    SELECT 
        pb.id as pool_bot_id,
        p.id as pool_id,
        p.name as pool_name,
        p.meta_pixel_id,
        CASE WHEN p.meta_tracking_enabled THEN '✅' ELSE '❌' END as tracking_enabled
    FROM pool_bots pb
    JOIN redirect_pools p ON pb.pool_id = p.id
    WHERE pb.bot_id = $BOT_ID
    LIMIT 1;
    " 2>/dev/null
fi

echo ""

# 3. Verificar logs de Purchase
echo "3️⃣ LOGS DE PURCHASE:"
echo "===================="
echo ""
echo "   Buscando logs relacionados a esta venda..."
echo ""

# Buscar logs específicos
tail -2000 logs/gunicorn.log | grep -iE "$PAYMENT_ID|META DELIVERY.*Delivery.*$PAYMENT_ID|Purchase.*$PAYMENT_ID|event_id.*$PAYMENT_ID" | tail -30

echo ""
echo "📋 Para monitorar em tempo real, execute:"
echo "   bash monitorar_purchase_tempo_real.sh"
echo ""
