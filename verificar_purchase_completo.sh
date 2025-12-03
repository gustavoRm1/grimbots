#!/bin/bash
# Script completo para diagnosticar Purchase events

echo "=================================================================================="
echo "🔍 DIAGNÓSTICO COMPLETO - PURCHASE EVENTS"
echo "=================================================================================="
echo

# 1. Encontrar arquivo de log
echo "📊 1. LOCALIZANDO ARQUIVO DE LOG:"
echo "----------------------------------------------------------------------------------"
LOG_FILE=""
if [ -f "/var/log/grimbots/app.log" ]; then
    LOG_FILE="/var/log/grimbots/app.log"
elif [ -f "/root/grimbots/logs/app.log" ]; then
    LOG_FILE="/root/grimbots/logs/app.log"
elif [ -f "logs/app.log" ]; then
    LOG_FILE="logs/app.log"
elif [ -f "app.log" ]; then
    LOG_FILE="app.log"
else
    echo "⚠️ Arquivo de log não encontrado nos caminhos padrão"
    echo "   Procurando em outros locais..."
    find /var/log -name "*.log" -type f 2>/dev/null | grep -i "app\|grimbots" | head -5
    find /root -name "*.log" -type f 2>/dev/null | grep -i "app\|grimbots" | head -5
fi

if [ -n "$LOG_FILE" ]; then
    echo "✅ Log encontrado: $LOG_FILE"
    echo "   Tamanho: $(du -h "$LOG_FILE" | cut -f1)"
    echo "   Última modificação: $(stat -c %y "$LOG_FILE" 2>/dev/null || stat -f %Sm "$LOG_FILE" 2>/dev/null)"
else
    echo "❌ Arquivo de log não encontrado"
fi
echo

# 2. Verificar Redis (fila de tasks)
echo "📊 2. VERIFICANDO REDIS (FILA DE TASKS):"
echo "----------------------------------------------------------------------------------"
if command -v redis-cli &> /dev/null; then
    REDIS_KEYS=$(redis-cli KEYS "celery*" 2>/dev/null | wc -l)
    echo "✅ Redis está acessível"
    echo "   Chaves relacionadas ao Celery: $REDIS_KEYS"
    
    # Verificar fila de tasks
    QUEUE_SIZE=$(redis-cli LLEN celery 2>/dev/null || echo "0")
    echo "   Tamanho da fila 'celery': $QUEUE_SIZE tasks"
    
    # Verificar tasks recentes
    echo "   Últimas 5 tasks na fila:"
    redis-cli LRANGE celery 0 4 2>/dev/null | head -5 || echo "   (fila vazia ou erro)"
else
    echo "⚠️ redis-cli não encontrado"
fi
echo

# 3. Verificar logs do Celery
echo "📊 3. LOGS DO CELERY:"
echo "----------------------------------------------------------------------------------"
CELERY_LOG=""
if [ -f "/var/log/celery/celery.service.log" ]; then
    CELERY_LOG="/var/log/celery/celery.service.log"
elif [ -f "/var/log/celery/worker1.log" ]; then
    CELERY_LOG="/var/log/celery/worker1.log"
fi

if [ -n "$CELERY_LOG" ] && [ -f "$CELERY_LOG" ]; then
    echo "✅ Log do Celery encontrado: $CELERY_LOG"
    echo "   Últimas 20 linhas relacionadas a Purchase:"
    grep -i "purchase\|meta event" "$CELERY_LOG" | tail -20 || echo "   (nenhum log de Purchase encontrado)"
else
    echo "⚠️ Log do Celery não encontrado"
fi
echo

# 4. Verificar logs da aplicação (Purchase)
if [ -n "$LOG_FILE" ] && [ -f "$LOG_FILE" ]; then
    echo "📊 4. LOGS DE PURCHASE (últimas 30 linhas):"
    echo "----------------------------------------------------------------------------------"
    grep -i "purchase.*enfileirado\|delivery.*purchase\|meta.*purchase" "$LOG_FILE" | tail -30 || echo "   (nenhum log encontrado)"
    echo
    
    echo "📊 5. SUCESSOS DA META API - PURCHASE (últimas 10):"
    echo "----------------------------------------------------------------------------------"
    grep -i "SUCCESS.*Purchase\|events_received.*Purchase" "$LOG_FILE" | tail -10 || echo "   (nenhum sucesso encontrado)"
    echo
    
    echo "📊 6. ERROS DA META API - PURCHASE (últimas 10):"
    echo "----------------------------------------------------------------------------------"
    grep -i "FAILED.*Purchase\|ERROR.*Purchase\|Meta API Error" "$LOG_FILE" | tail -10 || echo "   (nenhum erro encontrado)"
    echo
    
    echo "📊 7. PURCHASE ENFILEIRADO (últimas 10):"
    echo "----------------------------------------------------------------------------------"
    grep -i "Purchase enfileirado\|📤 Purchase" "$LOG_FILE" | tail -10 || echo "   (nenhum log de enfileiramento encontrado)"
    echo
fi

# 8. Verificar se Purchase está sendo enviado via client-side
echo "📊 8. VERIFICAR CLIENT-SIDE PURCHASE:"
echo "----------------------------------------------------------------------------------"
echo "   Para verificar client-side:"
echo "   1. Acessar /delivery/<token> no browser"
echo "   2. Abrir Console (F12)"
echo "   3. Procurar por: '[META PIXEL] Purchase disparado (client-side)'"
echo "   4. Verificar Network tab: request para connect.facebook.net"
echo

# 9. Verificar payments recentes com meta_purchase_sent
echo "📊 9. RESUMO:"
echo "----------------------------------------------------------------------------------"
echo "   Execute o diagnóstico Python para verificar:"
echo "   python3 diagnostico_purchase_eventos.py"
echo

echo "=================================================================================="
echo "✅ DIAGNÓSTICO CONCLUÍDO"
echo "=================================================================================="

