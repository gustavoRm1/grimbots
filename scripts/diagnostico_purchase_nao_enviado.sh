#!/bin/bash
# Script de diagnóstico - Purchase não sendo enviado

echo "=========================================="
echo "  DIAGNÓSTICO - PURCHASE NÃO ENVIADO"
echo "=========================================="
echo ""

# 1. Verificar últimos payments
echo "1. ÚLTIMOS PAYMENTS (últimas 2 horas):"
echo "-------------------------------------------"
export PGPASSWORD=123sefudeu
psql -U grimbots -d grimbots -c "SELECT payment_id, status, meta_purchase_sent, meta_event_id, created_at, paid_at FROM payments WHERE created_at >= NOW()-INTERVAL '2 hours' ORDER BY created_at DESC LIMIT 10;"
echo ""

# 2. Verificar logs de webhook
echo "2. LOGS DE WEBHOOK (últimas 50 linhas):"
echo "-------------------------------------------"
if [ -f "logs/rq-webhook.log" ]; then
    tail -n 50 logs/rq-webhook.log | grep -E "Webhook|paid|Meta Purchase|Purchase|status.*paid" || echo "Nenhuma linha encontrada"
else
    echo "⚠️  Arquivo logs/rq-webhook.log não encontrado"
fi
echo ""

# 3. Verificar logs de celery
echo "3. LOGS DE CELERY (últimas 50 linhas):"
echo "-------------------------------------------"
if [ -f "logs/celery.log" ]; then
    tail -n 50 logs/celery.log | grep -E "Purchase|Meta|send_meta" || echo "Nenhuma linha encontrada"
else
    echo "⚠️  Arquivo logs/celery.log não encontrado"
fi
echo ""

# 4. Verificar erros
echo "4. ERROS RECENTES:"
echo "-------------------------------------------"
if [ -f "logs/error.log" ]; then
    tail -n 100 logs/error.log | grep -E "ERROR|Exception|Traceback|Purchase|Meta" | tail -n 20 || echo "Nenhum erro encontrado"
else
    echo "⚠️  Arquivo logs/error.log não encontrado"
fi
echo ""

# 5. Verificar se workers estão rodando
echo "5. WORKERS RODANDO:"
echo "-------------------------------------------"
ps aux | grep -E "rq|celery" | grep -v grep || echo "⚠️  Nenhum worker encontrado"
echo ""

echo "=========================================="
echo "  DIAGNÓSTICO CONCLUÍDO"
echo "=========================================="

