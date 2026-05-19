#!/bin/bash

echo "🔍 VERIFICAR PURCHASE ESPECÍFICO"
echo "================================="
echo ""

# Buscar último log de Purchase problemático (sem fbclid/fbc)
echo "1️⃣ ÚLTIMO PURCHASE PROBLEMÁTICO (sem fbclid/fbc):"
echo "=================================================="
echo ""

# Buscar log mais recente com "Purchase - ❌ CRÍTICO: fbclid NÃO encontrado"
LAST_PROBLEM=$(tail -5000 logs/gunicorn.log | grep -iE "Purchase.*fbclid NÃO encontrado|Purchase.*fbc NÃO retornado" | tail -1)

if [ -z "$LAST_PROBLEM" ]; then
    echo "   ✅ Nenhum Purchase problemático encontrado recentemente"
else
    echo "   ⚠️ Purchase problemático encontrado:"
    echo "   $LAST_PROBLEM"
    echo ""
    
    # Extrair timestamp
    TIMESTAMP=$(echo "$LAST_PROBLEM" | grep -oE "[0-9]{2}:[0-9]{2}:[0-9]{2}" | head -1)
    echo "   📅 Timestamp: $TIMESTAMP"
    echo ""
    
    # Buscar payment_id relacionado (procurar por linhas próximas)
    echo "2️⃣ BUSCANDO DADOS COMPLETOS DESTE PURCHASE:"
    echo "============================================"
    echo ""
    
    # Buscar contexto (20 linhas antes e depois)
    tail -5000 logs/gunicorn.log | grep -B 20 -A 20 "$TIMESTAMP" | grep -iE "Purchase|payment|event_id|meta_purchase_sent" | head -40
fi

echo ""
echo "3️⃣ VERIFICAR DUPLICAÇÃO (últimos 30 minutos):"
echo "=============================================="
echo ""

# Buscar todos os Purchases enviados recentemente
tail -10000 logs/gunicorn.log | grep -iE "Purchase.*disparado|Purchase.*enfileirado|meta_purchase_sent.*True" | tail -20

echo ""
echo "4️⃣ VERIFICAR SE HÁ DUPLICADOS (mesmo payment_id):"
echo "=================================================="
echo ""

# Buscar payment_ids com múltiplos Purchases
tail -10000 logs/gunicorn.log | grep -iE "Purchase.*payment|payment.*Purchase" | grep -oE "payment [0-9]+" | sort | uniq -c | sort -rn | head -10

echo ""
echo "5️⃣ VERIFICAR EVENT_ID DUPLICADOS:"
echo "=================================="
echo ""

# Buscar event_ids duplicados
tail -10000 logs/gunicorn.log | grep -iE "event_id|eventID" | grep -oE "purchase_[0-9_]+|event_id.*purchase" | sort | uniq -c | sort -rn | head -10

echo ""
echo "6️⃣ ÚLTIMOS PURCHASES ENVIADOS (client-side e server-side):"
echo "==========================================================="
echo ""

tail -10000 logs/gunicorn.log | grep -iE "Purchase disparado.*eventID|Purchase via Server.*event_id|meta_purchase_sent.*True" | tail -30

echo ""
echo "=========================================="
echo "✅ Verificação concluída!"
echo ""
echo "📋 PRÓXIMOS PASSOS:"
echo "   1. Se houver Purchase problemático: Verificar se foi enviado mesmo sem fbclid/fbc"
echo "   2. Se houver event_id duplicado: Verificar se são do mesmo payment"
echo "   3. Se houver payment_id duplicado: Verificar deduplicação"
echo ""

