#!/bin/bash
# Monitorar especificamente fbc/fbp em tempo real

echo "=========================================="
echo "  MONITORAMENTO fbc/fbp - TEMPO REAL"
echo "=========================================="
echo ""
echo "Filtrando apenas linhas relacionadas a fbc/fbp"
echo "Pressione Ctrl+C para parar"
echo ""

tail -f logs/celery.log logs/error.log 2>/dev/null | grep --line-buffered -iE "fbc|fbp" | while read line; do
    # Destacar diferentes tipos de mensagens
    if echo "$line" | grep -qiE "fbc salvo|fbp salvo|fbc recuperado|fbp recuperado"; then
        echo -e "\033[32m✅ $line\033[0m"
    elif echo "$line" | grep -qiE "fbc não encontrado|fbp não encontrado|fbc ausente"; then
        echo -e "\033[33m⚠️ $line\033[0m"
    elif echo "$line" | grep -qiE "user_data.*fbc|user_data.*fbp"; then
        echo -e "\033[36m🔑 $line\033[0m"
    else
        echo "$line"
    fi
done

