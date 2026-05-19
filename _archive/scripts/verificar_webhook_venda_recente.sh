#!/bin/bash

echo "🔍 VERIFICANDO - Webhook de venda recente para identificar problema"
echo "==================================================================="
echo ""

# Verificar se estamos no diretório correto
if [ ! -f "app.py" ]; then
    echo "❌ Execute este script no diretório raiz do projeto (onde está app.py)"
    exit 1
fi

# 1. Verificar webhook mais recente (últimas 1h30)
echo "1️⃣ WEBHOOK MAIS RECENTE (últimas 1h30 - últimas 20 linhas):"
echo "==========================================================="
echo ""
tail -20000 logs/gunicorn.log | grep -iE "🔔 Webhook|webhook.*recebido|🔔.*webhook" | tail -20
if [ $? -ne 0 ] || [ -z "$(tail -20000 logs/gunicorn.log | grep -iE '🔔 Webhook|webhook.*recebido|🔔.*webhook' | tail -1)" ]; then
    echo "   ❌ Nenhum webhook real recebido (apenas reconciliação)"
fi
echo ""

# 2. Verificar se webhook foi enfileirado (últimas 1h30)
echo "2️⃣ WEBHOOK FOI ENFILEIRADO (status=queued)? (últimas 1h30)"
echo "==========================================================="
echo ""
tail -20000 logs/gunicorn.log | grep -iE "queued|enfileirar webhook" | tail -10
if [ $? -ne 0 ] || [ -z "$(tail -20000 logs/gunicorn.log | grep -iE 'queued|enfileirar webhook' | tail -1)" ]; then
    echo "   ❌ Nenhum webhook foi enfileirado"
fi
echo ""

# 3. Verificar se process_webhook_async está sendo executado (últimas 1h30)
echo "3️⃣ process_webhook_async ESTÁ SENDO EXECUTADO? (últimas 1h30)"
echo "=============================================================="
echo ""
tail -20000 logs/gunicorn.log | grep -iE "DIAGNÓSTICO.*process_webhook_async|process_webhook_async.*INICIADO|WEBHOOK.*payment|Enviando entregável|📦.*WEBHOOK" | tail -20
if [ $? -ne 0 ] || [ -z "$(tail -20000 logs/gunicorn.log | grep -iE 'DIAGNÓSTICO.*process_webhook_async|process_webhook_async.*INICIADO|WEBHOOK.*payment|Enviando entregável|📦.*WEBHOOK' | tail -1)" ]; then
    echo "   ❌ process_webhook_async NÃO está sendo executado"
fi
echo ""

# 4. Verificar erros no processamento do webhook (últimas 1h30)
echo "4️⃣ ERROS NO PROCESSAMENTO DO WEBHOOK (últimas 1h30):"
echo "======================================================"
echo ""
tail -20000 logs/gunicorn.log | grep -iE "Erro.*webhook|webhook.*erro|❌.*WEBHOOK|Exception.*webhook|❌.*DIAGNÓSTICO.*ERRO CRÍTICO" | tail -20
if [ $? -ne 0 ] || [ -z "$(tail -20000 logs/gunicorn.log | grep -iE 'Erro.*webhook|webhook.*erro|❌.*WEBHOOK|Exception.*webhook|❌.*DIAGNÓSTICO.*ERRO CRÍTICO' | tail -1)" ]; then
    echo "   ✅ Nenhum erro encontrado no processamento do webhook"
fi
echo ""

# 5. Verificar logs de payment atualizado para paid (últimas 1h30)
echo "5️⃣ PAYMENT ATUALIZADO PARA 'paid' (últimas 1h30 - últimas 10 linhas):"
echo "======================================================================"
echo ""
tail -20000 logs/gunicorn.log | grep -iE "payment.*paid|atualizado.*paid|Status.*paid|🔔.*payment.*paid|Webhook.*payment.*paid|💾.*WEBHOOK.*paid" | tail -10
if [ $? -ne 0 ] || [ -z "$(tail -20000 logs/gunicorn.log | grep -iE 'payment.*paid|atualizado.*paid|Status.*paid|🔔.*payment.*paid|Webhook.*payment.*paid|💾.*WEBHOOK.*paid' | tail -1)" ]; then
    echo "   ❌ Nenhum payment foi atualizado para paid (apenas reconciliação)"
