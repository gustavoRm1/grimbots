#!/bin/bash

echo "🔍 VERIFICANDO SE HÁ DUPLICAÇÃO DE EVENT_ID"
echo "==========================================="
echo ""

echo "1️⃣ Buscando todos os event_ids dos últimos Purchase events:"
echo ""
tail -1000 logs/gunicorn.log | grep -E "Purchase.*event_id|Delivery.*event_id|purchase_[0-9]+_[0-9]+" | grep -oE "purchase_[0-9]+_[0-9]+" | sort | uniq -c | sort -rn | head -10
echo ""

echo "2️⃣ Verificando se há event_ids duplicados:"
echo ""
DUPLICADOS=$(tail -1000 logs/gunicorn.log | grep -E "purchase_[0-9]+_[0-9]+" | grep -oE "purchase_[0-9]+_[0-9]+" | sort | uniq -d)

if [ -z "$DUPLICADOS" ]; then
    echo "✅ Nenhum event_id duplicado encontrado nos logs"
else
    echo "⚠️ Event IDs duplicados encontrados:"
    echo "$DUPLICADOS"
    echo ""
    echo "Verificando contexto de cada duplicado:"
    for event_id in $DUPLICADOS; do
        echo ""
        echo "--- Event ID: $event_id ---"
        tail -1000 logs/gunicorn.log | grep "$event_id" | tail -3
    done
fi
echo ""

echo "3️⃣ Últimos 5 Purchase events (verificando event_id):"
echo ""
tail -500 logs/gunicorn.log | grep -E "Purchase.*Event Data" | tail -5 | grep -oE "event_id=[^,]+"
echo ""

echo "4️⃣ Verificando se Delivery e Purchase usam mesmo event_id:"
echo ""
# Buscar último event_id do Delivery
LAST_DELIVERY_EVENT_ID=$(tail -500 logs/gunicorn.log | grep -E "Delivery.*event_id que será usado|Delivery.*event_id:" | tail -1 | grep -oE "purchase_[0-9]+_[0-9]+")
LAST_PURCHASE_EVENT_ID=$(tail -500 logs/gunicorn.log | grep -E "Purchase.*event_id recebido como parâmetro|Purchase.*Event Data" | tail -1 | grep -oE "purchase_[0-9]+_[0-9]+")

if [ -n "$LAST_DELIVERY_EVENT_ID" ] && [ -n "$LAST_PURCHASE_EVENT_ID" ]; then
    if [ "$LAST_DELIVERY_EVENT_ID" == "$LAST_PURCHASE_EVENT_ID" ]; then
        echo "✅ Delivery e Purchase usam MESMO event_id: $LAST_DELIVERY_EVENT_ID"
        echo "   ✅ Deduplicação garantida!"
    else
        echo "❌ Delivery e Purchase usam event_ids DIFERENTES:"
        echo "   Delivery: $LAST_DELIVERY_EVENT_ID"
        echo "   Purchase: $LAST_PURCHASE_EVENT_ID"
        echo "   ⚠️ Deduplicação pode não funcionar!"
    fi
else
    echo "⚠️ Não foi possível encontrar event_ids para comparar"
    echo "   Delivery event_id: ${LAST_DELIVERY_EVENT_ID:-NÃO ENCONTRADO}"
    echo "   Purchase event_id: ${LAST_PURCHASE_EVENT_ID:-NÃO ENCONTRADO}"
fi
echo ""

echo "==========================================="
echo "✅ Verificação concluída!"

