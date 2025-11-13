#!/bin/bash
# Monitorar logs do Meta Pixel em tempo real para validar correções

echo "=========================================="
echo "  MONITORAMENTO TEMPO REAL - META PIXEL"
echo "=========================================="
echo ""
echo "Monitorando logs do Celery para eventos Purchase..."
echo "Pressione Ctrl+C para parar"
echo ""

# Filtrar apenas linhas relevantes
tail -f logs/celery.log | grep --line-buffered -E "Purchase|META PAYLOAD|META RESPONSE|creationTime|2804019|event_time|fbc|ERROR|Invalid parameter" | while read line; do
    # Destacar erros
    if echo "$line" | grep -qiE "error|2804019|invalid|creationTime"; then
        echo -e "\033[31m❌ ERRO: $line\033[0m"
    elif echo "$line" | grep -qiE "Purchase ENVIADO|events_received.*1"; then
        echo -e "\033[32m✅ SUCESSO: $line\033[0m"
    elif echo "$line" | grep -qiE "event_time"; then
        # Verificar se event_time está em segundos (10 dígitos) ou milissegundos (13 dígitos)
        if echo "$line" | grep -oE "event_time[^0-9]*[0-9]{13}"; then
            echo -e "\033[33m⚠️  AVISO: event_time parece estar em milissegundos (13 dígitos): $line\033[0m"
        else
            echo -e "\033[36mℹ️  INFO: $line\033[0m"
        fi
    else
        echo "$line"
    fi
done

