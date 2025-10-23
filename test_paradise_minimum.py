#!/usr/bin/env python3
"""
Teste real da API Paradise para descobrir valor mínimo
"""

import requests
import json

# Credenciais da Paradise
API_KEY = "sk_c3728b109649c7ab1d4e19a61189dbb2b07161d6955b8f20b6023c55b8a9e722"
PRODUCT_HASH = "prod_6c60b3dd3ae2c63e"
STORE_ID = "177"

# URL da API
API_URL = "https://multi.paradisepags.com/api/v1/transaction.php"

def test_amount(amount_cents):
    """Testa um valor específico na API Paradise"""
    
    payload = {
        "amount": amount_cents,
        "description": f"Teste valor mínimo - {amount_cents} centavos",
        "reference": f"TEST-{amount_cents}",
        "checkoutUrl": "https://app.grimbots.online/payment/test",
        "productHash": PRODUCT_HASH,
        "customer": {
            "name": "Teste Valor Minimo",
            "email": "teste@valor.minimo",
            "phone": "11999999999",
            "document": "09553238602"
        },
        "split": {
            "store_id": STORE_ID,
            "amount": 1  # 1 centavo para split
        }
    }
    
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-API-Key': API_KEY
    }
    
    print(f"🧪 Testando: R$ {amount_cents/100:.2f} ({amount_cents} centavos)")
    
    try:
        response = requests.post(API_URL, json=payload, headers=headers, timeout=10)
        
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:200]}...")
        
        if response.status_code == 200:
            data = response.json()
            if 'transaction' in data:
                print(f"   ✅ SUCESSO! Valor aceito pela Paradise")
                return True
            else:
                print(f"   ❌ Erro na resposta: {data}")
                return False
        else:
            print(f"   ❌ ERRO! Status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"   ❌ EXCEÇÃO: {e}")
        return False

def main():
    """Testa diferentes valores para descobrir o mínimo"""
    
    print("🔍 TESTE REAL - VALOR MÍNIMO DA PARADISE")
    print("=" * 50)
    
    # Testa valores crescentes
    test_values = [1, 5, 10, 25, 50, 100]  # centavos
    
    for cents in test_values:
        success = test_amount(cents)
        print()
        
        if success:
            print(f"🎯 DESCOBERTO! Valor mínimo da Paradise: R$ {cents/100:.2f}")
            break
    else:
        print("❌ Todos os valores falharam!")

if __name__ == "__main__":
    main()
