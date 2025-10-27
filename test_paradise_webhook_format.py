#!/usr/bin/env python3
"""
Teste: Formato do Webhook Paradise
==================================

Testa se o Paradise está enviando webhooks e qual formato usa.
"""

import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Payment, Gateway
from gateway_paradise import ParadisePaymentGateway
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_paradise_webhook_format():
    """Testa diferentes formatos de webhook Paradise"""
    
    print("=" * 80)
    print("TESTE: FORMATO WEBHOOK PARADISE")
    print("=" * 80)
    
    # Criar instância do gateway
    credentials = {
        'api_key': 'sk_dummy',
        'product_hash': 'prod_dummy',
        'offer_hash': 'dummyhash',
        'store_id': '177',
        'split_percentage': 2.0
    }
    
    gateway = ParadisePaymentGateway(credentials)
    
    print("\n📋 TESTANDO DIFERENTES FORMATOS DE WEBHOOK...")
    
    # Formato 1: Paradise pode enviar assim (hipótese)
    webhook_1 = {
        'id': '146771',
        'payment_status': 'approved',
        'amount_paid': 1422
    }
    
    print("\n🔍 Formato 1:")
    print(f"   {webhook_1}")
    result_1 = gateway.process_webhook(webhook_1)
    print(f"   Resultado: {result_1}")
    
    # Formato 2: Paradise pode enviar assim (alternativa)
    webhook_2 = {
        'transaction_id': '146771',
        'status': 'paid',
        'amount': 1422
    }
    
    print("\n🔍 Formato 2:")
    print(f"   {webhook_2}")
    result_2 = gateway.process_webhook(webhook_2)
    print(f"   Resultado: {result_2}")
    
    # Formato 3: Paradise pode enviar assim (alternativa)
    webhook_3 = {
        'hash': 'abc123def456',
        'payment_status': 'approved',
        'amount': 1422
    }
    
    print("\n🔍 Formato 3:")
    print(f"   {webhook_3}")
    result_3 = gateway.process_webhook(webhook_3)
    print(f"   Resultado: {result_3}")
    
    print("\n" + "=" * 80)
    print("✅ TESTE CONCLUÍDO!")
    print("")
    print("📝 CONCLUSÃO:")
    print("   Verifique qual formato Paradise REALMENTE está enviando")
    print("   vendo os logs do webhook em app.py")
    print("")


if __name__ == '__main__':
    test_paradise_webhook_format()

