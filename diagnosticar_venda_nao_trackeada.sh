#!/bin/bash

echo "🔍 DIAGNOSTICAR VENDA NÃO TRACKEADA"
echo "==================================="
echo ""

# 1. Buscar última venda (última hora)
echo "1️⃣ ÚLTIMAS VENDAS (última hora):"
echo "================================="
echo ""

psql -U postgres -d grimbots -c "
SELECT 
    id,
    payment_id,
    bot_id,
    status,
    TO_CHAR(created_at, 'DD/MM/YYYY HH24:MI:SS') as created,
    TO_CHAR(paid_at, 'DD/MM/YYYY HH24:MI:SS') as paid,
    CASE WHEN meta_purchase_sent THEN '✅' ELSE '❌' END as purchase_sent,
    TO_CHAR(meta_purchase_sent_at, 'DD/MM/YYYY HH24:MI:SS') as purchase_sent_at,
    pageview_event_id,
    fbclid,
    utm_campaign,
    campaign_code
FROM payments 
WHERE status = 'paid' 
  AND paid_at >= NOW() - INTERVAL '1 hour'
ORDER BY paid_at DESC 
LIMIT 10;
" 2>/dev/null

echo ""

# 2. Buscar logs da última venda
echo "2️⃣ LOGS DA ÚLTIMA VENDA:"
echo "=========================="
echo ""

# Buscar payment_id mais recente
LAST_PAYMENT_ID=$(psql -U postgres -d grimbots -t -c "
SELECT payment_id 
FROM payments 
WHERE status = 'paid'
  AND paid_at >= NOW() - INTERVAL '1 hour'
ORDER BY paid_at DESC 
LIMIT 1;
" 2>/dev/null | xargs)

if [ -z "$LAST_PAYMENT_ID" ]; then
    echo "   ❌ Nenhuma venda encontrada na última hora"
    echo ""
    echo "   📋 Buscando todas as vendas de hoje..."
    psql -U postgres -d grimbots -c "
    SELECT 
        payment_id,
        TO_CHAR(paid_at, 'DD/MM/YYYY HH24:MI:SS') as paid,
        CASE WHEN meta_purchase_sent THEN '✅' ELSE '❌' END as purchase_sent
    FROM payments 
    WHERE status = 'paid' 
      AND DATE(paid_at) = CURRENT_DATE
    ORDER BY paid_at DESC 
    LIMIT 10;
    " 2>/dev/null
else
    echo "   📊 Payment ID: $LAST_PAYMENT_ID"
    echo ""
    
    # Buscar logs relacionados
    echo "   🔍 Buscando logs relacionados..."
    echo ""
    tail -5000 logs/gunicorn.log | grep -iE "$LAST_PAYMENT_ID|payment.*$LAST_PAYMENT_ID" | tail -30
fi

echo ""

# 3. Verificar Purchase disparado
echo "3️⃣ PURCHASE DISPARADO:"
echo "======================"
echo ""

tail -5000 logs/gunicorn.log | grep -iE "Purchase.*disparado|Purchase.*enfileirado|meta_purchase_sent.*True" | tail -20

echo ""

# 4. Verificar fbclid/fbc capturado
echo "4️⃣ FBCLID/FBC CAPTURADO:"
echo "========================"
echo ""

tail -5000 logs/gunicorn.log | grep -iE "fbclid.*encontrado|fbc.*retornado|fbc.*gerado|VENDA SERÁ TRACKEADA" | tail -20

echo ""

# 5. Verificar delivery token
echo "5️⃣ DELIVERY TOKEN:"
echo "=================="
echo ""

psql -U postgres -d grimbots -c "
SELECT 
    payment_id,
    CASE WHEN delivery_token IS NOT NULL THEN '✅' ELSE '❌' END as has_delivery_token,
    CASE WHEN delivery_token IS NOT NULL THEN delivery_token ELSE 'N/A' END as delivery_token
FROM payments 
WHERE status = 'paid'
  AND paid_at >= NOW() - INTERVAL '1 hour'
ORDER BY paid_at DESC 
LIMIT 5;
" 2>/dev/null

echo ""

# 6. Verificar pool/pixel configurado
echo "6️⃣ POOL/PIXEL CONFIGURADO:"
echo "==========================="
echo ""

if [ -n "$LAST_PAYMENT_ID" ]; then
    BOT_ID=$(psql -U postgres -d grimbots -t -c "
    SELECT bot_id FROM payments WHERE payment_id = '$LAST_PAYMENT_ID';
    " 2>/dev/null | xargs)
    
    if [ -n "$BOT_ID" ]; then
        psql -U postgres -d grimbots -c "
        SELECT 
            pb.id as pool_bot_id,
            p.id as pool_id,
            p.name as pool_name,
            p.meta_pixel_id,
            CASE WHEN p.meta_tracking_enabled THEN '✅' ELSE '❌' END as tracking_enabled,
            CASE WHEN p.meta_events_purchase THEN '✅' ELSE '❌' END as purchase_enabled
        FROM pool_bots pb
        JOIN redirect_pools p ON pb.pool_id = p.id
        WHERE pb.bot_id = $BOT_ID
        LIMIT 1;
        " 2>/dev/null
    fi
fi

echo ""
echo "=========================================="
echo "✅ Diagnóstico concluído!"
echo ""

