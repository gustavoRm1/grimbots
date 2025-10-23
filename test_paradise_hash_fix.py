#!/usr/bin/env python3
"""
TESTE DA CORREÇÃO CRÍTICA - Paradise Hash
========================================
Testa se a correção do hash resolve o problema
"""

import sys
import os
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Payment, Gateway
from gateway_factory import GatewayFactory
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_paradise_hash_fix():
    """Testa a correção do hash do Paradise"""
    
    with app.app_context():
        print("=" * 80)
        print("TESTE DA CORREÇÃO CRÍTICA - PARADISE HASH")
        print("=" * 80)
        
        # 1. Executar migração
        print("\n🔧 EXECUTANDO MIGRAÇÃO:")
        try:
            from migrate_add_transaction_hash import migrate_add_transaction_hash
            migrate_add_transaction_hash()
        except Exception as e:
            print(f"❌ Erro na migração: {e}")
        
        # 2. Criar uma transação de teste
        print("\n🔧 CRIANDO TRANSAÇÃO DE TESTE:")
        
        gateway = Gateway.query.filter_by(
            gateway_type='paradise',
            is_verified=True
        ).first()
        
        if not gateway:
            print("❌ Gateway Paradise não encontrado")
            return
        
        credentials = {
            'api_key': gateway.api_key,
            'product_hash': gateway.product_hash,
            'offer_hash': gateway.offer_hash,
            'store_id': gateway.store_id,
            'split_percentage': gateway.split_percentage or 4.0
        }
        
        payment_gateway = GatewayFactory.create_gateway('paradise', credentials)
        
        if not payment_gateway:
            print("❌ Falha ao criar gateway")
            return
        
        # Criar transação de teste
        test_result = payment_gateway.generate_pix(
            amount=1.00,  # R$ 1,00
            description="Teste Hash Fix",
            payment_id=999999,
            customer_data={
                'name': 'Teste Hash',
                'email': 'teste@hash.com',
                'phone': '11999999999',
                'document': '12345678901'
            }
        )
        
        if not test_result:
            print("❌ Falha ao criar transação de teste")
            return
        
        print(f"✅ Transação criada:")
        print(f"   Transaction ID: {test_result.get('transaction_id')}")
        print(f"   Transaction Hash: {test_result.get('transaction_hash')}")
        
        # 3. Testar consulta com hash
        print(f"\n🔍 TESTANDO CONSULTA COM HASH:")
        
        transaction_id = test_result.get('transaction_id')
        transaction_hash = test_result.get('transaction_hash')
        
        if transaction_hash:
            print(f"   Usando Hash: {transaction_hash}")
            
            # Testar consulta direta
            check_url = f"https://multi.paradisepags.com/api/v1/check_status.php?hash={transaction_hash}"
            headers = {
                'X-API-Key': gateway.api_key,
                'Accept': 'application/json'
            }
            
            try:
                response = requests.get(check_url, headers=headers, timeout=10)
                print(f"   Status: {response.status_code}")
                print(f"   Response: {response.text}")
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('payment_status') != 'not_found':
                        print("   ✅ CONSULTA FUNCIONANDO COM HASH!")
                    else:
                        print("   ❌ AINDA RETORNA NOT_FOUND")
                        
            except Exception as e:
                print(f"   ❌ Erro na consulta: {e}")
        
        # 4. Testar consulta via gateway
        print(f"\n🔧 TESTANDO CONSULTA VIA GATEWAY:")
        
        api_status = payment_gateway.get_payment_status(
            transaction_id,
            transaction_hash
        )
        
        if api_status:
            print(f"✅ Gateway retornou: {api_status}")
        else:
            print("❌ Gateway retornou None")
        
        # 5. Testar com transação existente
        print(f"\n🔍 TESTANDO COM TRANSAÇÃO EXISTENTE:")
        
        existing_payment = Payment.query.filter_by(
            gateway_type='paradise',
            status='pending'
        ).order_by(Payment.id.desc()).first()
        
        if existing_payment:
            print(f"   Payment ID: {existing_payment.payment_id}")
            print(f"   Transaction ID: {existing_payment.gateway_transaction_id}")
            print(f"   Transaction Hash: {existing_payment.gateway_transaction_hash}")
            
            if existing_payment.gateway_transaction_hash:
                print(f"   ✅ Hash disponível: {existing_payment.gateway_transaction_hash}")
                
                # Testar consulta com hash existente
                api_status = payment_gateway.get_payment_status(
                    existing_payment.gateway_transaction_id,
                    existing_payment.gateway_transaction_hash
                )
                
                if api_status:
                    print(f"   ✅ Consulta funcionou: {api_status}")
                else:
                    print("   ❌ Consulta falhou")
            else:
                print("   ❌ Hash não disponível")
        else:
            print("   ❌ Nenhuma transação existente encontrada")

if __name__ == '__main__':
    test_paradise_hash_fix()
