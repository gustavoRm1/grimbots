#!/bin/bash

# Uso: bash ver_venda_especifica.sh <payment_id>
# Exemplo: bash ver_venda_especifica.sh 9380
# Ou: bash ver_venda_especifica.sh BOT43_1763607031_eabd7eaf

if [ -z "$1" ]; then
    echo "❌ Uso: bash ver_venda_especifica.sh <payment_id>"
    echo "   Exemplo: bash ver_venda_especifica.sh 9380"
    echo "   Ou: bash ver_venda_especifica.sh BOT43_1763607031_eabd7eaf"
    exit 1
fi

PAYMENT_ID=$1

echo "🔍 VERIFICANDO VENDA: $PAYMENT_ID"
echo "=================================="
echo ""

echo "1️⃣ Logs relacionados a payment $PAYMENT_ID (últimos 30):"
echo ""
tail -2000 logs/gunicorn.log | grep -i "$PAYMENT_ID" | tail -30
echo ""

echo "2️⃣ Payment gerado:"
echo ""
tail -2000 logs/gunicorn.log | grep -iE "payment.*$PAYMENT_ID.*created|pix.*gerado.*$PAYMENT_ID|payment.*$PAYMENT_ID.*pending" | tail -5
echo ""

echo "3️⃣ Payment confirmado:"
echo ""
tail -2000 logs/gunicorn.log | grep -iE "payment.*$PAYMENT_ID.*paid|status.*paid.*$PAYMENT_ID|payment.*$PAYMENT_ID.*confirmado" | tail -5
echo ""

echo "4️⃣ Purchase event:"
echo ""
tail -2000 logs/gunicorn.log | grep -iE "purchase.*$PAYMENT_ID|payment.*$PAYMENT_ID.*purchase|event_id.*$PAYMENT_ID" | tail -10
echo ""

echo "5️⃣ Tracking/Meta Pixel:"
echo ""
tail -2000 logs/gunicorn.log | grep -iE "$PAYMENT_ID.*tracking|$PAYMENT_ID.*meta|$PAYMENT_ID.*pixel" | tail -10
echo ""

echo "6️⃣ Erros relacionados:"
echo ""
tail -2000 logs/gunicorn.log | grep -iE "erro.*$PAYMENT_ID|error.*$PAYMENT_ID|❌.*$PAYMENT_ID" | tail -5
echo ""

echo "=================================="
echo "✅ Verificação concluída!"

