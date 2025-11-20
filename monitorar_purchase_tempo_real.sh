#!/bin/bash
# Script para monitorar Purchase events em tempo real

echo "🔍 MONITORANDO PURCHASE EVENTS EM TEMPO REAL"
echo "=============================================="
echo ""
echo "Aguardando Purchase events..."
echo ""

tail -f logs/gunicorn.log | grep --line-buffered -E "Purchase.*fbc|Purchase.*fbclid|Purchase.*Parameter Builder|PARAM BUILDER.*fbc|Purchase.*CRÍTICO|Purchase.*VENDA SERÁ TRACKEADA" | while read line; do
    timestamp=$(date '+%H:%M:%S')
    echo "[$timestamp] $line"
    
    # Destacar mensagens críticas
    if echo "$line" | grep -q "CRÍTICO\|NÃO encontrado\|NÃO retornado"; then
        echo "    ❌ PROBLEMA DETECTADO!"
    elif echo "$line" | grep -q "VENDA SERÁ TRACKEADA\|fbc processado pelo Parameter Builder\|fbc gerado baseado em fbclid"; then
        echo "    ✅ SUCESSO - VENDA SERÁ TRACKEADA!"
    fi
done

