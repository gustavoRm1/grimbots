#!/bin/bash

PAYMENT_ID="BOT2_1763657851_e626447c"

echo "🔍 CAUSA RAIZ - Venda Não Trackeada: $PAYMENT_ID"
echo "================================================"
echo ""

# 1. Verificar dados da venda
echo "1️⃣ DADOS DA VENDA:"
echo "=================="
echo ""

psql -U postgres -d grimbots -c "
SELECT 
    id,
    payment_id,
    bot_id,
    status,
    customer_user_id,
    CASE WHEN delivery_token IS NOT NULL THEN '✅' ELSE '❌' END as has_delivery_token,
    CASE WHEN meta_purchase_sent THEN '✅' ELSE '❌' END as purchase_sent,
    TO_CHAR(paid_at, 'DD/MM/YYYY HH24:MI:SS') as paid,
    pageview_event_id,
    fbclid,
    utm_source,
    utm_campaign,
    campaign_code,
    tracking_token
FROM payments 
WHERE payment_id = '$PAYMENT_ID';
" 2>/dev/null

echo ""

# 2. Verificar bot_user (tracking_session_id)
echo "2️⃣ BOT_USER (TRACKING SESSION):"
echo "================================"
echo ""

BOT_ID=$(psql -U postgres -d grimbots -t -c "
SELECT bot_id FROM payments WHERE payment_id = '$PAYMENT_ID';
" 2>/dev/null | xargs)

CUSTOMER_ID=$(psql -U postgres -d grimbots -t -c "
SELECT REPLACE(customer_user_id, 'user_', '') FROM payments WHERE payment_id = '$PAYMENT_ID';
" 2>/dev/null | xargs)

if [ -n "$BOT_ID" ] && [ -n "$CUSTOMER_ID" ]; then
    psql -U postgres -d grimbots -c "
    SELECT 
        id,
        bot_id,
        telegram_user_id,
        CASE WHEN tracking_session_id IS NOT NULL THEN '✅' ELSE '❌' END as has_tracking_session,
        tracking_session_id,
        CASE WHEN fbp IS NOT NULL THEN '✅' ELSE '❌' END as has_fbp,
        CASE WHEN fbc IS NOT NULL THEN '✅' ELSE '❌' END as has_fbc,
        fbclid
    FROM bot_users 
    WHERE bot_id = $BOT_ID 
      AND telegram_user_id = '$CUSTOMER_ID';
    " 2>/dev/null
    
    echo ""
    echo "   🔍 Análise:"
    if [ -n "$(psql -U postgres -d grimbots -t -c "SELECT tracking_session_id FROM bot_users WHERE bot_id = $BOT_ID AND telegram_user_id = '$CUSTOMER_ID';" 2>/dev/null | xargs)" ]; then
        TRACKING_SESSION=$(psql -U postgres -d grimbots -t -c "SELECT tracking_session_id FROM bot_users WHERE bot_id = $BOT_ID AND telegram_user_id = '$CUSTOMER_ID';" 2>/dev/null | xargs)
        echo "   ✅ Cliente TEM tracking_session_id: $TRACKING_SESSION"
        
        # Verificar se começa com 'tracking_' (token gerado)
        if [[ "$TRACKING_SESSION" == tracking_* ]]; then
            echo "   ❌ PROBLEMA: tracking_session_id é um TOKEN GERADO (tracking_xxx)"
            echo "      Isso significa que cliente NÃO passou pelo redirect /go/<slug>"
            echo "      Token gerado não tem dados do redirect (fbclid, client_ip, etc)"
        else
            echo "   ✅ tracking_session_id parece ser um UUID do redirect"
            echo "   🔍 Verificando dados no Redis..."
            
            # Tentar recuperar do Redis (se possível)
            echo "   📋 Para verificar dados no Redis, execute:"
            echo "      redis-cli GET \"tracking:$TRACKING_SESSION\""
        fi
    else
        echo "   ❌ PROBLEMA: Cliente NÃO tem tracking_session_id"
        echo "      Isso significa que cliente NÃO passou pelo redirect /go/<slug>"
        echo "      SEM redirect, SEM fbclid, SEM atribuição à campanha"
    fi
fi

echo ""

# 3. Verificar logs do redirect
echo "3️⃣ LOGS DO REDIRECT (se cliente passou):"
echo "========================================="
echo ""

if [ -n "$CUSTOMER_ID" ]; then
    tail -10000 logs/gunicorn.log | grep -iE "$CUSTOMER_ID.*/go/|/go/.*$CUSTOMER_ID|fbclid.*$CUSTOMER_ID" | tail -10
fi

if [ -z "$(tail -10000 logs/gunicorn.log | grep -iE "$CUSTOMER_ID.*/go/|/go/.*$CUSTOMER_ID")" ]; then
    echo "   ❌ Nenhum log de redirect encontrado para este cliente"
    echo "   ❌ PROBLEMA CONFIRMADO: Cliente NÃO passou pelo redirect /go/<slug>"
fi

echo ""

# 4. Verificar se Purchase foi enviado
echo "4️⃣ PURCHASE ENVIADO:"
echo "===================="
echo ""

tail -5000 logs/gunicorn.log | grep -iE "$PAYMENT_ID.*Purchase|Purchase.*$PAYMENT_ID" | tail -10

echo ""

# 5. Diagnóstico final
echo "5️⃣ DIAGNÓSTICO FINAL:"
echo "====================="
echo ""

HAS_FBCLID=$(psql -U postgres -d grimbots -t -c "
SELECT CASE WHEN fbclid IS NOT NULL THEN 'SIM' ELSE 'NÃO' END 
FROM payments 
WHERE payment_id = '$PAYMENT_ID';
" 2>/dev/null | xargs)

HAS_TRACKING_SESSION=$(psql -U postgres -d grimbots -t -c "
SELECT CASE WHEN tracking_session_id IS NOT NULL THEN 'SIM' ELSE 'NÃO' END 
FROM bot_users 
WHERE bot_id = $BOT_ID AND telegram_user_id = '$CUSTOMER_ID';
" 2>/dev/null | xargs)

echo "   📊 Status:"
echo "      - fbclid na venda: $HAS_FBCLID"
echo "      - tracking_session_id no bot_user: $HAS_TRACKING_SESSION"
echo ""

if [ "$HAS_FBCLID" = "NÃO" ] && [ "$HAS_TRACKING_SESSION" = "NÃO" ]; then
    echo "   ❌ PROBLEMA CONFIRMADO:"
    echo "      - Cliente NÃO passou pelo redirect /go/<slug> antes de comprar"
    echo "      - SEM redirect, SEM fbclid, SEM atribuição à campanha Meta"
    echo ""
    echo "   ✅ SOLUÇÃO:"
    echo "      - Cliente DEVE passar pelo redirect /go/<slug> ANTES de comprar"
    echo "      - Redirect captura fbclid da URL do Facebook Ads"
    echo "      - Sem fbclid, Meta não consegue atribuir venda à campanha"
elif [ "$HAS_FBCLID" = "NÃO" ] && [ "$HAS_TRACKING_SESSION" = "SIM" ]; then
    echo "   ⚠️ PROBLEMA PARCIAL:"
    echo "      - Cliente TEM tracking_session_id (passou pelo redirect)"
    echo "      - MAS fbclid NÃO foi capturado/salvo na venda"
    echo ""
    echo "   🔍 POSSÍVEIS CAUSAS:"
    echo "      - Redirect não tinha fbclid na URL (tráfego direto/sem click_id)"
    echo "      - fbclid expirou ou foi perdido durante o fluxo"
    echo "      - tracking_data no Redis expirou"
elif [ "$HAS_FBCLID" = "SIM" ]; then
    echo "   ✅ Cliente TEM fbclid capturado"
    echo "   🔍 Verificar se Purchase foi enviado corretamente com fbclid"
fi

echo ""
echo "=========================================="
echo "✅ Diagnóstico concluído!"
echo ""

