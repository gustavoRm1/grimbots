#!/bin/bash

echo "🚀 Deploy Paradise Payment Checker"
echo "==================================="

git add paradise_payment_checker.py install_paradise_checker.sh deploy_paradise_checker.sh
git commit -m "feat: adicionar polling automático para pagamentos Paradise

- Paradise não suporta webhooks automáticos
- Implementado polling a cada 1 minuto via cron
- Atualiza status automaticamente
- Dispara Meta Pixel Purchase
- Notifica clientes via Telegram"

git push origin main

echo ""
echo "✅ Código enviado para repositório!"
echo ""
echo "🔧 PRÓXIMOS PASSOS NA VPS:"
echo ""
echo "1. Fazer pull do código:"
echo "   cd /root/grimbots && git pull origin main"
echo ""
echo "2. Instalar o checker:"
echo "   bash install_paradise_checker.sh"
echo ""
echo "3. Verificar se está funcionando:"
echo "   tail -f /root/grimbots/logs/paradise_checker.log"

