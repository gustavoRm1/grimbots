#!/bin/bash
# Script de Validação Completa - Meta Pixel Tracking
# Execute na VPS: chmod +x scripts/executar_validacao_completa.sh && ./scripts/executar_validacao_completa.sh

set -e

# Configurações do banco (ajustar se necessário)
export PGPASSWORD="${PGPASSWORD:-123sefudeu}"
DB_USER="${DB_USER:-grimbots}"
DB_NAME="${DB_NAME:-grimbots}"

echo "=========================================="
echo "  VALIDAÇÃO COMPLETA - META PIXEL"
echo "=========================================="
echo ""
echo "📤 Executando os 5 comandos de validação..."
echo ""

# 1. Schema do banco
echo "=========================================="
echo "1. SCHEMA DO BANCO (\\d+ payments)"
echo "=========================================="
psql -U "$DB_USER" -d "$DB_NAME" -c "\d+ payments"
echo ""

# 2. Tamanhos das colunas
echo "=========================================="
echo "2. TAMANHOS DAS COLUNAS"
echo "=========================================="
psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT column_name, data_type, character_maximum_length FROM information_schema.columns WHERE table_name='payments' AND column_name IN ('tracking_token','fbclid','pageview_event_id','meta_event_id');"
echo ""

# 3. Verificar truncamento
echo "=========================================="
echo "3. VERIFICAR TRUNCAMENTO"
echo "=========================================="
psql -U "$DB_USER" -d "$DB_NAME" -c "SELECT payment_id, length(fbclid) AS fbclid_len, length(tracking_token) AS token_len, length(meta_event_id) AS event_id_len FROM payments WHERE fbclid IS NOT NULL ORDER BY created_at DESC LIMIT 20;"
echo ""

# 4. Redis - Listar tokens recentes
echo "=========================================="
echo "4. REDIS - TOKENS RECENTES"
echo "=========================================="
echo "Listando últimos 10 tokens:"
redis-cli KEYS "tracking:*" | grep -E "^tracking:[a-f0-9]{32}$" | tail -n 10
echo ""

# Pegar o primeiro token da lista
TOKEN=$(redis-cli KEYS "tracking:*" | grep -E "^tracking:[a-f0-9]{32}$" | tail -n 1)

if [ -z "$TOKEN" ]; then
    echo "⚠️  Nenhum token encontrado no padrão esperado"
    echo "Tentando padrão alternativo (tracking_...):"
    TOKEN=$(redis-cli KEYS "tracking:tracking_*" | tail -n 1)
fi

if [ -n "$TOKEN" ]; then
    echo ""
    echo "Token selecionado: $TOKEN"
    echo ""
    echo "Conteúdo do token:"
    redis-cli GET "$TOKEN" | python3 -m json.tool 2>/dev/null || redis-cli GET "$TOKEN"
else
    echo "⚠️  Nenhum token encontrado para análise"
fi
echo ""

# 5. Logs recentes (últimas 200 linhas)
echo "=========================================="
echo "5. LOGS RECENTES (últimas 200 linhas)"
echo "=========================================="
echo ""
echo "--- logs/rq-webhook.log ---"
if [ -f "logs/rq-webhook.log" ]; then
    tail -n 200 logs/rq-webhook.log | grep -A 5 -B 5 "Purchase ENVIADO\|Meta Purchase\|paid e commitado" || echo "Nenhuma linha encontrada com os padrões"
else
    echo "⚠️  Arquivo logs/rq-webhook.log não encontrado"
fi
echo ""

echo "--- logs/celery.log ---"
if [ -f "logs/celery.log" ]; then
    tail -n 200 logs/celery.log | grep -A 5 -B 5 "Purchase ENVIADO\|Deduplicação\|Events Received" || echo "Nenhuma linha encontrada com os padrões"
else
    echo "⚠️  Arquivo logs/celery.log não encontrado"
fi
echo ""

echo "=========================================="
echo "  VALIDAÇÃO CONCLUÍDA"
echo "=========================================="
echo ""
echo "📋 Cole toda a saída acima para análise final"

