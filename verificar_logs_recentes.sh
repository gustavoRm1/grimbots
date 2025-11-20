#!/bin/bash

echo "🔍 VERIFICANDO LOGS RECENTES - Últimas 500 linhas"
echo "=================================================="
echo ""

echo "1️⃣ Últimas 30 linhas do log (para ver o que está acontecendo agora)..."
echo ""
tail -30 logs/gunicorn.log
echo ""

echo "2️⃣ Todas as linhas contendo 'Purchase' (últimas 500 linhas)..."
echo ""
tail -500 logs/gunicorn.log | grep -i "purchase" | tail -30
echo ""

echo "3️⃣ Todas as linhas contendo 'Redirect' (últimas 500 linhas)..."
echo ""
tail -500 logs/gunicorn.log | grep -i "redirect" | tail -30
echo ""

echo "4️⃣ Todas as linhas contendo 'utm' ou 'campaign' (últimas 500 linhas)..."
echo ""
tail -500 logs/gunicorn.log | grep -iE "utm|campaign" | tail -30
echo ""

echo "5️⃣ Todas as linhas contendo 'event_id' ou 'pageview_event_id' (últimas 500 linhas)..."
echo ""
tail -500 logs/gunicorn.log | grep -iE "event_id|pageview_event_id" | tail -30
echo ""

echo "6️⃣ Todas as linhas contendo 'tracking' (últimas 500 linhas)..."
echo ""
tail -500 logs/gunicorn.log | grep -i "tracking" | tail -30
echo ""

echo "=================================================="
echo "✅ Verificação concluída!"

