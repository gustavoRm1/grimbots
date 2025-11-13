#!/bin/bash
# Verificar logs do redirect para entender o problema

echo "=========================================="
echo "  VERIFICAÇÃO - LOGS DE REDIRECT"
echo "=========================================="
echo ""

echo "1. Últimos logs de redirect (últimas 100 linhas):"
echo "----------------------------------------"
tail -n 100 logs/error.log | grep -E "Redirect|pageview_event_id|tracking_payload|tracking_token salvo" | tail -30
echo ""

echo "2. Verificar se pageview_event_id está sendo gerado:"
echo "----------------------------------------"
tail -n 200 logs/error.log | grep -E "pageview_event_id|PageView" | tail -20
echo ""

echo "3. Verificar token específico no Redis (último payment):"
echo "----------------------------------------"
export PGPASSWORD=123sefudeu
LAST_TOKEN=$(psql -U grimbots -d grimbots -t -c "SELECT tracking_token FROM payments ORDER BY created_at DESC LIMIT 1;" | xargs)
if [ -n "$LAST_TOKEN" ] && [ "$LAST_TOKEN" != "" ]; then
    echo "Token: $LAST_TOKEN"
    echo ""
    echo "Conteúdo completo do Redis:"
    redis-cli GET "tracking:$LAST_TOKEN" | python3 -m json.tool 2>/dev/null || redis-cli GET "tracking:$LAST_TOKEN"
    echo ""
    echo "Keys relacionadas:"
    redis-cli KEYS "tracking:*$LAST_TOKEN*" 2>/dev/null || echo "Nenhuma chave encontrada"
else
    echo "⚠️  Nenhum payment encontrado"
fi
echo ""

echo "4. Verificar quando o token foi criado (últimos 5 redirects):"
echo "----------------------------------------"
tail -n 500 logs/error.log | grep -E "Redirect - Salvando tracking_payload|tracking_token salvo no Redis" | tail -5
echo ""

echo "=========================================="
echo "  VERIFICAÇÃO CONCLUÍDA"
echo "=========================================="

