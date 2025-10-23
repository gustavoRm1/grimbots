#!/usr/bin/env python3
"""
INVESTIGAÇÃO FINAL - Paradise API Response
==========================================
Vamos ver exatamente o que a API retorna
"""

import sys
import os
import requests
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Payment, Gateway
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def investigate_paradise_response():
    """Investiga a resposta real da API do Paradise"""
    
    with app.app_context():
        print("=" * 80)
        print("INVESTIGAÇÃO FINAL - PARADISE API RESPONSE")
        print("=" * 80)
        
        # Buscar gateway
        gateway = Gateway.query.filter_by(
            gateway_type='paradise',
            is_verified=True
        ).first()
        
        if not gateway:
            print("❌ Gateway Paradise não encontrado")
            return
        
        print(f"🔑 GATEWAY:")
        print(f"   API Key: {gateway.api_key[:20]}...")
        print(f"   Product Hash: {gateway.product_hash}")
        print(f"   Store ID: {gateway.store_id}")
        
        # Criar transação de teste
        print(f"\n🔧 CRIANDO TRANSAÇÃO DE TESTE:")
        
        test_payload = {
            "amount": 100,  # R$ 1,00
            "description": "Teste Response Investigation",
            "reference": "TEST-RESPONSE-001",
            "checkoutUrl": "https://app.grimbots.online/payment/test",
            "webhookUrl": "https://app.grimbots.online/webhook/payment/paradise",
            "productHash": gateway.product_hash,
            "customer": {
                "name": "Teste Response",
                "email": "teste@response.com",
                "phone": "11999999999",
                "document": "12345678901"
            }
        }
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'X-API-Key': gateway.api_key
        }
        
        try:
            response = requests.post(
                "https://multi.paradisepags.com/api/v1/transaction.php",
                json=test_payload,
                headers=headers,
                timeout=15
            )
            
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"\n📊 ANÁLISE DA RESPOSTA:")
                print(f"   Status: {data.get('status')}")
                print(f"   Transaction ID: {data.get('transaction_id')}")
                print(f"   ID: {data.get('id')}")
                print(f"   QR Code: {data.get('qr_code', 'N/A')[:50]}...")
                print(f"   Amount: {data.get('amount')}")
                print(f"   Acquirer: {data.get('acquirer')}")
                print(f"   Attempts: {data.get('attempts')}")
                print(f"   Expires At: {data.get('expires_at')}")
                
                # Verificar se há campo hash
                if 'hash' in data:
                    print(f"   ✅ HASH ENCONTRADO: {data.get('hash')}")
                else:
                    print(f"   ❌ HASH NÃO ENCONTRADO")
                
                # Verificar todos os campos
                print(f"\n🔍 TODOS OS CAMPOS DA RESPOSTA:")
                for key, value in data.items():
                    print(f"   {key}: {value}")
                
                # Testar consulta imediatamente
                if data.get('transaction_id'):
                    transaction_id = data.get('transaction_id')
                    print(f"\n🔍 TESTANDO CONSULTA IMEDIATA:")
                    print(f"   Transaction ID: {transaction_id}")
                    
                    # Aguardar 5 segundos
                    import time
                    time.sleep(5)
                    
                    # Testar consulta
                    check_url = f"https://multi.paradisepags.com/api/v1/check_status.php?hash={transaction_id}"
                    check_response = requests.get(check_url, headers={'X-API-Key': gateway.api_key}, timeout=10)
                    
                    print(f"   Check Status: {check_response.status_code}")
                    print(f"   Check Response: {check_response.text}")
                    
                    if check_response.status_code == 200:
                        check_data = check_response.json()
                        print(f"   Check Data: {check_data}")
                        
                        if check_data.get('payment_status') != 'not_found':
                            print("   ✅ CONSULTA FUNCIONANDO!")
                        else:
                            print("   ❌ CONSULTA AINDA RETORNA NOT_FOUND")
                            
                            # Testar com diferentes parâmetros
                            print(f"\n🔍 TESTANDO DIFERENTES PARÂMETROS:")
                            
                            test_params = [
                                f"https://multi.paradisepags.com/api/v1/check_status.php?hash={transaction_id}",
                                f"https://multi.paradisepags.com/api/v1/check_status.php?id={transaction_id}",
                                f"https://multi.paradisepags.com/api/v1/check_status.php?transaction_id={transaction_id}",
                                f"https://multi.paradisepags.com/api/v1/check_status.php?reference={transaction_id}",
                            ]
                            
                            for i, url in enumerate(test_params, 1):
                                print(f"   Teste {i}: {url}")
                                try:
                                    test_response = requests.get(url, headers={'X-API-Key': gateway.api_key}, timeout=10)
                                    print(f"      Status: {test_response.status_code}")
                                    print(f"      Response: {test_response.text}")
                                    
                                    if test_response.status_code == 200:
                                        test_data = test_response.json()
                                        if test_data.get('payment_status') != 'not_found':
                                            print(f"      ✅ FUNCIONOU! Status: {test_data.get('payment_status')}")
                                            break
                                            
                                except Exception as e:
                                    print(f"      ❌ Erro: {e}")
                
            else:
                print("   ❌ Erro na criação da transação")
                
        except Exception as e:
            print(f"   ❌ Erro ao testar API: {e}")

if __name__ == '__main__':
    investigate_paradise_response()
