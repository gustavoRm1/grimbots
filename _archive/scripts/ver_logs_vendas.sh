#!/bin/bash

echo "📊 LOGS DE VENDAS"
echo "=================="
echo ""

echo "1️⃣ Últimas vendas (últimas 100 linhas):"
echo ""
tail -100 logs/gunicorn.log | grep -iE "payment|venda|purchase|pix" | tail -20
echo ""

echo "2️⃣ Pagamentos gerados (últimos 10):"
echo ""
tail -1000 logs/gunicorn.log | grep -iE "pix.*gerado|payment.*created|payment.*pending" | tail -10
echo ""

echo "3️⃣ Pagamentos confirmados (últimos 10):"
echo ""
tail -1000 logs/gunicorn.log | grep -iE "payment.*paid|status.*paid|payment.*confirmado" | tail -10
echo ""

echo "4️⃣ Purchase events enviados (últimos 10):"
echo ""
tail -1000 logs/gunicorn.log | grep -iE "purchase.*enviado|purchase.*sent|purchase.*events received" | tail -10
echo ""

echo "5️⃣ Erros em vendas (últimos 10):"
echo ""
tail -1000 logs/gunicorn.log | grep -iE "erro.*payment|error.*payment|❌.*payment" | tail -10
echo ""

echo "6️⃣ Últimos 20 logs relacionados a payments:"
echo ""
tail -500 logs/gunicorn.log | grep -i "payment" | tail -20
echo ""

echo "=================="
echo "✅ Verificação concluída!"

