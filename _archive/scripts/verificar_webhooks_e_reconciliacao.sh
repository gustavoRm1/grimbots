#!/bin/bash

echo "🔍 VERIFICANDO - Webhooks e Reconciliação para identificar por que send_payment_delivery não está sendo chamado"
echo "=============================================================================================================="
echo ""

# Verificar se estamos no diretório correto
if [ ! -f "app.py" ]; then
    echo "❌ Execute este script no diretório raiz do projeto (onde está app.py)"
    exit 1
fi

# 1. Verificar se webhooks estão sendo recebidos
echo "1️⃣ WEBHOOKS ESTÃO SENDO RECEBIDOS?"
echo "==================================="
echo ""
WEBHOOKS_RECEBIDOS=$(tail -5000 logs/gunicorn.log | grep -iE "webhook.*recebido|POST.*webhook|webhook.*POST" | wc -l)
echo "   Webhooks recebidos: $WEBHOOKS_RECEBIDOS"
echo ""

# 2. Verificar logs de webhook recentes
echo "2️⃣ LOGS DE WEBHOOK (últimas 30 linhas):"
echo "========================================"
echo ""
tail -5000 logs/gunicorn.log | grep -iE "webhook|POST.*/webhook" | tail -30
echo ""

# 3. Verificar se payments estão sendo encontrados no webhook
echo "3️⃣ PAYMENTS ESTÃO SENDO ENCONTRADOS NO WEBHOOK?"
echo "================================================"
echo ""
PAYMENT_ENCONTRADO=$(tail -5000 logs/gunicorn.log | grep -iE "Payment encontrado|payment.*encontrado" | wc -l)
PAYMENT_NAO_ENCONTRADO=$(tail -5000 logs/gunicorn.log | grep -iE "Payment.*não encontrado|Payment NÃO encontrado" | wc -l)
echo "   Payments encontrados: $PAYMENT_ENCONTRADO"
echo "   Payments NÃO encontrados: $PAYMENT_NAO_ENCONTRADO"
echo ""

# 4. Verificar logs de payment não encontrado
echo "4️⃣ LOGS DE PAYMENT NÃO ENCONTRADO:"
echo "===================================="
echo ""
tail -5000 logs/gunicorn.log | grep -iE "Payment.*não encontrado|Payment NÃO encontrado|CRÍTICO.*Payment NÃO" | tail -20
echo ""

# 5. Verificar se payments estão sendo atualizados para 'paid'
echo "5️⃣ PAYMENTS ESTÃO SENDO ATUALIZADOS PARA 'paid'?"
echo "================================================="
echo ""
PAYMENT_PAID=$(tail -5000 logs/gunicorn.log | grep -iE "payment.*atualizado.*paid|status.*paid|Payment.*paid|atualizado para paid" | wc -l)
echo "   Payments atualizados para paid: $PAYMENT_PAID"
echo ""

# 6. Verificar logs de payment atualizado para paid
echo "6️⃣ LOGS DE PAYMENT ATUALIZADO PARA 'paid':"
echo "============================================"
echo ""
tail -5000 logs/gunicorn.log | grep -iE "payment.*atualizado.*paid|atualizado para paid|Webhook.*payment.*paid" | tail -20
echo ""

# 7. Verificar reconciliação (Paradise e PushynPay)
echo "7️⃣ RECONCILIAÇÃO ESTÁ FUNCIONANDO?"
echo "===================================="
echo ""
RECONCILIACAO_PARADISE=$(tail -5000 logs/gunicorn.log | grep -iE "reconcile.*paradise|Paradise.*reconcili" | wc -l)
RECONCILIACAO_PUSHYNPAY=$(tail -5000 logs/gunicorn.log | grep -iE "reconcile.*pushyn|PushynPay.*reconcili" | wc -l)
echo "   Reconciliação Paradise: $RECONCILIACAO_PARADISE"
echo "   Reconciliação PushynPay: $RECONCILIACAO_PUSHYNPAY"
echo ""

