#!/usr/bin/env python3
"""
INVESTIGAÇÃO PROFUNDA - Paradise API
====================================
Vamos descobrir o que mudou na API do Paradise
"""

import sys
import os
import requests
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Payment, Gateway
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def investigate_paradise_api():
    """Investiga profundamente a API do Paradise"""
    
    with app.app_context():
        print("=" * 80)
        print("INVESTIGAÇÃO PROFUNDA - PARADISE API")
        print("=" * 80)
        
        # 1. Verificar se há pagamentos Paradise aprovados no banco
        paid_payments = Payment.query.filter_by(
            gateway_type='paradise',
            status='paid'
        ).order_by(Payment.id.desc()).limit(3).all()
        
        print(f"\n📊 PAGAMENTOS PARADISE APROVADOS NO BANCO:")
        if paid_payments:
            for payment in paid_payments:
                print(f"   ✅ {payment.payment_id} | Transaction: {payment.gateway_transaction_id} | Amount: R$ {payment.amount:.2f} | Paid: {payment.paid_at}")
        else:
            print("   ❌ Nenhum pagamento Paradise aprovado encontrado")
        
        # 2. Verificar se há pagamentos Paradise pendentes
        pending_payments = Payment.query.filter_by(
            gateway_type='paradise',
            status='pending'
        ).order_by(Payment.id.desc()).limit(3).all()
        
        print(f"\n📊 PAGAMENTOS PARADISE PENDENTES:")
        if pending_payments:
            for payment in pending_payments:
                print(f"   ⏳ {payment.payment_id} | Transaction: {payment.gateway_transaction_id} | Amount: R$ {payment.amount:.2f} | Created: {payment.created_at}")
        else:
            print("   ❌ Nenhum pagamento Paradise pendente encontrado")
        
        # 3. Verificar se há pagamentos de outros gateways funcionando
        other_payments = Payment.query.filter(
            Payment.gateway_type != 'paradise',
            Payment.status == 'paid'
        ).order_by(Payment.id.desc()).limit(3).all()
        
        print(f"\n📊 PAGAMENTOS DE OUTROS GATEWAYS (FUNCIONANDO):")
        if other_payments:
            for payment in other_payments:
                print(f"   ✅ {payment.gateway_type.upper()} | {payment.payment_id} | Amount: R$ {payment.amount:.2f} | Paid: {payment.paid_at}")
        else:
            print("   ❌ Nenhum pagamento de outros gateways encontrado")
        
        # 4. Testar API Key do Paradise
        print(f"\n🔑 TESTANDO API KEY DO PARADISE:")
        
        gateway = Gateway.query.filter_by(
            gateway_type='paradise',
            is_verified=True
        ).first()
        
        if not gateway:
            print("   ❌ Gateway Paradise não encontrado")
            return
        
        print(f"   API Key: {gateway.api_key[:20]}...")
        print(f"   Product Hash: {gateway.product_hash}")
        print(f"   Store ID: {gateway.store_id}")
        
        # 5. Testar endpoint de verificação com diferentes parâmetros
        print(f"\n🔍 TESTANDO ENDPOINT DE VERIFICAÇÃO:")
        
        # Pegar uma transação para testar
        test_payment = pending_payments[0] if pending_payments else None
        
        if not test_payment:
            print("   ❌ Nenhuma transação para testar")
            return
        
        transaction_id = test_payment.gateway_transaction_id
        print(f"   Transaction ID: {transaction_id}")
        
        # Testar diferentes formatos de URL
        test_urls = [
            f"https://multi.paradisepags.com/api/v1/check_status.php?hash={transaction_id}",
            f"https://multi.paradisepags.com/api/v1/check_status.php?id={transaction_id}",
            f"https://multi.paradisepags.com/api/v1/check_status.php?transaction_id={transaction_id}",
            f"https://multi.paradisepags.com/api/v1/check_status.php?reference={transaction_id}",
        ]
        
        headers = {
            'X-API-Key': gateway.api_key,
            'Accept': 'application/json'
        }
        
        for i, url in enumerate(test_urls, 1):
            print(f"\n   Teste {i}: {url}")
            try:
                response = requests.get(url, headers=headers, timeout=10)
                print(f"      Status: {response.status_code}")
                print(f"      Response: {response.text}")
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('payment_status') != 'not_found':
                        print(f"      ✅ ENCONTRADO! Status: {data.get('payment_status')}")
                        break
                    else:
                        print(f"      ❌ Not found")
                        
            except Exception as e:
                print(f"      ❌ Erro: {e}")
        
        # 6. Verificar se o problema é com a API Key
        print(f"\n🔑 TESTANDO API KEY COM ENDPOINT DE TESTE:")
        
        # Tentar criar uma transação de teste
        test_payload = {
            "amount": 100,  # R$ 1,00
            "description": "Teste API Key",
            "reference": "TEST-API-KEY",
            "checkoutUrl": "https://app.grimbots.online/payment/test",
            "productHash": gateway.product_hash,
            "customer": {
                "name": "Teste",
                "email": "teste@teste.com",
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
                if data.get('status') == 'success':
                    print("   ✅ API Key funcionando - transação criada com sucesso")
                    test_transaction_id = data.get('transaction_id')
                    
                    if test_transaction_id:
                        print(f"   🔍 Testando consulta da transação de teste: {test_transaction_id}")
                        
                        # Aguardar 5 segundos
                        import time
                        time.sleep(5)
                        
                        check_url = f"https://multi.paradisepags.com/api/v1/check_status.php?hash={test_transaction_id}"
                        check_response = requests.get(check_url, headers={'X-API-Key': gateway.api_key}, timeout=10)
                        
                        print(f"   Check Status: {check_response.status_code}")
                        print(f"   Check Response: {check_response.text}")
                        
                        if check_response.status_code == 200:
                            check_data = check_response.json()
                            if check_data.get('payment_status') != 'not_found':
                                print("   ✅ CONSULTA FUNCIONANDO!")
                            else:
                                print("   ❌ CONSULTA AINDA RETORNA NOT_FOUND")
                else:
                    print("   ❌ API Key não funcionando - erro na criação")
            else:
                print("   ❌ API Key não funcionando - status de erro")
                
        except Exception as e:
            print(f"   ❌ Erro ao testar API Key: {e}")

if __name__ == '__main__':
    investigate_paradise_api()
