#!/bin/bash
# Monitorar especificamente Purchase events em tempo real

echo "=========================================="
echo "  MONITORAMENTO PURCHASE EVENTS"
echo "=========================================="
echo ""
echo "Filtrando apenas Purchase events e payloads"
echo "Pressione Ctrl+C para parar"
echo ""

tail -f logs/celery.log | grep --line-buffered -E "Purchase|META PAYLOAD.*Purchase|META RESPONSE.*Purchase|fbc|fbp" | while read line; do
    # Destacar diferentes tipos de mensagens
    if echo "$line" | grep -qiE "Purchase ENVIADO|events_received.*1|success"; then
        echo -e "\033[32m✅ $line\033[0m"
    elif echo "$line" | grep -qiE "error|2804019|invalid|failed"; then
        echo -e "\033[31m❌ $line\033[0m"
    elif echo "$line" | grep -qiE "META PAYLOAD.*Purchase"; then
        echo -e "\033[35m📤 $line\033[0m"
    elif echo "$line" | grep -qiE "META RESPONSE.*Purchase"; then
        echo -e "\033[36m📥 $line\033[0m"
    elif echo "$line" | grep -qiE "\"fbc\"|\"fbp\""; then
        echo -e "\033[33m🔑 $line\033[0m"
    else
        echo "$line"
    fi
done

