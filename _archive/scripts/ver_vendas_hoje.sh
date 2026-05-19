#!/bin/bash

echo "📊 VENDAS DE HOJE"
echo "=================="
echo ""

# Data de hoje no formato do log (YYYY-MM-DD)
HOJE=$(date +%Y-%m-%d)
ONTEM=$(date -d "1 day ago" +%Y-%m-%d)

echo "1️⃣ Vendas geradas hoje ($HOJE):"
echo ""
grep "$HOJE" logs/gunicorn.log | grep -iE "pix.*gerado|payment.*created|payment.*pending" | wc -l
grep "$HOJE" logs/gunicorn.log | grep -iE "pix.*gerado|payment.*created|payment.*pending" | tail -10
echo ""

echo "2️⃣ Vendas confirmadas hoje ($HOJE):"
echo ""
grep "$HOJE" logs/gunicorn.log | grep -iE "payment.*paid|status.*paid|payment.*confirmado" | wc -l
grep "$HOJE" logs/gunicorn.log | grep -iE "payment.*paid|status.*paid|payment.*confirmado" | tail -10
echo ""

echo "3️⃣ Purchase events enviados hoje ($HOJE):"
echo ""
grep "$HOJE" logs/gunicorn.log | grep -iE "purchase.*enviado|purchase.*sent|purchase.*events received" | wc -l
grep "$HOJE" logs/gunicorn.log | grep -iE "purchase.*enviado|purchase.*sent|purchase.*events received" | tail -10
echo ""

echo "4️⃣ Resumo (últimas 24 horas):"
echo ""
echo "   Geradas: $(tail -10000 logs/gunicorn.log | grep -iE "pix.*gerado|payment.*created" | wc -l)"
echo "   Confirmadas: $(tail -10000 logs/gunicorn.log | grep -iE "payment.*paid|status.*paid" | wc -l)"
echo "   Purchase enviados: $(tail -10000 logs/gunicorn.log | grep -iE "purchase.*enviado|purchase.*sent" | wc -l)"
echo ""

echo "=================="
echo "✅ Verificação concluída!"

