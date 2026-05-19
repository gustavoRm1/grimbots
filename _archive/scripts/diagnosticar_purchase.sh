#!/bin/bash

echo "🔍 DIAGNÓSTICO COMPLETO - Purchase SEM UTMs e Cobertura 0%"
echo "=========================================================="
echo ""

echo "1️⃣ Verificando Purchase events recentes (últimos 200 linhas)..."
echo ""
tail -200 logs/gunicorn.log | grep -i "purchase" | tail -20
echo ""

echo "2️⃣ Verificando Redirect events recentes (últimos 200 linhas)..."
echo ""
tail -200 logs/gunicorn.log | grep -i "redirect" | tail -20
echo ""

echo "3️⃣ Verificando UTMs em qualquer contexto (últimos 200 linhas)..."
echo ""
tail -200 logs/gunicorn.log | grep -i "utm" | tail -20
echo ""

echo "4️⃣ Verificando event_id em qualquer contexto (últimos 200 linhas)..."
echo ""
tail -200 logs/gunicorn.log | grep -i "event_id\|eventID" | tail -20
echo ""

echo "5️⃣ Verificando tracking_token em qualquer contexto (últimos 200 linhas)..."
echo ""
tail -200 logs/gunicorn.log | grep -i "tracking_token\|tracking:token" | tail -20
echo ""

echo "6️⃣ Verificando erros críticos recentes (últimos 200 linhas)..."
echo ""
tail -200 logs/gunicorn.log | grep -i "crítico\|erro.*purchase\|error.*purchase" | tail -20
echo ""

echo "7️⃣ Verificando campaign_code em qualquer contexto (últimos 200 linhas)..."
echo ""
tail -200 logs/gunicorn.log | grep -i "campaign_code\|grim" | tail -20
echo ""

echo "8️⃣ Últimos 50 logs de qualquer tipo relacionados a Meta/Purchase/Redirect..."
echo ""
tail -200 logs/gunicorn.log | grep -iE "meta|purchase|redirect|tracking" | tail -50
echo ""

echo "=========================================================="
echo "✅ Diagnóstico concluído!"
echo ""
echo "📋 PRÓXIMOS PASSOS:"
echo "   1. Verificar se há Purchase events recentes"
echo "   2. Verificar se há Redirect events recentes"
echo "   3. Analisar logs acima para identificar padrões"

