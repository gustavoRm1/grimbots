#!/bin/bash

echo "🔍 DIAGNÓSTICO - Por que meta_event_id está NULL?"
echo "=================================================="
echo ""

# 1. Verificar vendas com meta_purchase_sent=True mas meta_event_id=NULL
echo "1️⃣ VENDAS COM meta_purchase_sent=True MAS meta_event_id=NULL:"
echo "=============================================================="
psql -U postgres -d grimbots -c "
SELECT 
    p.id,
    p.payment_id,
    p.status,
    p.amount,
    p.created_at,
    p.meta_purchase_sent,
    p.meta_event_id,
    p.meta_purchase_sent_at,
    b.name as bot_name
FROM payments p
JOIN bots b ON p.bot_id = b.id
WHERE p.status = 'paid'
AND p.meta_purchase_sent = true
AND p.meta_event_id IS NULL
AND p.created_at >= NOW() - INTERVAL '24 hours'
ORDER BY p.created_at DESC
LIMIT 10;
" 2>/dev/null || echo "❌ Erro ao consultar banco de dados"
echo ""

# 2. Verificar logs de Purchase para essas vendas
echo "2️⃣ LOGS DE PURCHASE PARA ESSAS VENDAS:"
echo "======================================="
echo ""
echo "   Buscando logs de Purchase (últimas 1000 linhas)..."
tail -1000 logs/gunicorn.log | grep -iE "Purchase.*enfileirado|Purchase ENVIADO|Purchase.*Events Received|Purchase.*timeout|Purchase.*erro|meta_event_id atualizado" | tail -20
echo ""

# 3. Verificar erros no Celery
echo "3️⃣ ERROS NO CELERY:"
echo "==================="
echo ""
echo "   a) Timeouts ao aguardar resultado:"
tail -1000 logs/gunicorn.log | grep -i "timeout" | grep -i "purchase\|celery" | wc -l | xargs echo "      "
echo ""
echo "   b) Erros ao enviar Purchase:"
tail -1000 logs/gunicorn.log | grep -iE "Erro ao enviar Purchase|Purchase.*erro|Purchase.*error" | wc -l | xargs echo "      "
echo ""
echo "   c) Erros da API Meta:"
tail -1000 logs/gunicorn.log | grep -iE "Meta API error|Meta.*error|Meta.*400|Meta.*401|Meta.*403" | wc -l | xargs echo "      "
echo ""

# 4. Verificar se Purchase está sendo enfileirado
echo "4️⃣ PURCHASE ESTÁ SENDO ENFILEIRADO?"
echo "==================================="
echo ""
PURCHASE_QUEUED=$(tail -1000 logs/gunicorn.log | grep -i "Purchase enfileirado" | wc -l)
echo "   Purchase enfileirados: $PURCHASE_QUEUED"
echo ""

# 5. Verificar se Purchase está sendo enviado com sucesso
echo "5️⃣ PURCHASE ESTÁ SENDO ENVIADO COM SUCESSO?"
echo "==========================================="
echo ""
PURCHASE_SENT=$(tail -1000 logs/gunicorn.log | grep -iE "Purchase ENVIADO|Purchase.*Events Received.*1" | wc -l)
echo "   Purchase enviados com sucesso: $PURCHASE_SENT"
echo ""

# 6. Verificar se meta_event_id está sendo atualizado
echo "6️⃣ meta_event_id ESTÁ SENDO ATUALIZADO?"
echo "======================================="
echo ""
META_EVENT_ID_UPDATED=$(tail -1000 logs/gunicorn.log | grep -i "meta_event_id atualizado" | wc -l)
echo "   meta_event_id atualizados: $META_EVENT_ID_UPDATED"
echo ""

# 7. Verificar últimas linhas de logs de Purchase
echo "7️⃣ ÚLTIMAS LINHAS DE LOGS DE PURCHASE:"
echo "======================================="
echo ""
tail -1000 logs/gunicorn.log | grep -iE "Purchase|META PURCHASE" | tail -20
echo ""

# 8. Verificar status do Celery
echo "8️⃣ STATUS DO CELERY:"
echo "===================="
echo ""
if command -v celery &> /dev/null; then
    echo "   Verificando workers do Celery..."
    celery -A celery_app inspect active 2>/dev/null || echo "      ❌ Não foi possível verificar workers"
else
    echo "      ⚠️ Celery não está instalado ou não está no PATH"
fi
echo ""

echo "============================================================================"
echo "✅ Diagnóstico concluído!"
echo ""
echo "📋 ANÁLISE DOS RESULTADOS:"
echo ""
echo "   Se 'Purchase enfileirados' > 0 mas 'Purchase enviados' = 0:"
echo "      ❌ PROBLEMA: Purchase está sendo enfileirado mas não está sendo enviado"
echo "      ✅ SOLUÇÃO: Verificar logs do Celery, verificar erros da API Meta"
echo ""
echo "   Se 'meta_event_id atualizados' = 0:"
echo "      ❌ PROBLEMA: meta_event_id não está sendo salvo após envio bem-sucedido"
echo "      ✅ SOLUÇÃO: Verificar se Purchase está sendo enviado com sucesso (events_received > 0)"
echo ""
echo "   Se há timeouts:"
echo "      ❌ PROBLEMA: Timeout ao aguardar resultado do Celery (timeout=10s pode ser muito curto)"
echo "      ✅ SOLUÇÃO: Aumentar timeout ou verificar se Celery está processando tasks"
echo ""
echo "   Se há erros da API Meta:"
echo "      ❌ PROBLEMA: Meta API está rejeitando Purchase events"
echo "      ✅ SOLUÇÃO: Verificar token de acesso, pixel_id, payload enviado"
echo ""
echo "📝 PRÓXIMOS PASSOS:"
echo "   1. Execute: tail -f logs/gunicorn.log | grep -i Purchase para ver logs em tempo real"
echo "   2. Verifique logs do Celery: tail -f logs/celery.log (se existir)"
echo "   3. Verifique se workers do Celery estão ativos: celery -A celery_app inspect active"
echo "   4. Teste com uma nova venda após corrigir o problema"
echo ""

