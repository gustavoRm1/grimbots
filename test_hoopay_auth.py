#!/usr/bin/env python3
"""
Testar diferentes métodos de autenticação HooPay
"""

import requests
import base64

def test_auth_methods():
    """Testa diferentes métodos de autenticação"""
    api_key = "d7c92c358a7ec4819ce7282ff2f3f70d"
    
    # URL que sabemos que existe (pay.hoopay.com.br)
    url = "https://pay.hoopay.com.br/api/v1/charge"
    
    payload = {
        "amount": 1.00,
        "customer": {
            "email": "teste@exemplo.com",
            "name": "Teste Cliente"
        }
    }
    
    print("🔐 TESTANDO MÉTODOS DE AUTENTICAÇÃO HOOAY...")
    
    # Método 1: Bearer Token
    print("\n1️⃣ Bearer Token:")
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        print(f"📡 Status: {response.status_code}")
        print(f"📋 Response: {response.text[:200]}...")
    except Exception as e:
        print(f"❌ Erro: {e}")
    
    # Método 2: Basic Auth (token como username)
    print("\n2️⃣ Basic Auth (token como username):")
    try:
        response = requests.post(
            url, 
            json=payload, 
            auth=(api_key, ''),
            headers={'Content-Type': 'application/json'},
            timeout=5
        )
        print(f"📡 Status: {response.status_code}")
        print(f"📋 Response: {response.text[:200]}...")
    except Exception as e:
        print(f"❌ Erro: {e}")
    
    # Método 3: Basic Auth (token como password)
    print("\n3️⃣ Basic Auth (token como password):")
    try:
        response = requests.post(
            url, 
            json=payload, 
            auth=('', api_key),
            headers={'Content-Type': 'application/json'},
            timeout=5
        )
        print(f"📡 Status: {response.status_code}")
        print(f"📋 Response: {response.text[:200]}...")
    except Exception as e:
        print(f"❌ Erro: {e}")
    
    # Método 4: Header X-API-Key
    print("\n4️⃣ Header X-API-Key:")
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-API-Key': api_key
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        print(f"📡 Status: {response.status_code}")
        print(f"📋 Response: {response.text[:200]}...")
    except Exception as e:
        print(f"❌ Erro: {e}")
    
    # Método 5: Header Authorization com Token
    print("\n5️⃣ Header Authorization Token:")
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': f'Token {api_key}'
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        print(f"📡 Status: {response.status_code}")
        print(f"📋 Response: {response.text[:200]}...")
    except Exception as e:
        print(f"❌ Erro: {e}")
    
    print("\n🎯 TESTE DE AUTENTICAÇÃO CONCLUÍDO!")

if __name__ == '__main__':
    test_auth_methods()
