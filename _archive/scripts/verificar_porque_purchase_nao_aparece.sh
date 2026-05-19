#!/bin/bash

echo "🔍 DIAGNÓSTICO COMPLETO - Por que Purchase não aparece no Meta Event Manager?"
echo "=============================================================================="
echo ""

# Verificar se estamos no diretório correto
if [ ! -f "app.py" ]; then
    echo "❌ Execute este script no diretório raiz do projeto (onde está app.py)"
    exit 1
fi

# 1. Verificar vendas recentes (últimas 8 vendas)
echo "1️⃣ VENDAS RECENTES (últimas 8 vendas):"
echo "======================================="
psql -U postgres -d grimbots -c "
SELECT 
    p.id,
    p.payment_id,
    p.status,
    p.amount,
    p.created_at,
    p.delivery_token IS NOT NULL as tem_delivery_token,
    p.meta_purchase_sent,
    p.meta_event_id IS NOT NULL as tem_meta_event_id,
    b.name as bot_name,
    pb.pool_id
FROM payments p
JOIN bots b ON p.bot_id = b.id
LEFT JOIN pool_bots pb ON p.bot_id = pb.bot_id
WHERE p.status = 'paid'
AND p.created_at >= NOW() - INTERVAL '24 hours'
ORDER BY p.created_at DESC
LIMIT 8;
" 2>/dev/null || echo "❌ Erro ao consultar banco de dados"
echo ""

