#!/bin/bash

echo "🔍 VERIFICANDO - Venda específica e webhooks"
echo "============================================="
echo ""

# Verificar se estamos no diretório correto
if [ ! -f "app.py" ]; then
    echo "❌ Execute este script no diretório raiz do projeto (onde está app.py)"
    exit 1
fi

# 1. Verificar últimas 10 vendas (últimas 24h)
echo "1️⃣ ÚLTIMAS 10 VENDAS (últimas 24h):"
echo "===================================="
echo ""
RECENT_PAYMENTS=$(psql -U postgres -d grimbots -t -c "
SELECT 
    payment_id,
    bot_id,
    status,
    gateway_type,
    CASE WHEN delivery_token IS NOT NULL THEN '✅' ELSE '❌' END as has_delivery_token,
    TO_CHAR(created_at, 'DD/MM/YYYY HH24:MI:SS') as created,
    TO_CHAR(paid_at, 'DD/MM/YYYY HH24:MI:SS') as paid
FROM payments 
WHERE created_at >= NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC 
LIMIT 10;
" 2>/dev/null)
if [ -n "$RECENT_PAYMENTS" ]; then
    echo "$RECENT_PAYMENTS"
else
    echo "   ❌ Nenhuma venda encontrada nas últimas 24 horas"
fi
echo ""

# 2. Verificar última venda específica
echo "2️⃣ ÚLTIMA VENDA ESPECÍFICA:"
echo "============================"
echo ""
LAST_PAYMENT_ID=$(psql -U postgres -d grimbots -t -c "
SELECT payment_id 
FROM payments 
ORDER BY created_at DESC 
LIMIT 1;
" 2>/dev/null | xargs)
if [ -n "$LAST_PAYMENT_ID" ]; then
    echo "   payment_id: $LAST_PAYMENT_ID"
    echo ""
    
    # Buscar detalhes da última venda
    PAYMENT_DETAILS=$(psql -U postgres -d grimbots -t -c "
    SELECT 
        payment_id,
        bot_id,
        status,
        gateway_type,
        gateway_transaction_id,
        gateway_transaction_hash,
        CASE WHEN delivery_token IS NOT NULL THEN '✅' ELSE '❌' END as has_delivery_token,
        TO_CHAR(created_at, 'DD/MM/YYYY HH24:MI:SS') as created,
        TO_CHAR(paid_at, 'DD/MM/YYYY HH24:MI:SS') as paid
    FROM payments 
    WHERE payment_id = '$LAST_PAYMENT_ID';
    " 2>/dev/null)
    echo "$PAYMENT_DETAILS"
    echo ""
    
    # Buscar logs relacionados a esta venda
    echo "   Buscando logs relacionados a esta venda..."
    tail -30000 logs/gunicorn.log | grep -i "$LAST_PAYMENT_ID" | tail -30
else
    echo "   ❌ Nenhuma venda encontrada no banco"
fi
echo ""

# 3. Verificar webhooks reais vs reconciliação
echo "3️⃣ WEBHOOKS REAIS VS RECONCILIAÇÃO (últimas 1h30):"
echo "==================================================="
echo ""
echo "   Webhooks reais (POST /webhook/payment/*):"
WEBHOOKS_REAIS=$(tail -30000 logs/gunicorn.log | grep -iE "POST.*/webhook/payment|🔔 Webhook.*recebido" | wc -l)
echo "      Total: $WEBHOOKS_REAIS"
echo ""
echo "   Reconciliação (polling - 📥 [UmbrellaPag] Resposta):"
RECONCILIACAO=$(tail -30000 logs/gunicorn.log | grep -iE "📥.*UmbrellaPag.*Resposta|📥.*Paradise.*Resposta|📥.*AtomPay.*Resposta" | wc -l)
echo "      Total: $RECONCILIACAO"
echo ""

# 4. Verificar gateway_type das vendas recentes
echo "4️⃣ GATEWAY_TYPE DAS VENDAS RECENTES (últimas 24h):"
echo "==================================================="
echo ""
GATEWAY_TYPES=$(psql -U postgres -d grimbots -t -c "
SELECT 
    gateway_type,
    COUNT(*) as total,
    COUNT(CASE WHEN status = 'paid' THEN 1 END) as paid,
    COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
    COUNT(CASE WHEN delivery_token IS NOT NULL THEN 1 END) as has_delivery_token
FROM payments 
WHERE created_at >= NOW() - INTERVAL '24 hours'
GROUP BY gateway_type
ORDER BY total DESC;
" 2>/dev/null)
if [ -n "$GATEWAY_TYPES" ]; then
    echo "$GATEWAY_TYPES"
else
    echo "   ❌ Nenhuma venda encontrada nas últimas 24 horas"
fi
echo ""

# 5. Verificar se há webhooks pendentes na fila
echo "5️⃣ WEBHOOKS PENDENTES NA FILA RQ:"
echo "=================================="
echo ""
# Verificar se há jobs na fila webhook
RQ_JOBS=$(redis-cli LLEN rq:queue:webhook 2>/dev/null || echo "0")
echo "   Jobs pendentes na fila webhook: $RQ_JOBS"
if [ "$RQ_JOBS" != "0" ] && [ "$RQ_JOBS" != "" ]; then
    echo "   ⚠️ Há webhooks pendentes na fila!"
    echo "   ✅ SOLUÇÃO: Verificar se RQ worker está processando a fila"
else
    echo "   ✅ Nenhum webhook pendente na fila"
fi
echo ""

# 6. Verificar logs de webhook recebido (últimas 1h30)
echo "6️⃣ LOGS DE WEBHOOK RECEBIDO (últimas 1h30):"
echo "============================================"
echo ""
tail -30000 logs/gunicorn.log | grep -iE "🔔 Webhook|webhook.*recebido|POST.*/webhook/payment" | tail -10
if [ $? -ne 0 ] || [ -z "$(tail -30000 logs/gunicorn.log | grep -iE '🔔 Webhook|webhook.*recebido|POST.*/webhook/payment' | tail -1)" ]; then
    echo "   ❌ Nenhum webhook real recebido (apenas reconciliação)"
fi
echo ""

echo "============================================================================"
echo "✅ Verificação concluída!"
echo ""
echo "📋 ANÁLISE DOS RESULTADOS:"
echo ""
echo "   Se 'últimas 10 vendas' = 0:"
echo "      ❌ PROBLEMA: Nenhuma venda foi criada recentemente"
echo ""
echo "   Se 'webhooks reais' = 0:"
echo "      ❌ PROBLEMA: Gateways NÃO estão enviando webhooks"
echo "      ✅ SOLUÇÃO: Verificar configuração do webhook no gateway"
echo ""
echo "   Se 'webhooks pendentes na fila' > 0:"
echo "      ❌ PROBLEMA: Webhooks estão sendo enfileirados mas não processados"
echo "      ✅ SOLUÇÃO: Verificar se RQ worker está processando a fila"
echo ""
echo "📝 PRÓXIMOS PASSOS:"
echo "   1. Verifique se há vendas recentes (seção 1)"
echo "   2. Verifique gateway_type das vendas (seção 4)"
echo "   3. Verifique se gateways estão enviando webhooks (seção 3)"
echo "   4. Verifique se há webhooks pendentes na fila (seção 5)"
echo ""