fi
echo ""

# 6. Verificar TODOS os logs de diagnóstico (incluindo variantes - últimas 1h30)
echo "6️⃣ TODOS OS LOGS DE DIAGNÓSTICO (últimas 1h30):"
echo "================================================"
echo ""
tail -20000 logs/gunicorn.log | grep -iE "DIAGNÓSTICO|diagnostico|deve_enviar_entregavel|status.*paid|Status.*paid" | tail -30
if [ $? -ne 0 ] || [ -z "$(tail -20000 logs/gunicorn.log | grep -iE 'DIAGNÓSTICO|diagnostico|deve_enviar_entregavel|status.*paid|Status.*paid' | tail -1)" ]; then
    echo "   ❌ Nenhum log de diagnóstico encontrado"
fi
echo ""

# 7. Verificar última venda no banco (últimas 1h30)
echo "7️⃣ ÚLTIMA VENDA NO BANCO (últimas 1h30):"
echo "=========================================="
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
WHERE created_at >= NOW() - INTERVAL '90 minutes'
ORDER BY created_at DESC 
LIMIT 1;
" 2>/dev/null | xargs)
if [ -n "$LAST_PAYMENT" ]; then
    echo "$LAST_PAYMENT"
    echo ""
    echo "   Buscando logs para este payment..."
    PAYMENT_ID=$(echo "$LAST_PAYMENT" | awk '{print $1}')
    tail -10000 logs/gunicorn.log | grep -i "$PAYMENT_ID" | tail -30
else
    echo "   ❌ Nenhuma venda encontrada nos últimos 90 minutos"
fi
echo ""

# 8. Verificar se RQ worker está rodando
echo "8️⃣ RQ WORKER ESTÁ RODANDO?"
echo "==========================="
echo ""
RQ_WORKER=$(ps aux | grep -iE "rq.*worker|python.*rq.*worker" | grep -v grep | wc -l)
echo "   Processos RQ worker: $RQ_WORKER"
if [ "$RQ_WORKER" -eq 0 ]; then
    echo "   ❌ PROBLEMA: RQ worker NÃO está rodando!"
    echo "   ✅ SOLUÇÃO: Iniciar RQ worker para processar webhooks"
else
    echo "   ✅ RQ worker está rodando"
    ps aux | grep -iE "rq.*worker|python.*rq.*worker" | grep -v grep | head -3
fi
echo ""

# 9. Verificar vendas recentes (últimas 1h30)
echo "9️⃣ VENDAS RECENTES (últimas 1h30):"
echo "===================================="
echo ""
RECENT_PAYMENTS=$(psql -U postgres -d grimbots -t -c "
SELECT 
    payment_id,
    bot_id,
    status,
    gateway_type,
    CASE WHEN delivery_token IS NOT NULL THEN '✅' ELSE '❌' END as has_delivery_token,
    TO_CHAR(created_at, 'HH24:MI:SS') as created_time,
    TO_CHAR(paid_at, 'HH24:MI:SS') as paid_time
FROM payments 
WHERE created_at >= NOW() - INTERVAL '90 minutes'
ORDER BY created_at DESC 
LIMIT 10;
" 2>/dev/null)
if [ -n "$RECENT_PAYMENTS" ]; then
    echo "$RECENT_PAYMENTS"
else
    echo "   ❌ Nenhuma venda encontrada nos últimos 90 minutos"
fi
echo ""

# 10. Verificar logs de webhook recebido (últimas 1h30)
echo "🔟 WEBHOOKS RECEBIDOS (últimas 1h30):"
echo "======================================"
echo ""
tail -20000 logs/gunicorn.log | grep -iE "🔔 Webhook|webhook.*recebido|🔔.*webhook" | tail -10
if [ $? -ne 0 ] || [ -z "$(tail -20000 logs/gunicorn.log | grep -iE '🔔 Webhook|webhook.*recebido|🔔.*webhook' | tail -1)" ]; then
    echo "   ❌ Nenhum webhook real recebido (apenas reconciliação)"
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
echo "   5. Verifique se RQ worker está rodando (seção 8)"
echo "   6. Verifique vendas recentes (seção 9)"
echo "   7. Se RQ worker não está rodando, iniciar: rq worker --with-scheduler webhook"
echo ""

