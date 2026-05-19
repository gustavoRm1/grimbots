#!/bin/bash

echo "🔍 VERIFICANDO - Por que Purchase não está sendo enfileirado?"
echo "=============================================================="
echo ""

# Verificar se estamos no diretório correto
if [ ! -f "app.py" ]; then
    echo "❌ Execute este script no diretório raiz do projeto (onde está app.py)"
    exit 1
fi

# 1. Verificar se send_meta_pixel_purchase_event está sendo chamado
echo "1️⃣ send_meta_pixel_purchase_event ESTÁ SENDO CHAMADO?"
echo "======================================================"
echo ""
PURCHASE_CALLED=$(tail -2000 logs/gunicorn.log | grep -i "Purchase - Iniciando send_meta_pixel_purchase_event" | wc -l)
echo "   Chamadas a send_meta_pixel_purchase_event: $PURCHASE_CALLED"
echo ""

# 2. Verificar se há erros bloqueando Purchase ANTES de enfileirar
echo "2️⃣ ERROS BLOQUEANDO PURCHASE ANTES DE ENFILEIRAR:"
echo "=================================================="
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
echo "   f) Purchase marcado como enviado mas sem meta_event_id:"
tail -2000 logs/gunicorn.log | grep -i "Purchase marcado como enviado, mas CAPI ainda não foi enviado" | wc -l | xargs echo "      "
echo ""

# 3. Verificar se Purchase está sendo preparado
echo "3️⃣ PURCHASE ESTÁ SENDO PREPARADO?"
echo "=================================="
echo ""
PURCHASE_PREPARING=$(tail -2000 logs/gunicorn.log | grep -i "Preparando envio Meta Purchase" | wc -l)
echo "   Purchase sendo preparado: $PURCHASE_PREPARING"
echo ""

# 4. Verificar se Purchase está sendo enfileirado
echo "4️⃣ PURCHASE ESTÁ SENDO ENFILEIRADO?"
echo "===================================="
echo ""
PURCHASE_QUEUED=$(tail -2000 logs/gunicorn.log | grep -i "Purchase enfileirado|INICIANDO ENFILEIRAMENTO" | wc -l)
echo "   Purchase enfileirados: $PURCHASE_QUEUED"
echo ""

# 5. Verificar se há erros ao enfileirar
echo "5️⃣ ERROS AO ENFILEIRAR PURCHASE?"
echo "================================="
echo ""
tail -2000 logs/gunicorn.log | grep -iE "ERRO.*enfileirar Purchase|Erro.*Purchase.*Celery|Purchase.*exception|Purchase.*error" | tail -10
echo ""

# 6. Verificar logs de Purchase para uma venda específica
echo "6️⃣ LOGS DE PURCHASE PARA VENDA RECENTE (última venda):"
echo "======================================================"
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
    tail -2000 logs/gunicorn.log | grep -i "$LAST_PAYMENT_ID" | grep -iE "Purchase|META PURCHASE|DEBUG" | tail -20
else
    echo "   ❌ Nenhuma venda recente encontrada"
fi
echo ""

# 7. Verificar últimos logs de Purchase
echo "7️⃣ ÚLTIMOS LOGS DE PURCHASE (últimas 30 linhas):"
echo "================================================="
echo ""
tail -2000 logs/gunicorn.log | grep -iE "Purchase|META PURCHASE|send_meta_pixel_purchase_event" | tail -30
echo ""

# 8. Verificar logs de Delivery
echo "8️⃣ LOGS DE DELIVERY (últimas 20 linhas):"
echo "========================================="
echo ""
tail -2000 logs/gunicorn.log | grep -iE "Delivery.*Purchase|Delivery.*Enviando Purchase|Delivery.*enfileirado" | tail -20
echo ""

echo "============================================================================"
echo "✅ Verificação concluída!"
echo ""
echo "📋 ANÁLISE DOS RESULTADOS:"
echo ""
echo "   Se 'send_meta_pixel_purchase_event está sendo chamado' = 0:"
echo "      ❌ PROBLEMA: Função não está sendo chamada"
echo "      ✅ SOLUÇÃO: Verificar se delivery.html está chamando a função corretamente"
echo ""
echo "   Se há erros bloqueando Purchase:"
echo "      ❌ PROBLEMA: Alguma verificação está bloqueando o Purchase"
echo "      ✅ SOLUÇÃO: Corrigir configuração do pool (seção 2)"
echo ""
echo "   Se 'Purchase está sendo preparado' > 0 mas 'Purchase enfileirados' = 0:"
echo "      ❌ PROBLEMA: Purchase está sendo preparado mas não está sendo enfileirado"
echo "      ✅ SOLUÇÃO: Verificar se há erro ao enfileirar (seção 5)"
echo ""
echo "📝 PRÓXIMOS PASSOS:"
echo "   1. Execute: tail -f logs/gunicorn.log | grep -i Purchase para ver logs em tempo real"
echo "   2. Verifique se há erros bloqueando Purchase (seção 2)"
echo "   3. Verifique logs de uma venda específica (seção 6)"
echo "   4. Teste com uma nova venda após corrigir o problema"
echo ""

