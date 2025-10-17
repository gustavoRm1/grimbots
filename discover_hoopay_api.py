#!/usr/bin/env python3
"""
Descobrir URL correta do HooPay - Debug
"""

import requests
import json

def discover_hoopay_api():
    """Descobre a URL correta da API HooPay"""
    api_key = "d7c92c358a7ec4819ce7282ff2f3f70d"
    
    # Possíveis bases e endpoints
    bases = [
        "https://api.hoopay.com.br",
        "https://pay.hoopay.com.br", 
        "https://hoopay.com.br/api",
        "https://api.hoopay.com.br/api",
        "https://pay.hoopay.com.br/api"
    ]
    
    versions = ["v1", "v2", "api/v1", "api/v2", ""]
    
    endpoints = [
        "payments", "charges", "pix", "transactions", 
        "payment", "charge", "create", "generate"
    ]
    
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }
    
    payload = {
        "amount": 1.00,
        "customer": {
            "email": "teste@exemplo.com",
            "name": "Teste Cliente"
        }
    }
    
    print("🔍 DESCOBRINDO API DO HOOAY...")
    
    for base in bases:
        for version in versions:
            for endpoint in endpoints:
                # Construir URL
                if version:
                    url = f"{base}/{version}/{endpoint}"
                else:
                    url = f"{base}/{endpoint}"
                
                print(f"\n📤 Testando: {url}")
                
                try:
                    response = requests.post(
                        url,
                        json=payload,
                        headers=headers,
                        timeout=5
                    )
                    
                    print(f"📡 Status: {response.status_code}")
                    
                    if response.status_code == 200:
                        print("✅ SUCESSO! URL ENCONTRADA!")
                        print(f"📋 Response: {response.text[:300]}...")
                        return url
                    elif response.status_code == 401:
                        print("🔐 Erro de autenticação (URL pode estar correta)")
                    elif response.status_code == 400:
                        print("⚠️ Bad Request (URL pode estar correta, payload errado)")
                    elif response.status_code == 404:
                        print("❌ Não encontrado")
                    elif response.status_code == 405:
                        print("❌ Método não permitido")
                    else:
                        print(f"⚠️ Status: {response.status_code}")
                        
                except requests.exceptions.Timeout:
                    print("⏰ Timeout")
                except requests.exceptions.ConnectionError:
                    print("🔌 Erro de conexão")
                except Exception as e:
                    print(f"❌ Erro: {e}")
    
    print("\n🎯 BUSCA CONCLUÍDA!")
    print("💡 Se não encontrou, a API pode estar:")
    print("   - Fora do ar")
    print("   - Com URL diferente")
    print("   - Requerendo autenticação diferente")

if __name__ == '__main__':
    discover_hoopay_api()