# 2. Verificar se delivery_token foi gerado
echo "2️⃣ DELIVERY_TOKEN FOI GERADO?"
echo "=============================="
echo ""
DELIVERY_TOKENS=$(psql -U postgres -d grimbots -t -c "
SELECT COUNT(*) 
FROM payments 
WHERE status = 'paid' 
AND delivery_token IS NOT NULL 
AND created_at >= NOW() - INTERVAL '24 hours';
" 2>/dev/null | xargs)
echo "   Vendas com delivery_token: $DELIVERY_TOKENS"
echo ""

# 3. Verificar se link de delivery foi enviado
echo "3️⃣ LINK DE DELIVERY FOI ENVIADO?"
echo "================================="
echo ""
DELIVERY_SENT=$(tail -2000 logs/gunicorn.log | grep -i "Entregável enviado\|delivery_token" | wc -l)
echo "   Logs de entregável enviado: $DELIVERY_SENT"
echo ""

# 4. Verificar se página de delivery foi acessada
echo "4️⃣ PÁGINA DE DELIVERY FOI ACESSADA?"
echo "===================================="
echo ""
DELIVERY_ACCESSED=$(tail -2000 logs/gunicorn.log | grep -iE "Delivery.*Renderizando|delivery_page|/delivery/" | wc -l)
echo "   Acessos à página de delivery: $DELIVERY_ACCESSED"
echo ""

# 5. Verificar se Purchase está sendo chamado
echo "5️⃣ PURCHASE ESTÁ SENDO CHAMADO?"
echo "==============================="
echo ""
PURCHASE_CALLED=$(tail -2000 logs/gunicorn.log | grep -i "Purchase - Iniciando send_meta_pixel_purchase_event" | wc -l)
echo "   Chamadas a send_meta_pixel_purchase_event: $PURCHASE_CALLED"
echo ""

# 6. Verificar erros bloqueando Purchase
echo "6️⃣ ERROS BLOQUEANDO PURCHASE:"
echo "=============================="
echo ""
echo "   a) Bot não associado a pool:"
tail -2000 logs/gunicorn.log | grep -i "Bot.*não está associado a nenhum pool" | wc -l | xargs echo "      "
echo ""
echo "   b) Meta tracking desabilitado:"
tail -2000 logs/gunicorn.log | grep -i "Meta tracking DESABILITADO" | wc -l | xargs echo "      "
echo ""
echo "   c) Evento Purchase desabilitado:"
tail -2000 logs/gunicorn.log | grep -i "Evento Purchase DESABILITADO" | wc -l | xargs echo "      "
echo ""
echo "   d) Sem pixel_id ou access_token:"
tail -2000 logs/gunicorn.log | grep -i "SEM pixel_id ou access_token" | wc -l | xargs echo "      "
echo ""
echo "   e) Purchase já enviado (bloqueado por duplicação):"
tail -2000 logs/gunicorn.log | grep -i "Purchase já enviado via CAPI" | wc -l | xargs echo "      "
echo ""

# 7. Verificar se Purchase está sendo enviado com sucesso
echo "7️⃣ PURCHASE ESTÁ SENDO ENVIADO COM SUCESSO?"
echo "==========================================="
echo ""
PURCHASE_SENT=$(tail -2000 logs/gunicorn.log | grep -iE "Purchase ENVIADO|Purchase.*Events Received.*1" | wc -l)
echo "   Purchase enviados com sucesso: $PURCHASE_SENT"
echo ""

# 8. Verificar configuração do pool
echo "8️⃣ CONFIGURAÇÃO DO POOL:"
echo "========================"
echo ""
psql -U postgres -d grimbots -c "
SELECT 
    p.id,
    p.name,
    p.meta_tracking_enabled as tracking_enabled,
    p.meta_events_purchase as purchase_enabled,
    CASE WHEN p.meta_pixel_id IS NOT NULL THEN '✅' ELSE '❌' END as has_pixel_id,
    CASE WHEN p.meta_access_token IS NOT NULL THEN '✅' ELSE '❌' END as has_access_token,
    COUNT(pb.bot_id) as bots_associados
FROM pools p
LEFT JOIN pool_bots pb ON p.id = pb.pool_id
WHERE p.meta_tracking_enabled = true
GROUP BY p.id, p.name, p.meta_tracking_enabled, p.meta_events_purchase, p.meta_pixel_id, p.meta_access_token
LIMIT 5;
" 2>/dev/null || echo "❌ Erro ao consultar banco de dados"
echo ""

# 9. Verificar últimos logs de Purchase
echo "9️⃣ ÚLTIMOS LOGS DE PURCHASE (últimas 15 linhas):"
echo "================================================="
echo ""
tail -2000 logs/gunicorn.log | grep -iE "Purchase|META PURCHASE" | tail -15
echo ""

# 10. Verificar últimos logs de Delivery
echo "🔟 ÚLTIMOS LOGS DE DELIVERY (últimas 10 linhas):"
echo "================================================="
echo ""
tail -2000 logs/gunicorn.log | grep -iE "Delivery|delivery_token|Entregável enviado" | tail -10
echo ""

echo "=============================================================================="
echo "✅ Diagnóstico concluído!"
echo ""
echo "📋 ANÁLISE DOS RESULTADOS:"
echo ""
echo "   Se 'delivery_token foi gerado' = 0:"
echo "      ❌ PROBLEMA: delivery_token não está sendo gerado"
echo "      ✅ SOLUÇÃO: Verificar send_payment_delivery()"
echo ""
echo "   Se 'link de delivery foi enviado' = 0:"
echo "      ❌ PROBLEMA: Link não está sendo enviado via Telegram"
echo "      ✅ SOLUÇÃO: Verificar send_payment_delivery() e bot_manager"
echo ""
echo "   Se 'página de delivery foi acessada' = 0:"
echo "      ❌ PROBLEMA: Usuários não estão acessando o link"
echo "      ✅ SOLUÇÃO: Verificar se link está sendo enviado corretamente"
echo ""
echo "   Se 'Purchase está sendo chamado' = 0:"
echo "      ❌ PROBLEMA: send_meta_pixel_purchase_event() não está sendo chamado"
echo "      ✅ SOLUÇÃO: Verificar se delivery.html está chamando a função corretamente"
echo ""
echo "   Se há erros bloqueando Purchase:"
echo "      ❌ PROBLEMA: Alguma verificação está bloqueando o Purchase"
echo "      ✅ SOLUÇÃO: Corrigir configuração do pool (seção 8)"
echo ""
echo "   Se 'Purchase está sendo enviado' = 0:"
echo "      ❌ PROBLEMA: Purchase não está sendo enviado para Meta"
echo "      ✅ SOLUÇÃO: Verificar logs de erro da API Meta"
echo ""
echo "📝 PRÓXIMOS PASSOS:"
echo "   1. Identifique qual seção está com problema"
echo "   2. Execute: tail -f logs/gunicorn.log | grep -i Purchase para ver logs em tempo real"
echo "   3. Verifique configuração do pool (seção 8)"
echo "   4. Teste com uma nova venda após corrigir o problema"
echo ""

