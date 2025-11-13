#!/bin/bash
# Verificar Redis para token específico

TOKEN="tracking_446bf80b326e52088176bc86"

echo "=========================================="
echo "  VERIFICAR REDIS - TOKEN"
echo "=========================================="
echo ""

echo "Token: $TOKEN"
echo ""

echo "1. Conteúdo do token no Redis:"
redis-cli GET "tracking:$TOKEN" | python3 -m json.tool 2>/dev/null || redis-cli GET "tracking:$TOKEN"
echo ""

echo "2. Verificar chaves relacionadas:"
redis-cli KEYS "tracking:*$TOKEN*" || echo "Nenhuma chave encontrada"
echo ""

echo "3. Verificar por payment_id:"
redis-cli GET "tracking:payment:BOT44_1763053810_030edbde" | python3 -m json.tool 2>/dev/null || echo "N/A"
echo ""