# 8. Verificar logs de reconciliação
echo "8️⃣ LOGS DE RECONCILIAÇÃO:"
echo "=========================="
echo ""
tail -5000 logs/gunicorn.log | grep -iE "reconcili|Reconciliador" | tail -20
echo ""

# 9. Verificar se deve_enviar_entregavel está sendo calculado
echo "9️⃣ deve_enviar_entregavel ESTÁ SENDO CALCULADO?"
echo "================================================"
echo ""
DEVE_ENVIAR=$(tail -5000 logs/gunicorn.log | grep -iE "deve_enviar_entregavel|Enviando entregável|📦 Enviando entregável" | wc -l)
echo "   Logs de 'Enviando entregável': $DEVE_ENVIAR"
echo ""

# 10. Verificar vendas recentes com status 'paid' mas sem delivery enviado
echo "🔟 VENDAS RECENTES 'paid' SEM DELIVERY ENVIADO:"
echo "================================================"
echo ""
RECENT_PAID=$(psql -U postgres -d grimbots -t -c "
SELECT 
    payment_id,
    bot_id,
    status,
    CASE WHEN delivery_token IS NOT NULL THEN '✅' ELSE '❌' END as has_delivery_token,
    created_at,
    paid_at
FROM payments 
WHERE status = 'paid' 
AND created_at >= NOW() - INTERVAL '7 days'
ORDER BY created_at DESC 
LIMIT 10;
" 2>/dev/null)
if [ -n "$RECENT_PAID" ]; then
    echo "$RECENT_PAID"
else
    echo "   ❌ Erro ao consultar banco de dados ou nenhuma venda encontrada"
fi
echo ""

# 11. Verificar gateway_type das vendas recentes
echo "1️⃣1️⃣ GATEWAY_TYPE DAS VENDAS RECENTES:"
echo "========================================"
echo ""
GATEWAY_TYPES=$(psql -U postgres -d grimbots -t -c "
SELECT 
    gateway_type,
    COUNT(*) as total,
    COUNT(CASE WHEN status = 'paid' THEN 1 END) as paid
FROM payments 
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY gateway_type
ORDER BY total DESC;
" 2>/dev/null)
if [ -n "$GATEWAY_TYPES" ]; then
    echo "$GATEWAY_TYPES"
else
    echo "   ❌ Erro ao consultar banco de dados"
fi
echo ""

echo "============================================================================"
echo "✅ Verificação concluída!"
echo ""
echo "📋 ANÁLISE DOS RESULTADOS:"
echo ""
echo "   Se 'webhooks recebidos' = 0:"
echo "      ❌ PROBLEMA: Webhooks NÃO estão sendo recebidos"
echo "      ✅ SOLUÇÃO: Verificar configuração do webhook no gateway"
echo ""
echo "   Se 'payments NÃO encontrados' > 0:"
echo "      ❌ PROBLEMA: Payment não está sendo encontrado no webhook"
echo "      ✅ SOLUÇÃO: Verificar se gateway_transaction_id/hash está correto"
echo ""
echo "   Se 'payments atualizados para paid' = 0:"
echo "      ❌ PROBLEMA: Payments não estão sendo atualizados para paid"
echo "      ✅ SOLUÇÃO: Verificar lógica de atualização de status no webhook"
echo ""
echo "   Se 'deve_enviar_entregavel está sendo calculado' = 0:"
echo "      ❌ PROBLEMA: deve_enviar_entregavel está False ou não está sendo verificado"
echo "      ✅ SOLUÇÃO: Verificar se status == 'paid' está sendo verificado corretamente"
echo ""
echo "📝 PRÓXIMOS PASSOS:"
echo "   1. Verifique se webhooks estão sendo recebidos (seção 1)"
echo "   2. Verifique se payments estão sendo encontrados (seção 3)"
echo "   3. Verifique se payments estão sendo atualizados para paid (seção 5)"
echo "   4. Verifique gateway_type das vendas recentes (seção 11)"
echo "   5. Teste com uma nova venda após corrigir o problema"
echo ""

