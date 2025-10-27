#!/bin/bash

echo "=========================================="
echo "DEPLOY: Fix Paradise Verification"
echo "=========================================="

# Diretório do projeto
cd /root/grimbots || exit 1

# Ativar venv
source venv/bin/activate

echo ""
echo "📦 1. Commit e Push das correções..."
git add gateway_paradise.py bot_manager.py fix_stats_calculation.py
git commit -m "fix: Corrigir verificação Paradise - usar transaction_id ao invés de hash inexistente"
git push origin main

echo ""
echo "📥 2. Pull na VPS..."
git pull origin main

echo ""
echo "🔄 3. Restart do serviço..."
sudo systemctl restart grimbots

echo ""
echo "✅ 4. Verificar status..."
sudo systemctl status grimbots --no-pager

echo ""
echo "📊 5. Recalcular estatísticas antigas (corrigir bugs de cálculo)..."
python fix_stats_calculation.py

echo ""
echo "✅ DEPLOY CONCLUÍDO!"
echo ""
echo "🧪 Testar verificação de pagamento Paradise:"
echo "   - Criar novo pagamento Paradise"
echo "   - Pagar o PIX"
echo "   - Clicar em 'Verificar Pagamento'"
echo "   - Deve confirmar instantaneamente!"
echo ""
echo "📋 Ver logs:"
echo "   sudo journalctl -u grimbots -f"
echo ""

