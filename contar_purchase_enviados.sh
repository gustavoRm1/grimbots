#!/bin/bash
# Script para contar Purchase events enviados

echo "=================================================================================="
echo "🔍 CONTANDO PURCHASE EVENTS ENVIADOS"
echo "=================================================================================="
echo

CELERY_LOG="/var/log/celery/celery.service.log"

if [ ! -f "$CELERY_LOG" ]; then
    echo "❌ Log do Celery não encontrado: $CELERY_LOG"
    exit 1
fi

echo "📊 1. ESTATÍSTICAS GERAIS (últimas 24h):"
echo "----------------------------------------------------------------------------------"
TOTAL_PAGEVIEW=$(grep -i "SUCCESS.*Meta Event.*PageView" "$CELERY_LOG" | grep -E "$(date -d '24 hours ago' '+%Y-%m-%d')|$(date '+%Y-%m-%d')" | wc -l)
TOTAL_PURCHASE=$(grep -i "SUCCESS.*Meta Event.*Purchase" "$CELERY_LOG" | grep -E "$(date -d '24 hours ago' '+%Y-%m-%d')|$(date '+%Y-%m-%d')" | wc -l)

echo "   PageView enviados: $TOTAL_PAGEVIEW"
echo "   Purchase enviados: $TOTAL_PURCHASE"
echo "   Razão: $(echo "scale=2; $TOTAL_PURCHASE * 100 / $TOTAL_PAGEVIEW" | bc 2>/dev/null || echo "N/A")%"
echo

echo "📊 2. PURCHASE EVENTS (últimas 10):"
echo "----------------------------------------------------------------------------------"
grep -i "SUCCESS.*Meta Event.*Purchase\|📤 META PAYLOAD COMPLETO (Purchase)" "$CELERY_LOG" | grep -E "$(date -d '24 hours ago' '+%Y-%m-%d')|$(date '+%Y-%m-%d')" | tail -10 || echo "   (nenhum Purchase encontrado)"
echo

echo "📊 3. EVENT_IDs DOS PURCHASES (últimos 5):"
echo "----------------------------------------------------------------------------------"
grep -i "SUCCESS.*Meta Event.*Purchase" "$CELERY_LOG" | grep -E "$(date -d '24 hours ago' '+%Y-%m-%d')|$(date '+%Y-%m-%d')" | grep -oP "ID: \K[^ ]+" | tail -5 || echo "   (nenhum Purchase encontrado)"
echo

echo "📊 4. META RESPONSE - PURCHASE (últimos 5):"
echo "----------------------------------------------------------------------------------"
grep -A 5 "📥 META RESPONSE (Purchase)" "$CELERY_LOG" | grep -E "$(date -d '24 hours ago' '+%Y-%m-%d')|$(date '+%Y-%m-%d')" | tail -15 || echo "   (nenhum Purchase encontrado)"
echo

echo "📊 5. RESUMO:"
echo "----------------------------------------------------------------------------------"
echo "   ✅ Purchase está sendo enviado via Celery"
echo "   ✅ Meta está recebendo (events_received: 1)"
echo "   ⚠️ Mas apenas $TOTAL_PURCHASE Purchase enviados vs $TOTAL_PAGEVIEW PageView"
echo "   💡 Possível problema: Client-side Purchase não dispara ou deduplicação falha"
echo

echo "=================================================================================="
echo "✅ ANÁLISE CONCLUÍDA"
echo "=================================================================================="

