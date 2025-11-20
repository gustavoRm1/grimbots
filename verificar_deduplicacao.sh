#!/bin/bash

echo "🔍 VERIFICAÇÃO COMPLETA DE DEDUPLICAÇÃO"
echo "======================================="
echo ""

echo "1️⃣ Últimos Purchase events gerados (últimos 500 logs):"
echo ""
tail -500 logs/gunicorn.log | grep -E "Purchase.*Event Data|Purchase.*event_id gerado|Purchase.*event_id recebido" | tail -5
echo ""

echo "2️⃣ Event IDs usados (últimos 10):"
echo ""
tail -500 logs/gunicorn.log | grep -E "Purchase.*event_id|Delivery.*event_id" | tail -10 | grep -oE "purchase_[0-9]+_[0-9]+" | sort -u
echo ""

echo "3️⃣ Verificando se pageview_event_id foi passado como parâmetro:"
echo ""
tail -500 logs/gunicorn.log | grep -E "Purchase.*event_id recebido como parâmetro|pageview_event_id NÃO foi passado|Delivery.*event_id que será usado" | tail -5
echo ""

echo "4️⃣ Verificando formato do event_id (deve ser purchase_{id}_{timestamp}):"
echo ""
tail -500 logs/gunicorn.log | grep -E "Purchase.*event_id gerado novo|Purchase.*event_id recebido" | tail -3
echo ""

echo "5️⃣ Verificando se há duplicação (mesmos event_ids):"
echo ""
EVENT_IDS=$(tail -500 logs/gunicorn.log | grep -E "Purchase.*event_id|Delivery.*event_id" | tail -10 | grep -oE "purchase_[0-9]+_[0-9]+")
UNIQUE_COUNT=$(echo "$EVENT_IDS" | sort -u | wc -l)
TOTAL_COUNT=$(echo "$EVENT_IDS" | wc -l)

if [ "$UNIQUE_COUNT" -eq "$TOTAL_COUNT" ]; then
    echo "✅ Todos os event_ids são únicos (não há duplicação nos logs)"
else
    echo "⚠️ Possível duplicação detectada (alguns event_ids aparecem múltiplas vezes)"
    echo "$EVENT_IDS" | sort | uniq -c | sort -rn | head -5
fi
echo ""

echo "6️⃣ Último Purchase enviado com sucesso:"
echo ""
tail -500 logs/gunicorn.log | grep -E "Purchase.*ENVIADO|Purchase.*Events Received" | tail -3
echo ""

echo "======================================="
echo "✅ Verificação concluída!"
echo ""
echo "📋 PRÓXIMOS PASSOS:"
echo "   1. Verificar Event Manager do Meta (Test Events)"
echo "   2. Verificar Event Coverage (deve ser ≥ 75%)"
echo "   3. Confirmar que não há duplicação (1 evento Purchase, não 2)"

