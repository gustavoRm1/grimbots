#!/bin/bash

echo "🔍 Testando Webhook do Paradise"
echo "==============================="

echo "📡 Fazendo teste de conectividade..."
curl -X POST https://app.grimbots.online/webhook/payment/paradise \
  -H "Content-Type: application/json" \
  -d '{
    "id": "test_123",
    "payment_status": "paid",
    "amount": 1497
  }' \
  -v

echo ""
echo "✅ Teste concluído!"
echo ""
echo "🔍 Verifique os logs:"
echo "journalctl -u grimbots -f | grep 'WEBHOOK RECEBIDO'"

