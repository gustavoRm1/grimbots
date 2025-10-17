#!/usr/bin/env python3
"""
Teste de URLs do HooPay - Debug
"""

import requests
import json

def test_hoopay_urls():
    """Testa diferentes URLs do HooPay"""
    api_key = "d7c92c358a7ec4819ce7282ff2f3f70d"
    
    # URLs para testar (corrigidas)
    urls_to_test = [
        "https://api.hoopay.com.br/v1/payments",
        "https://api.hoopay.com.br/v1/charges", 
        "https://api.hoopay.com.br/v1/pix",
        "https://api.hoopay.com.br/v1/transactions",
        "https://pay.hoopay.com.br/api/v1/payments",
        "https://pay.hoopay.com.br/api/v1/charges"
    ]
    
    payload = {
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
    }
    
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    print("🧪 TESTANDO URLs DO HOOAY...")
    
    for url in urls_to_test:
        print(f"\n📤 Testando: {url}")
        
        try:
            # Teste com Bearer Token
            headers['Authorization'] = f'Bearer {api_key}'
            
            response = requests.post(
                url,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            print(f"📡 Status: {response.status_code}")
            print(f"📋 Response: {response.text[:200]}...")
            
            if response.status_code == 200:
                print("✅ SUCESSO!")
                break
            elif response.status_code == 401:
                print("🔐 Erro de autenticação")
            elif response.status_code == 404:
                print("❌ URL não encontrada")
            elif response.status_code == 405:
                print("❌ Método não permitido")
            else:
                print(f"⚠️ Status inesperado: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Erro: {e}")
    
    print("\n🎯 TESTE CONCLUÍDO!")

if __name__ == '__main__':
    test_hoopay_urls()
