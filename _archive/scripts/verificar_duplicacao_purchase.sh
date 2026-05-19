#!/bin/bash

echo "🔍 VERIFICAR DUPLICAÇÃO DE PURCHASE"
echo "==================================="
echo ""

# 1. Buscar purchases duplicados (mesmo payment_id com múltiplos envios)
echo "1️⃣ PURCHASES DUPLICADOS (mesmo payment_id):"
echo "==========================================="
echo ""

tail -20000 logs/gunicorn.log | grep -iE "Purchase.*payment [0-9]+|payment [0-9]+.*Purchase" | \
  grep -oE "payment [0-9]+" | sort | uniq -c | sort -rn | awk '$1 > 1 {print $1 " envios - payment " $2}' | head -20

if [ $? -ne 0 ] || [ -z "$(tail -20000 logs/gunicorn.log | grep -iE 'Purchase.*payment [0-9]+|payment [0-9]+.*Purchase' | grep -oE 'payment [0-9]+' | sort | uniq -c | sort -rn | awk '\$1 > 1')" ]; then
    echo "   ✅ Nenhum Purchase duplicado encontrado"
fi

echo ""

# 2. Buscar event_ids duplicados
echo "2️⃣ EVENT_IDs DUPLICADOS:"
echo "========================"
echo ""

tail -20000 logs/gunicorn.log | grep -iE "event_id.*purchase|eventID.*purchase|purchase.*event_id|purchase.*eventID" | \
  grep -oE "purchase_[0-9_]+|event_id.*[0-9]+|eventID.*[0-9]+" | sort | uniq -c | sort -rn | awk '$1 > 1 {print $1 " envios - " $2}' | head -20

if [ $? -ne 0 ] || [ -z "$(tail -20000 logs/gunicorn.log | grep -iE 'event_id.*purchase|eventID.*purchase|purchase.*event_id|purchase.*eventID' | grep -oE 'purchase_[0-9_]+|event_id.*[0-9]+|eventID.*[0-9]+' | sort | uniq -c | sort -rn | awk '\$1 > 1')" ]; then
    echo "   ✅ Nenhum event_id duplicado encontrado"
fi

echo ""

# 3. Verificar meta_purchase_sent marcado múltiplas vezes
echo "3️⃣ META_PURCHASE_SENT MARCADO MÚLTIPLAS VEZES:"
echo "=============================================="
echo ""

tail -20000 logs/gunicorn.log | grep -iE "meta_purchase_sent.*True|Purchase.*já foi enviado" | \
  grep -oE "payment [0-9]+" | sort | uniq -c | sort -rn | awk '$1 > 1 {print $1 " marcações - payment " $2}' | head -20

if [ $? -ne 0 ] || [ -z "$(tail -20000 logs/gunicorn.log | grep -iE 'meta_purchase_sent.*True|Purchase.*já foi enviado' | grep -oE 'payment [0-9]+' | sort | uniq -c | sort -rn | awk '\$1 > 1')" ]; then
    echo "   ✅ Nenhum payment marcado múltiplas vezes"
fi

echo ""

# 4. Verificar purchases client-side e server-side para mesmo payment
echo "4️⃣ PURCHASES CLIENT-SIDE E SERVER-SIDE (mesmo payment):"
echo "======================================================"
echo ""

tail -20000 logs/gunicorn.log | grep -iE "Purchase disparado.*eventID|Purchase via Server.*event_id" | \
  grep -oE "payment [0-9]+" | sort | uniq -c | sort -rn | awk '$1 > 1 {print $1 " envios - payment " $2}' | head -20

if [ $? -ne 0 ] || [ -z "$(tail -20000 logs/gunicorn.log | grep -iE 'Purchase disparado.*eventID|Purchase via Server.*event_id' | grep -oE 'payment [0-9]+' | sort | uniq -c | sort -rn | awk '\$1 > 1')" ]; then
    echo "   ✅ Todos os payments têm apenas 1 Purchase (client-side OU server-side)"
fi

echo ""

# 5. Verificar se há purchases sem deduplicação
echo "5️⃣ PURCHASES SEM DEDUPLICAÇÃO (meta_purchase_sent=False mas enviado):"
echo "==================================================================="
echo ""

# Buscar casos onde Purchase foi enviado mas meta_purchase_sent não foi marcado
tail -20000 logs/gunicorn.log | grep -iE "Purchase disparado|Purchase via Server" | \
  grep -vE "meta_purchase_sent.*True|Purchase já foi enviado|pulando client-side" | head -10

echo ""
echo "=========================================="
echo "✅ Verificação concluída!"
echo ""

