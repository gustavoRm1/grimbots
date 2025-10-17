#!/bin/bash

# ============================================================================
# TESTE DE REINICIALIZAÇÃO AUTOMÁTICA DOS BOTS
# ============================================================================

echo "🧪 TESTANDO REINICIALIZAÇÃO AUTOMÁTICA DOS BOTS..."

# 1. Verificar status atual dos bots
echo "📊 Verificando status atual dos bots..."
curl -s -X GET "https://app.grimbots.online/api/admin/check-bots-status" \
  -H "Cookie: session=your_session_cookie" | jq '.'

# 2. Forçar reinicialização manual
echo "🔄 Forçando reinicialização manual..."
curl -s -X POST "https://app.grimbots.online/api/admin/restart-all-bots" \
  -H "Cookie: session=your_session_cookie" | jq '.'

# 3. Aguardar processamento
echo "⏳ Aguardando processamento..."
sleep 3

# 4. Verificar status após reinicialização
echo "📊 Verificando status após reinicialização..."
curl -s -X GET "https://app.grimbots.online/api/admin/check-bots-status" \
  -H "Cookie: session=your_session_cookie" | jq '.'

# 5. Verificar logs
echo "📋 Verificando logs de reinicialização..."
sudo journalctl -u grimbots -n 20 --no-pager | grep -E "(REINICIALIZAÇÃO|Bot.*reiniciado|Sucessos|Falhas)"

echo "✅ TESTE CONCLUÍDO!"
