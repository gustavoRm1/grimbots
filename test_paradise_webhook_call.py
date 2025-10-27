#!/usr/bin/env python3
"""
Teste: Chamar webhook Paradise manualmente
========================================

Simula o webhook que Paradise deveria estar enviando.
"""

import requests
import json
import sys

# Dados da transação aprovada no painel Paradise
webhook_data = {
    "id": "166793",  # Transaction ID da Paradise
    "payment_status": "approved",
    "amount": 1422  # Valor em centavos
}

# URL do webhook configurado
webhook_url = "https://app.grimbots.online/webhook/payment/paradise"

print("=" * 80)
print("TESTE: WEBHOOK PARADISE")
print("=" * 80)
print(f"\n📤 Enviando webhook para: {webhook_url}")
print(f"📦 Dados: {json.dumps(webhook_data, indent=2)}")

try:
    response = requests.post(
        webhook_url,
        json=webhook_data,
        headers={'Content-Type': 'application/json'},
        timeout=10
    )
    
    print(f"\n📥 Status Code: {response.status_code}")
    print(f"📥 Response: {response.text}")
    
    if response.status_code == 200:
        print("\n✅ Webhook enviado com sucesso!")
    else:
        print("\n❌ Webhook falhou!")
        
except Exception as e:
    print(f"\n❌ Erro ao enviar webhook: {e}")

print("\n" + "=" * 80)

