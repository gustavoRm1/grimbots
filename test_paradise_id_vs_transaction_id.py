#!/usr/bin/env python3
"""
TESTE CRÍTICO - PARADISE ID vs TRANSACTION_ID
=============================================
Testa se devemos usar 'id' ou 'transaction_id' para consulta
"""

import sys
import os
import requests
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

def test_paradise_id_vs_transaction_id():
    """Testa se devemos usar 'id' ou 'transaction_id' para consulta"""
    
    with app.app_context():
        print("=" * 80)
        print("TESTE CRÍTICO - PARADISE ID vs TRANSACTION_ID")
        print("=" * 80)
        
        # Pegar último pagamento Paradise
        payment = Payment.query.filter_by(gateway_type='paradise').order_by(Payment.id.desc()).first()
        
        if not payment:
            print("❌ Nenhum pagamento Paradise encontrado no banco")
            return
        
        print(f"\n📊 PAGAMENTO NO BANCO:")
        print(f"   Payment ID: {payment.payment_id}")
        print(f"   Transaction ID: {payment.gateway_transaction_id}")
        print(f"   Amount: R$ {payment.amount:.2f}")
        print(f"   Created: {payment.created_at}")
        
        # Buscar gateway
        bot = payment.bot
        gateway = Gateway.query.filter_by(
            user_id=bot.user_id,
            gateway_type='paradise',
            is_verified=True
        ).first()
        
        if not gateway:
            print("\n❌ Gateway Paradise não encontrado")
            return
        
        # Criar instância do gateway
        credentials = {
            'api_key': gateway.api_key,
            'product_hash': gateway.product_hash,
            'offer_hash': gateway.offer_hash,
            'store_id': gateway.store_id,
            'split_percentage': gateway.split_percentage or 4.0
        }
        
        pg = GatewayFactory.create_gateway('paradise', credentials)
        
        if not pg:
            print("❌ Não foi possível criar gateway")
            return
        
        print(f"\n🔍 TESTANDO AMBOS OS CAMPOS:")
        
        # TESTE 1: Usar transaction_id (atual)
        print(f"\n1️⃣ TESTE COM TRANSACTION_ID:")
        print(f"   URL: {pg.check_status_url}?hash={payment.gateway_transaction_id}")
        
        try:
            response = requests.get(
                f"{pg.check_status_url}?hash={payment.gateway_transaction_id}",
                headers={'X-API-Key': gateway.api_key},
                timeout=30
            )
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text}")
        except Exception as e:
            print(f"   ❌ Erro: {e}")
        
        # TESTE 2: Usar id (campo de referência)
        print(f"\n2️⃣ TESTE COM ID (REFERÊNCIA):")
        # Extrair id da referência (BOT-999997)
        reference_id = payment.payment_id.replace('BOT', '').replace('_', '')
        print(f"   URL: {pg.check_status_url}?hash={reference_id}")
        
        try:
            response = requests.get(
                f"{pg.check_status_url}?hash={reference_id}",
                headers={'X-API-Key': gateway.api_key},
                timeout=30
            )
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text}")
        except Exception as e:
            print(f"   ❌ Erro: {e}")
        
        # TESTE 3: Usar payment_id completo
        print(f"\n3️⃣ TESTE COM PAYMENT_ID COMPLETO:")
        print(f"   URL: {pg.check_status_url}?hash={payment.payment_id}")
        
        try:
            response = requests.get(
                f"{pg.check_status_url}?hash={payment.payment_id}",
                headers={'X-API-Key': gateway.api_key},
                timeout=30
            )
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text}")
        except Exception as e:
            print(f"   ❌ Erro: {e}")
        
        print(f"\n" + "=" * 80)
        print("TESTE FINALIZADO")
        print("=" * 80)

if __name__ == '__main__':
    test_paradise_id_vs_transaction_id()
