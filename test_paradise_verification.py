#!/usr/bin/env python3
"""
Teste de Verificação Paradise
=============================

Testa o problema de verificação de pagamento no Paradise.
"""

import os
import sys
from datetime import datetime

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


def test_paradise_verification():
    """Testa verificação de pagamento Paradise"""
    
    with app.app_context():
        # Buscar último pagamento Paradise pendente
        payment = Payment.query.filter_by(
            gateway_type='paradise',
            status='pending'
        ).order_by(Payment.id.desc()).first()
        
        if not payment:
            print("❌ Nenhum pagamento Paradise pendente encontrado")
            return
        
        print("=" * 80)
        print("TESTE: VERIFICAÇÃO DE PAGAMENTO PARADISE")
        print("=" * 80)
        
        print(f"\n📊 DADOS DO PAGAMENTO:")
        print(f"   Payment ID: {payment.payment_id}")
        print(f"   Status: {payment.status}")
        print(f"   Gateway Transaction ID: {payment.gateway_transaction_id}")
        print(f"   Gateway Transaction Hash: {payment.gateway_transaction_hash}")
        print(f"   Amount: R$ {payment.amount:.2f}")
        print(f"   Created At: {payment.created_at}")
        
        # Buscar gateway
        bot = payment.bot
        gateway = Gateway.query.filter_by(
            user_id=bot.user_id,
            gateway_type='paradise',
            is_verified=True
        ).first()
        
        if not gateway:
            print("\n❌ Gateway não encontrado")
            return
        
        print(f"\n📦 DADOS DO GATEWAY:")
        print(f"   API Key: {gateway.api_key[:20]}...")
        print(f"   Product Hash: {gateway.product_hash}")
        print(f"   Store ID: {gateway.store_id}")
        
        # Criar instância do gateway
        credentials = {
            'api_key': gateway.api_key,
            'product_hash': gateway.product_hash,
            'offer_hash': gateway.offer_hash,
            'store_id': gateway.store_id,
            'split_percentage': gateway.split_percentage or 2.0
        }
        
        payment_gateway = GatewayFactory.create_gateway(
            gateway_type='paradise',
            credentials=credentials
        )
        
        if not payment_gateway:
            print("\n❌ Erro ao criar gateway")
            return
        
        print(f"\n🔍 CONSULTANDO STATUS NA API PARADISE...")
        print(f"   Transaction ID: {payment.gateway_transaction_id}")
        print(f"   Transaction Hash: {payment.gateway_transaction_hash}")
        
        # Teste 1: Com transaction_hash
        if payment.gateway_transaction_hash:
            print(f"\n📤 TESTE 1: Com transaction_hash")
            api_status = payment_gateway.get_payment_status(
                payment.gateway_transaction_id,
                payment.gateway_transaction_hash
            )
            print(f"   Resultado: {api_status}")
        
        # Teste 2: Sem transaction_hash (só ID)
        print(f"\n📤 TESTE 2: Sem transaction_hash (só ID)")
        api_status = payment_gateway.get_payment_status(
            payment.gateway_transaction_id,
            None
        )
        print(f"   Resultado: {api_status}")
        
        # Teste 3: Diretamente com transaction_id
        print(f"\n📤 TESTE 3: Usando transaction_id como hash")
        api_status = payment_gateway.get_payment_status(
            payment.gateway_transaction_id,
            payment.gateway_transaction_id  # Usar ID como hash
        )
        print(f"   Resultado: {api_status}")
        
        print("\n" + "=" * 80)
        print("TESTE CONCLUÍDO!")
        print("=" * 80)


if __name__ == '__main__':
    test_paradise_verification()

