#!/bin/bash

echo "🔍 DIAGNÓSTICO - Por que Purchase Events não estão aparecendo no Meta Event Manager?"
echo "================================================================================"
echo ""

# 1. Verificar vendas recentes (últimas 24 horas)
echo "1️⃣ VENDAS RECENTES (últimas 24 horas):"
echo "---------------------------------------"
echo ""
psql -U postgres -d grimbots -c "
SELECT 
    p.id,
    p.payment_id,
    p.status,
    p.amount,
    p.created_at,
    p.meta_purchase_sent,
    p.meta_event_id,
    p.tracking_token,
    b.id as bot_id,
    b.name as bot_name
FROM payments p
JOIN bots b ON p.bot_id = b.id
WHERE p.status = 'paid'
AND p.created_at >= NOW() - INTERVAL '24 hours'
ORDER BY p.created_at DESC
LIMIT 10;
" 2>/dev/null || echo "❌ Erro ao consultar banco de dados"
echo ""

# 2. Verificar logs de Purchase (últimas 500 linhas)
echo "2️⃣ LOGS DE PURCHASE (últimas 500 linhas):"
echo "------------------------------------------"
echo ""
tail -500 logs/gunicorn.log | grep -iE "Purchase|META PURCHASE|send_meta_pixel_purchase_event" | tail -20
echo ""

# 3. Verificar se Purchase está sendo chamado
echo "3️⃣ PURCHASE ESTÁ SENDO CHAMADO?"
echo "--------------------------------"
echo ""
PURCHASE_CALLED=$(tail -1000 logs/gunicorn.log | grep -i "Purchase - Iniciando send_meta_pixel_purchase_event" | wc -l)
echo "   Chamadas a send_meta_pixel_purchase_event: $PURCHASE_CALLED"
echo ""

# 4. Verificar erros bloqueando Purchase
echo "4️⃣ ERROS BLOQUEANDO PURCHASE:"
echo "------------------------------"
echo ""
echo "   a) Bot não associado a pool:"
tail -1000 logs/gunicorn.log | grep -i "Bot.*não está associado a nenhum pool" | wc -l
echo ""
echo "   b) Meta tracking desabilitado:"
tail -1000 logs/gunicorn.log | grep -i "Meta tracking DESABILITADO" | wc -l
echo ""
echo "   c) Evento Purchase desabilitado:"
tail -1000 logs/gunicorn.log | grep -i "Evento Purchase DESABILITADO" | wc -l
echo ""
echo "   d) Sem pixel_id ou access_token:"
tail -1000 logs/gunicorn.log | grep -i "SEM pixel_id ou access_token" | wc -l
echo ""
echo "   e) Purchase já enviado (bloqueado por duplicação):"
tail -1000 logs/gunicorn.log | grep -i "Purchase já enviado via CAPI" | wc -l
echo ""

# 5. Verificar se Purchase está sendo enviado com sucesso
echo "5️⃣ PURCHASE ESTÁ SENDO ENVIADO COM SUCESSO?"
echo "-------------------------------------------"
echo ""
PURCHASE_SENT=$(tail -1000 logs/gunicorn.log | grep -iE "Purchase ENVIADO|Purchase.*Events Received" | wc -l)
echo "   Purchase enviados com sucesso: $PURCHASE_SENT"
echo ""

# 6. Verificar configuração do pool
echo "6️⃣ CONFIGURAÇÃO DO POOL:"
echo "------------------------"
echo ""
psql -U postgres -d grimbots -c "
SELECT 
    p.id,
    p.name,
    p.meta_tracking_enabled,
    p.meta_events_purchase,
    CASE WHEN p.meta_pixel_id IS NOT NULL THEN '✅' ELSE '❌' END as has_pixel_id,
    CASE WHEN p.meta_access_token IS NOT NULL THEN '✅' ELSE '❌' END as has_access_token
FROM pools p
WHERE p.meta_tracking_enabled = true
LIMIT 5;
" 2>/dev/null || echo "❌ Erro ao consultar banco de dados"
echo ""

# 7. Verificar se delivery.html está sendo acessado
echo "7️⃣ PÁGINA DE DELIVERY ESTÁ SENDO ACESSADA?"
echo "------------------------------------------"
echo ""
DELIVERY_ACCESSED=$(tail -1000 logs/gunicorn.log | grep -iE "Delivery.*Renderizando|delivery.*token" | wc -l)
echo "   Acessos à página de delivery: $DELIVERY_ACCESSED"
echo ""

# 8. Verificar se meta_purchase_sent está sendo marcado
echo "8️⃣ meta_purchase_sent ESTÁ SENDO MARCADO?"
echo "-----------------------------------------"
echo ""
META_PURCHASE_SENT=$(tail -1000 logs/gunicorn.log | grep -i "meta_purchase_sent marcado" | wc -l)
echo "   meta_purchase_sent marcado: $META_PURCHASE_SENT"
echo ""

# 9. Verificar últimas linhas de logs relacionadas a Purchase
echo "9️⃣ ÚLTIMAS LINHAS DE LOGS DE PURCHASE:"
echo "--------------------------------------"
echo ""
tail -1000 logs/gunicorn.log | grep -iE "Purchase|META PURCHASE" | tail -10
echo ""

echo "================================================================================"
echo "✅ Diagnóstico concluído!"
echo ""
echo "📋 PRÓXIMOS PASSOS:"
echo "   1. Verifique se há erros bloqueando Purchase (seção 4)"
echo "   2. Verifique se Purchase está sendo enviado (seção 5)"
echo "   3. Verifique configuração do pool (seção 6)"
echo "   4. Execute: tail -f logs/gunicorn.log | grep -i Purchase para ver logs em tempo real"
echo ""

