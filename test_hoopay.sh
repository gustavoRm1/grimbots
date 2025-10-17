#!/bin/bash

# ============================================================================
# TESTE ESPECÍFICO DO HOOAY
# ============================================================================

echo "🧪 TESTANDO HOOAY ESPECIFICAMENTE..."

# 1. Verificar se HooPay está ativo
echo "📊 Verificando status do HooPay..."
curl -s -X GET "https://app.grimbots.online/api/gateways" \
  -H "Cookie: session=your_session_cookie" | jq '.[] | select(.gateway_type == "hoopay")'

# 2. Testar geração de PIX via bot
echo "💰 Testando geração de PIX..."
echo "1. Acesse seu bot no Telegram"
echo "2. Clique em um botão de compra"
echo "3. Verifique se aparece o PIX"

# 3. Verificar logs em tempo real
echo "📋 Monitorando logs do HooPay..."
sudo journalctl -u grimbots -f | grep -E "(HooPay|hoopay|Gateway.*hoopay)"

echo "✅ TESTE CONCLUÍDO!"
echo "💡 Se não gerar PIX, verifique:"
echo "   - API Key do HooPay está correta"
echo "   - Organization ID está configurado"
echo "   - Gateway está ativo e verificado"
