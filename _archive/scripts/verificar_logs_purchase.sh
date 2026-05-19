#!/bin/bash
# Script para verificar logs de Purchase events

echo "=================================================================================="
echo "🔍 VERIFICANDO LOGS DE PURCHASE EVENTS"
echo "=================================================================================="
echo

# 1. Verificar logs do Gunicorn (error.log)
echo "📊 1. LOGS DO GUNICORN (error.log):"
echo "----------------------------------------------------------------------------------"
ERROR_LOG=""
if [ -f "/root/grimbots/logs/error.log" ]; then
    ERROR_LOG="/root/grimbots/logs/error.log"
elif [ -f "logs/error.log" ]; then
    ERROR_LOG="logs/error.log"
fi

if [ -n "$ERROR_LOG" ] && [ -f "$ERROR_LOG" ]; then
    echo "✅ Log encontrado: $ERROR_LOG"
    echo "   Últimas 30 linhas relacionadas a Purchase:"
    grep -i "purchase\|meta.*purchase" "$ERROR_LOG" | tail -30 || echo "   (nenhum log de Purchase encontrado)"
else
    echo "⚠️ Arquivo error.log não encontrado"
fi
echo

# 2. Verificar logs do Celery
echo "📊 2. LOGS DO CELERY:"
echo "----------------------------------------------------------------------------------"
CELERY_LOG=""
if [ -f "/var/log/celery/celery.service.log" ]; then
    CELERY_LOG="/var/log/celery/celery.service.log"
elif [ -f "/var/log/celery/worker1.log" ]; then
    CELERY_LOG="/var/log/celery/worker1.log"
fi

if [ -n "$CELERY_LOG" ] && [ -f "$CELERY_LOG" ]; then
    echo "✅ Log encontrado: $CELERY_LOG"
    echo "   Últimas 30 linhas relacionadas a Purchase/Meta:"
    grep -i "purchase\|meta event\|send_meta" "$CELERY_LOG" | tail -30 || echo "   (nenhum log encontrado)"
else
    echo "⚠️ Log do Celery não encontrado"
    echo "   Tentando encontrar..."
    find /var/log/celery -name "*.log" -type f 2>/dev/null | head -5
fi
echo

# 3. Verificar Redis (fila de tasks)
echo "📊 3. VERIFICANDO REDIS (FILA DE TASKS):"
echo "----------------------------------------------------------------------------------"
if command -v redis-cli &> /dev/null; then
    # Verificar fila padrão
    QUEUE_SIZE=$(redis-cli LLEN celery 2>/dev/null || echo "0")
    echo "   Fila 'celery': $QUEUE_SIZE tasks"
    
    # Verificar outras filas possíveis
    echo "   Todas as filas relacionadas ao Celery:"
    redis-cli KEYS "celery*" 2>/dev/null | head -10 || echo "   (nenhuma fila encontrada)"
    
    # Verificar tasks recentes
    if [ "$QUEUE_SIZE" -gt 0 ]; then
        echo "   Primeiras 3 tasks na fila:"
        redis-cli LRANGE celery 0 2 2>/dev/null | head -3
    fi
else
    echo "⚠️ redis-cli não encontrado"
fi
echo

# 4. Verificar se Purchase está sendo enfileirado (logs do app)
if [ -n "$ERROR_LOG" ] && [ -f "$ERROR_LOG" ]; then
    echo "📊 4. PURCHASE ENFILEIRADO (últimas 20):"
    echo "----------------------------------------------------------------------------------"
    grep -i "Purchase enfileirado\|📤 Purchase\|Purchase.*enfileirado" "$ERROR_LOG" | tail -20 || echo "   (nenhum log de enfileiramento encontrado)"
    echo
    
    echo "📊 5. SUCESSOS DA META API - PURCHASE (últimas 10):"
    echo "----------------------------------------------------------------------------------"
    grep -i "SUCCESS.*Purchase\|events_received.*Purchase\|✅.*Purchase.*Meta" "$ERROR_LOG" | tail -10 || echo "   (nenhum sucesso encontrado)"
    echo
    
    echo "📊 6. ERROS DA META API - PURCHASE (últimas 10):"
    echo "----------------------------------------------------------------------------------"
    grep -i "FAILED.*Purchase\|ERROR.*Purchase\|Meta API Error.*Purchase\|❌.*Purchase" "$ERROR_LOG" | tail -10 || echo "   (nenhum erro encontrado)"
    echo
    
    echo "📊 7. DELIVERY PAGE - PURCHASE (últimas 10):"
    echo "----------------------------------------------------------------------------------"
    grep -i "META DELIVERY.*Purchase\|Delivery.*Purchase" "$ERROR_LOG" | tail -10 || echo "   (nenhum log encontrado)"
    echo
fi

# 8. Verificar journalctl (systemd logs)
echo "📊 8. LOGS DO SYSTEMD (journalctl):"
echo "----------------------------------------------------------------------------------"
if command -v journalctl &> /dev/null; then
    echo "   Últimas 20 linhas do serviço Gunicorn relacionadas a Purchase:"
    journalctl -u grimbots -n 100 --no-pager 2>/dev/null | grep -i "purchase\|meta.*purchase" | tail -20 || echo "   (nenhum log encontrado)"
else
    echo "⚠️ journalctl não encontrado"
fi
echo

echo "=================================================================================="
echo "✅ VERIFICAÇÃO CONCLUÍDA"
echo "=================================================================================="
echo
echo "💡 PRÓXIMOS PASSOS:"
echo "   1. Verificar se Purchase está sendo enfileirado (logs acima)"
echo "   2. Verificar se Celery está processando (logs do Celery)"
echo "   3. Verificar se Meta está recebendo (sucessos/erros acima)"
echo "   4. Verificar client-side: acessar /delivery/<token> e verificar console"

