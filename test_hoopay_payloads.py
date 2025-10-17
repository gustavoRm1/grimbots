#!/usr/bin/env python3
"""
Testar diferentes payloads para HooPay
"""

import requests
import json

def test_payloads():
    """Testa diferentes estruturas de payload"""
    api_key = "d7c92c358a7ec4819ce7282ff2f3f70d"
    url = "https://pay.hoopay.com.br/api/v1/charge"
    
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }
    
    # Diferentes payloads para testar
    payloads = [
        # Payload 1: Estrutura simples
        {
            "amount": 1.00,
            "description": "Teste"
        },
        
        # Payload 2: Com customer
        {
            "amount": 1.00,
            "customer": {
                "email": "teste@exemplo.com",
                "name": "Teste Cliente"
            }
        },
        
        # Payload 3: Estrutura completa
        {
            "amount": 1.00,
            "customer": {
                "email": "teste@exemplo.com",
                "name": "Teste Cliente",
                "phone": "11999999999",
                "document": "12345678901"
            },
            "products": [{
                "title": "Teste",
                "amount": 1.00,
                "quantity": 1
            }],
            "payments": [{
                "amount": 1.00,
                "type": "pix"
            }]
        },
        
        # Payload 4: Com split
        {
            "amount": 1.00,
            "customer": {
                "email": "teste@exemplo.com",
                "name": "Teste Cliente"
            },
            "products": [{
                "title": "Teste",
                "amount": 1.00,
                "quantity": 1
            }],
            "payments": [{
                "amount": 1.00,
                "type": "pix"
            }],
            "commissions": [{
                "userId": "5547db08-12c5-4de5-9592-90d38479745c",
                "type": "platform",
                "amount": 0.04
            }]
        },
        
        # Payload 5: Estrutura alternativa
        {
            "value": 1.00,
            "currency": "BRL",
            "payment_method": "pix",
            "customer_email": "teste@exemplo.com"
        }
    ]
    
    print("📦 TESTANDO DIFERENTES PAYLOADS HOOAY...")
    
    for i, payload in enumerate(payloads, 1):
        print(f"\n{i}️⃣ Payload {i}:")
        print(f"📤 Payload: {json.dumps(payload, indent=2)}")
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=5)
            print(f"📡 Status: {response.status_code}")
            print(f"📋 Response: {response.text[:300]}...")
            
            if response.status_code == 200:
                print("✅ SUCESSO!")
                return payload
            elif response.status_code == 400:
                print("⚠️ Bad Request (payload pode estar quase correto)")
            elif response.status_code == 401:
                print("🔐 Erro de autenticação")
            elif response.status_code == 404:
                print("❌ Não encontrado")
            elif response.status_code == 405:
                print("❌ Método não permitido")
            else:
                print(f"⚠️ Status inesperado: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Erro: {e}")
    
    print("\n🎯 TESTE DE PAYLOADS CONCLUÍDO!")

if __name__ == '__main__':
    test_payloads()
