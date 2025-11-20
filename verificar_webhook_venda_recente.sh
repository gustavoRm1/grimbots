#!/bin/bash

echo "🔍 VERIFICANDO - Webhook de venda recente para identificar problema"
echo "==================================================================="
echo ""

# Verificar se estamos no diretório correto
if [ ! -f "app.py" ]; then
    echo "❌ Execute este script no diretório raiz do projeto (onde está app.py)"
    exit 1
fi

# 1. Verificar webhook mais recente
echo "1️⃣ WEBHOOK MAIS RECENTE (últimas 20 linhas):"
echo "============================================="
echo ""
tail -5000 logs/gunicorn.log | grep -iE "🔔 Webhook|webhook.*recebido" | tail -20
echo ""

# 2. Verificar se webhook foi enfileirado
echo "2️⃣ WEBHOOK FOI ENFILEIRADO (status=queued)?"
echo "============================================"
echo ""
tail -5000 logs/gunicorn.log | grep -iE "queued|enfileirar webhook" | tail -10
echo ""

# 3. Verificar se process_webhook_async está sendo executado
echo "3️⃣ process_webhook_async ESTÁ SENDO EXECUTADO?"
echo "================================================"
echo ""
tail -5000 logs/gunicorn.log | grep -iE "process_webhook_async|WEBHOOK.*payment|Enviando entregável|📦.*WEBHOOK" | tail -20
echo ""

# 4. Verificar erros no processamento do webhook
echo "4️⃣ ERROS NO PROCESSAMENTO DO WEBHOOK:"
echo "======================================"
echo ""
tail -5000 logs/gunicorn.log | grep -iE "Erro.*webhook|webhook.*erro|❌.*WEBHOOK|Exception.*webhook" | tail -20
echo ""

# 5. Verificar logs de payment atualizado para paid
echo "5️⃣ PAYMENT ATUALIZADO PARA 'paid' (últimas 10 linhas):"
echo "========================================================"
echo ""
tail -5000 logs/gunicorn.log | grep -iE "payment.*paid|atualizado.*paid|Status.*paid|🔔.*payment.*paid" | tail -10
echo ""

# 6. Verificar TODOS os logs de diagnóstico (incluindo variantes)
echo "6️⃣ TODOS OS LOGS DE DIAGNÓSTICO:"
echo "=================================="
echo ""
tail -5000 logs/gunicorn.log | grep -iE "DIAGNÓSTICO|diagnostico|deve_enviar_entregavel|status.*paid|Status.*paid" | tail -30
echo ""

# 7. Verificar última venda no banco
echo "7️⃣ ÚLTIMA VENDA NO BANCO:"
echo "=========================="
echo ""
LAST_PAYMENT=$(psql -U postgres -d grimbots -t -c "
SELECT 
    payment_id,
    bot_id,
    status,
    gateway_type,
    CASE WHEN delivery_token IS NOT NULL THEN '✅' ELSE '❌' END as has_delivery_token,
    created_at,
    paid_at
FROM payments 
WHERE created_at >= NOW() - INTERVAL '30 minutes'
ORDER BY created_at DESC 
LIMIT 1;
" 2>/dev/null | xargs)
if [ -n "$LAST_PAYMENT" ]; then
    echo "$LAST_PAYMENT"
    echo ""
    echo "   Buscando logs para este payment..."
    PAYMENT_ID=$(echo "$LAST_PAYMENT" | awk '{print $1}')
    tail -5000 logs/gunicorn.log | grep -i "$PAYMENT_ID" | tail -20
else
    echo "   ❌ Nenhuma venda encontrada nos últimos 30 minutos"
fi
echo ""

echo "============================================================================"
echo "✅ Verificação concluída!"
echo ""
echo "📋 ANÁLISE DOS RESULTADOS:"
echo ""
echo "   Se 'webhook mais recente' = 0:"
echo "      ❌ PROBLEMA: Webhook NÃO está sendo recebido"
echo ""
echo "   Se 'webhook foi enfileirado' = 0:"
echo "      ❌ PROBLEMA: Webhook está sendo recebido mas NÃO está sendo enfileirado"
echo ""
echo "   Se 'process_webhook_async está sendo executado' = 0:"
echo "      ❌ PROBLEMA: Webhook foi enfileirado mas NÃO está sendo processado"
echo ""
echo "   Se há erros no processamento:"
echo "      ❌ PROBLEMA: Webhook está sendo processado mas está falhando"
echo "      ✅ SOLUÇÃO: Verificar erros específicos (seção 4)"
echo ""
echo "📝 PRÓXIMOS PASSOS:"
echo "   1. Verifique se webhook foi recebido (seção 1)"
echo "   2. Verifique se webhook foi enfileirado (seção 2)"
echo "   3. Verifique se process_webhook_async está sendo executado (seção 3)"
echo "   4. Verifique erros no processamento (seção 4)"
echo ""

