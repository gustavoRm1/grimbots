#!/usr/bin/env python3
"""
TESTE DA SOLUÇÃO CRÍTICA - Paradise Retry
=========================================
Testa se o retry resolve o problema do Paradise
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

def test_paradise_retry_solution():
    """Testa a solução de retry do Paradise"""
    
    with app.app_context():
        print("=" * 80)
        print("TESTE DA SOLUÇÃO CRÍTICA - PARADISE RETRY")
        print("=" * 80)
        
        # Buscar gateway
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
        print("\n🔧 CRIANDO TRANSAÇÃO DE TESTE:")
        
        test_result = payment_gateway.generate_pix(
            amount=1.00,  # R$ 1,00
            description="Teste Retry Solution",
            payment_id=999998,
            customer_data={
                'name': 'Teste Retry',
                'email': 'teste@retry.com',
                'phone': '11999999999',
                'document': '12345678901'
            }
        )
        
        if not test_result:
            print("❌ Falha ao criar transação de teste")
            return
        
        transaction_id = test_result.get('transaction_id')
        print(f"✅ Transação criada: {transaction_id}")
        
        # Testar consulta com retry
        print(f"\n🔍 TESTANDO CONSULTA COM RETRY:")
        
        api_status = payment_gateway.get_payment_status(
            transaction_id,
            None  # Sem hash
        )
        
        if api_status:
            print(f"✅ Gateway retornou: {api_status}")
            
            if api_status.get('status') == 'paid':
                print("🎉 PAGAMENTO APROVADO!")
            elif api_status.get('status') == 'pending':
                print("⏳ PAGAMENTO PENDENTE")
            else:
                print(f"📊 Status: {api_status.get('status')}")
        else:
            print("❌ Gateway retornou None")
        
        # Testar com transação existente
        print(f"\n🔍 TESTANDO COM TRANSAÇÃO EXISTENTE:")
        
        existing_payment = Payment.query.filter_by(
            gateway_type='paradise',
            status='pending'
        ).order_by(Payment.id.desc()).first()
        
        if existing_payment:
            print(f"   Payment ID: {existing_payment.payment_id}")
            print(f"   Transaction ID: {existing_payment.gateway_transaction_id}")
            
            api_status = payment_gateway.get_payment_status(
                existing_payment.gateway_transaction_id,
                existing_payment.gateway_transaction_hash
            )
            
            if api_status:
                print(f"   ✅ Consulta funcionou: {api_status}")
            else:
                print("   ❌ Consulta falhou")
        else:
            print("   ❌ Nenhuma transação existente encontrada")

if __name__ == '__main__':
    test_paradise_retry_solution()
