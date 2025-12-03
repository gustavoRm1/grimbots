#!/bin/bash
# Script para verificar se Celery está processando Purchase events

echo "=================================================================================="
echo "🔍 VERIFICANDO CELERY E PURCHASE EVENTS"
echo "=================================================================================="
echo

# 1. Verificar se Celery está rodando
echo "📊 1. STATUS DO CELERY:"
echo "----------------------------------------------------------------------------------"
if systemctl is-active --quiet celery; then
    echo "✅ Celery está RODANDO"
    systemctl status celery --no-pager -l | head -5
else
    echo "❌ Celery NÃO está rodando!"
fi
echo

# 2. Verificar tasks ativas
echo "📊 2. TASKS ATIVAS NO CELERY:"
echo "----------------------------------------------------------------------------------"
celery -A celery_app inspect active 2>/dev/null | head -20 || echo "⚠️ Erro ao verificar tasks ativas"
echo

# 3. Verificar tasks falhadas
echo "📊 3. TASKS FALHADAS (últimas 10):"
echo "----------------------------------------------------------------------------------"
celery -A celery_app inspect reserved 2>/dev/null | head -20 || echo "⚠️ Erro ao verificar tasks falhadas"
echo

# 4. Verificar logs para Purchase events
echo "📊 4. LOGS DE PURCHASE (últimas 20 linhas):"
echo "----------------------------------------------------------------------------------"
if [ -f "/var/log/grimbots/app.log" ]; then
    grep -i "purchase\|meta event" /var/log/grimbots/app.log | tail -20
elif [ -f "logs/app.log" ]; then
    grep -i "purchase\|meta event" logs/app.log | tail -20
else
    echo "⚠️ Arquivo de log não encontrado"
fi
echo

# 5. Verificar erros da Meta API
echo "📊 5. ERROS DA META API (últimas 10):"
echo "----------------------------------------------------------------------------------"
if [ -f "/var/log/grimbots/app.log" ]; then
    grep -i "FAILED\|ERROR\|Meta API Error" /var/log/grimbots/app.log | grep -i purchase | tail -10
elif [ -f "logs/app.log" ]; then
    grep -i "FAILED\|ERROR\|Meta API Error" logs/app.log | grep -i purchase | tail -10
else
    echo "⚠️ Arquivo de log não encontrado"
fi
echo

# 6. Verificar sucessos da Meta API
echo "📊 6. SUCESSOS DA META API - PURCHASE (últimas 5):"
echo "----------------------------------------------------------------------------------"
if [ -f "/var/log/grimbots/app.log" ]; then
    grep -i "SUCCESS.*Purchase\|events_received.*Purchase" /var/log/grimbots/app.log | tail -5
elif [ -f "logs/app.log" ]; then
    grep -i "SUCCESS.*Purchase\|events_received.*Purchase" logs/app.log | tail -5
else
    echo "⚠️ Arquivo de log não encontrado"
fi
echo

echo "=================================================================================="
echo "✅ VERIFICAÇÃO CONCLUÍDA"
echo "=================================================================================="

