#!/bin/bash

echo "🔍 VERIFICANDO - Logs de Delivery para identificar problema"
echo "============================================================"
echo ""

# Verificar se estamos no diretório correto
if [ ! -f "app.py" ]; then
    echo "❌ Execute este script no diretório raiz do projeto (onde está app.py)"
    exit 1
fi

# 1. Verificar se delivery está sendo acessado
echo "1️⃣ PÁGINA DE DELIVERY ESTÁ SENDO ACESSADA?"
echo "==========================================="
echo ""
DELIVERY_ACCESSED=$(tail -2000 logs/gunicorn.log | grep -iE "Delivery.*Renderizando|delivery_page|/delivery/" | wc -l)
echo "   Acessos à página de delivery: $DELIVERY_ACCESSED"
echo ""

# 2. Verificar logs de Delivery
echo "2️⃣ LOGS DE DELIVERY (últimas 50 linhas):"
echo "========================================="
echo ""
tail -2000 logs/gunicorn.log | grep -iE "Delivery|delivery" | tail -50
echo ""

# 3. Verificar se has_meta_pixel é True
echo "3️⃣ has_meta_pixel ESTÁ TRUE?"
echo "============================="
echo ""
HAS_META_PIXEL=$(tail -2000 logs/gunicorn.log | grep -iE "Delivery.*Pixel.*✅|Delivery.*Pixel.*❌|has_meta_pixel.*True|has_meta_pixel.*False" | wc -l)
echo "   Logs de has_meta_pixel: $HAS_META_PIXEL"
echo ""

# 4. Verificar se meta_purchase_sent está sendo marcado
echo "4️⃣ meta_purchase_sent ESTÁ SENDO MARCADO?"
echo "=========================================="
echo ""
META_PURCHASE_SENT=$(tail -2000 logs/gunicorn.log | grep -i "meta_purchase_sent marcado como True" | wc -l)
echo "   meta_purchase_sent marcado: $META_PURCHASE_SENT"
echo ""

# 5. Verificar se send_meta_pixel_purchase_event está sendo chamado
echo "5️⃣ send_meta_pixel_purchase_event ESTÁ SENDO CHAMADO?"
echo "======================================================"
echo ""
PURCHASE_CALLED=$(tail -2000 logs/gunicorn.log | grep -i "Enviando Purchase via Server" | wc -l)
echo "   Chamadas a send_meta_pixel_purchase_event: $PURCHASE_CALLED"
echo ""

# 6. Verificar erros ao enviar Purchase
echo "6️⃣ ERROS AO ENVIAR PURCHASE?"
echo "============================="
echo ""
tail -2000 logs/gunicorn.log | grep -iE "Erro ao enviar Purchase|Purchase.*erro|Purchase.*error|Purchase.*exception" | tail -20
echo ""

# 7. Verificar logs de Delivery para uma venda específica
echo "7️⃣ LOGS DE DELIVERY PARA VENDA ESPECÍFICA (última venda):"
echo "=========================================================="
echo ""
LAST_PAYMENT_ID=$(psql -U postgres -d grimbots -t -c "
SELECT payment_id FROM payments 
WHERE status = 'paid' 
AND meta_purchase_sent = true 
AND meta_event_id IS NULL 
ORDER BY created_at DESC 
LIMIT 1;
" 2>/dev/null | xargs)
if [ -n "$LAST_PAYMENT_ID" ]; then
    echo "   Buscando logs para payment: $LAST_PAYMENT_ID"
    tail -5000 logs/gunicorn.log | grep -i "$LAST_PAYMENT_ID" | grep -iE "Delivery|Purchase|meta_purchase_sent|has_meta_pixel|Pixel" | tail -30
else
    echo "   ❌ Nenhuma venda recente encontrada"
fi
echo ""

# 8. Verificar configuração do pool para essas vendas
echo "8️⃣ CONFIGURAÇÃO DO POOL PARA ESSAS VENDAS:"
echo "==========================================="
echo ""
psql -U postgres -d grimbots -c "
SELECT 
    p.id as payment_id,
    p.meta_purchase_sent,
    p.meta_event_id IS NOT NULL as tem_meta_event_id,
    pool.id as pool_id,
    pool.name as pool_name,
    pool.meta_tracking_enabled,
    pool.meta_events_purchase,
    CASE WHEN pool.meta_pixel_id IS NOT NULL THEN '✅' ELSE '❌' END as has_pixel_id,
    CASE WHEN pool.meta_access_token IS NOT NULL THEN '✅' ELSE '❌' END as has_access_token
FROM payments p
JOIN bots b ON p.bot_id = b.id
JOIN pool_bots pb ON p.bot_id = pb.bot_id
JOIN pools pool ON pb.pool_id = pool.id
WHERE p.status = 'paid'
AND p.meta_purchase_sent = true
AND p.meta_event_id IS NULL
AND p.created_at >= NOW() - INTERVAL '24 hours'
ORDER BY p.created_at DESC
LIMIT 10;
" 2>/dev/null || echo "❌ Erro ao consultar banco de dados"
echo ""

echo "============================================================================"
echo "✅ Verificação concluída!"
echo ""
echo "📋 ANÁLISE DOS RESULTADOS:"
echo ""
echo "   Se 'has_meta_pixel está True' = 0:"
echo "      ❌ PROBLEMA: has_meta_pixel é False"
echo "      ✅ SOLUÇÃO: Verificar configuração do pool (seção 8)"
echo ""
echo "   Se 'meta_purchase_sent está sendo marcado' > 0 mas 'send_meta_pixel_purchase_event está sendo chamado' = 0:"
echo "      ❌ PROBLEMA: meta_purchase_sent está sendo marcado mas send_meta_pixel_purchase_event não está sendo chamado"
echo "      ✅ SOLUÇÃO: Verificar se há erro ao chamar send_meta_pixel_purchase_event (seção 6)"
echo ""
echo "   Se 'meta_purchase_sent está sendo marcado' > 0 e 'send_meta_pixel_purchase_event está sendo chamado' > 0:"
echo "      ❌ PROBLEMA: send_meta_pixel_purchase_event está sendo chamado mas não está funcionando"
echo "      ✅ SOLUÇÃO: Verificar logs de send_meta_pixel_purchase_event (seção 6)"
echo ""
echo "📝 PRÓXIMOS PASSOS:"
echo "   1. Execute: tail -f logs/gunicorn.log | grep -i Delivery para ver logs em tempo real"
echo "   2. Verifique configuração do pool (seção 8)"
echo "   3. Verifique logs de uma venda específica (seção 7)"
echo "   4. Teste com uma nova venda após corrigir o problema"
echo ""

