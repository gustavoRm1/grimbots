#!/bin/bash

echo "🚨 CORREÇÃO CRÍTICA: Webhook Paradise"
echo "=================================="

echo "📦 Adicionando arquivos..."
git add -A

echo "💾 Commitando correções..."
git commit -m "fix: adicionar webhook URL no payload do Paradise e logs detalhados

- Adicionado webhookUrl no payload do Paradise
- Logs detalhados para debug do webhook
- Correção crítica para receber confirmações de pagamento"

echo "🚀 Fazendo push..."
git push origin main

echo "🔄 Reiniciando serviço na VPS..."
ssh root@seudominio.com "cd /root/grimbots && git pull origin main && sudo systemctl restart grimbots"

echo "✅ Deploy concluído!"
echo ""
echo "🔍 PRÓXIMOS PASSOS:"
echo "1. Teste um novo pagamento"
echo "2. Verifique os logs: journalctl -u grimbots -f"
echo "3. Confirme se o webhook está sendo recebido"
