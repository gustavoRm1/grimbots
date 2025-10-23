#!/bin/bash

echo "🚀 Deploy Paradise Checker - Correção Crítica"
echo "============================================="

git add paradise_payment_checker.py update_paradise_checker.sh
git commit -m "fix: corrigir polling Paradise com retry e backoff

- Paradise demora para processar transações na API
- Aumentado intervalo de busca para 2 horas
- Adicionado retry com 3 tentativas e delay de 30s
- Atualizado cron para executar a cada 2 minutos
- Garante que transações sejam detectadas mesmo com delay"

git push origin main

echo ""
echo "✅ Código enviado para repositório!"
echo ""
echo "🔧 PRÓXIMOS PASSOS NA VPS:"
echo ""
echo "1. Fazer pull do código:"
echo "   cd /root/grimbots && git pull origin main"
echo ""
echo "2. Atualizar cron job:"
echo "   bash update_paradise_checker.sh"
echo ""
echo "3. Verificar se está funcionando:"
echo "   tail -f /root/grimbots/logs/paradise_checker.log"
