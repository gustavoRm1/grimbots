#!/bin/bash
# Script para encontrar e verificar logs de Purchase

echo "=================================================================================="
echo "🔍 ENCONTRANDO E VERIFICANDO LOGS DE PURCHASE"
echo "=================================================================================="
echo

# 1. Procurar arquivos de log
echo "📊 1. PROCURANDO ARQUIVOS DE LOG:"
echo "----------------------------------------------------------------------------------"

# Possíveis locais
LOG_PATHS=(
    "/root/grimbots/logs/error.log"
    "/root/grimbots/logs/app.log"
    "logs/error.log"
    "logs/app.log"
    "/var/log/grimbots/app.log"
    "/var/log/grimbots/error.log"
)

ERROR_LOG=""
for path in "${LOG_PATHS[@]}"; do
    if [ -f "$path" ]; then
        ERROR_LOG="$path"
        echo "✅ Log encontrado: $path"
        echo "   Tamanho: $(du -h "$path" | cut -f1)"
        echo "   Última modificação: $(stat -c %y "$path" 2>/dev/null || stat -f %Sm "$path" 2>/dev/null)"
        break
    fi
done

if [ -z "$ERROR_LOG" ]; then
    echo "⚠️ Nenhum log encontrado nos caminhos padrão"
    echo "   Procurando em todo o sistema..."
    find /root/grimbots -name "*.log" -type f 2>/dev/null | head -10
    find /var/log -name "*.log" -type f 2>/dev/null | grep -i "app\|error\|grimbots" | head -10
fi
echo

# 2. Verificar logs do Celery
echo "📊 2. LOGS DO CELERY:"
echo "----------------------------------------------------------------------------------"
CELERY_LOGS=(
    "/var/log/celery/celery.service.log"
    "/var/log/celery/worker1.log"
    "/root/grimbots/logs/celery.log"
)

CELERY_LOG=""
for path in "${CELERY_LOGS[@]}"; do
    if [ -f "$path" ]; then
        CELERY_LOG="$path"
        echo "✅ Log do Celery encontrado: $path"
        break
    fi
done

if [ -z "$CELERY_LOG" ]; then
    echo "⚠️ Log do Celery não encontrado"
    echo "   Procurando..."
    find /var/log/celery -name "*.log" -type f 2>/dev/null | head -5
fi
echo

# 3. Se encontrou log, verificar Purchase
if [ -n "$ERROR_LOG" ] && [ -f "$ERROR_LOG" ]; then
    echo "📊 3. PURCHASE ENFILEIRADO (últimas 30):"
    echo "----------------------------------------------------------------------------------"
    grep -i "Purchase enfileirado\|📤 Purchase\|Purchase.*enfileirado\|META PURCHASE.*Purchase.*enfileirado" "$ERROR_LOG" | tail -30 || echo "   (nenhum log encontrado)"
    echo
    
    echo "📊 4. SUCESSOS DA META API - PURCHASE (últimas 20):"
    echo "----------------------------------------------------------------------------------"
    grep -i "SUCCESS.*Purchase\|events_received.*Purchase\|✅.*Purchase.*Meta" "$ERROR_LOG" | tail -20 || echo "   (nenhum sucesso encontrado)"
    echo
    
    echo "📊 5. ERROS DA META API - PURCHASE (últimas 20):"
    echo "----------------------------------------------------------------------------------"
    grep -i "FAILED.*Purchase\|ERROR.*Purchase\|Meta API Error.*Purchase\|❌.*Purchase\|Exception.*Purchase" "$ERROR_LOG" | tail -20 || echo "   (nenhum erro encontrado)"
    echo
    
    echo "📊 6. DELIVERY PAGE - PURCHASE (últimas 20):"
    echo "----------------------------------------------------------------------------------"
    grep -i "META DELIVERY.*Purchase\|Delivery.*Purchase.*enfileirado" "$ERROR_LOG" | tail -20 || echo "   (nenhum log encontrado)"
    echo
    
    echo "📊 7. RESUMO - CONTAGEM:"
    echo "----------------------------------------------------------------------------------"
    TOTAL_ENFILEIRADO=$(grep -i "Purchase enfileirado\|📤 Purchase" "$ERROR_LOG" | wc -l)
    TOTAL_SUCESSO=$(grep -i "SUCCESS.*Purchase\|events_received.*Purchase" "$ERROR_LOG" | wc -l)
    TOTAL_ERRO=$(grep -i "FAILED.*Purchase\|ERROR.*Purchase\|Meta API Error.*Purchase" "$ERROR_LOG" | wc -l)
    
    echo "   Purchase enfileirado: $TOTAL_ENFILEIRADO"
    echo "   Sucessos Meta API: $TOTAL_SUCESSO"
    echo "   Erros Meta API: $TOTAL_ERRO"
    echo
fi

# 4. Verificar Celery logs
if [ -n "$CELERY_LOG" ] && [ -f "$CELERY_LOG" ]; then
    echo "📊 8. LOGS DO CELERY - PURCHASE (últimas 30):"
    echo "----------------------------------------------------------------------------------"
    grep -i "purchase\|meta event\|send_meta" "$CELERY_LOG" | tail -30 || echo "   (nenhum log encontrado)"
    echo
fi

# 5. Verificar Redis
echo "📊 9. VERIFICANDO REDIS:"
echo "----------------------------------------------------------------------------------"
if command -v redis-cli &> /dev/null; then
    QUEUE_SIZE=$(redis-cli LLEN celery 2>/dev/null || echo "0")
    echo "   Fila 'celery': $QUEUE_SIZE tasks"
    
    if [ "$QUEUE_SIZE" -gt 0 ]; then
        echo "   ⚠️ Há tasks na fila! Primeiras 3:"
        redis-cli LRANGE celery 0 2 2>/dev/null | head -3
    else
        echo "   ✅ Fila vazia (tasks processadas ou não enfileiradas)"
    fi
else
    echo "⚠️ redis-cli não encontrado"
fi
echo

echo "=================================================================================="
echo "✅ VERIFICAÇÃO CONCLUÍDA"
echo "=================================================================================="

