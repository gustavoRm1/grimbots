#!/usr/bin/env python3
"""
TESTE DA CORREÇÃO CRÍTICA - Paradise
====================================
Testa se a correção da URL resolve o problema
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

def test_paradise_fix():
    """Testa a correção da URL do Paradise"""
    
    with app.app_context():
        print("=" * 80)
        print("TESTE DA CORREÇÃO CRÍTICA - PARADISE")
        print("=" * 80)
        
        # Pegar último pagamento Paradise
        payment = Payment.query.filter_by(
            gateway_type='paradise',
            status='pending'
        ).order_by(Payment.id.desc()).first()
        
        if not payment:
            print("❌ Nenhum pagamento Paradise pendente encontrado")
            return
        
        print(f"📊 PAGAMENTO TESTE:")
        print(f"   Payment ID: {payment.payment_id}")
        print(f"   Transaction ID: {payment.gateway_transaction_id}")
        print(f"   Amount: R$ {payment.amount:.2f}")
        
        # Buscar gateway
        bot = payment.bot
        gateway = Gateway.query.filter_by(
            user_id=bot.user_id,
            gateway_type='paradise',
            is_verified=True
        ).first()
        
        if not gateway:
            print("❌ Gateway Paradise não encontrado")
            return
        
        print(f"\n🔑 GATEWAY:")
        print(f"   API Key: {gateway.api_key[:20]}...")
        
        # Testar consulta direta com URL corrigida
        print(f"\n🔍 TESTANDO CONSULTA COM URL CORRIGIDA:")
        
        # URL corrigida (como no paradise.php)
        check_url = f"https://multi.paradisepags.com/api/v1/check_status.php?hash={payment.gateway_transaction_id}"
        headers = {
            'X-API-Key': gateway.api_key,
            'Accept': 'application/json'
        }
        
        print(f"   URL: {check_url}")
        print(f"   Headers: X-API-Key={gateway.api_key[:20]}...")
        
        try:
            response = requests.get(check_url, headers=headers, timeout=10)
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"   JSON: {data}")
                
                if data.get('payment_status') == 'paid':
                    print("\n✅ TRANSAÇÃO APROVADA!")
                    print("   A correção funcionou!")
                elif data.get('payment_status') == 'not_found':
                    print("\n❌ AINDA RETORNA NOT_FOUND")
                    print("   Pode ser que a transação realmente não existe")
                else:
                    print(f"\n📊 STATUS: {data.get('payment_status')}")
                    
        except Exception as e:
            print(f"   ❌ Erro na consulta: {e}")
        
        # Testar com gateway atualizado
        print(f"\n🔧 TESTANDO COM GATEWAY ATUALIZADO:")
        
        credentials = {
            'api_key': gateway.api_key,
            'product_hash': gateway.product_hash,
            'offer_hash': gateway.offer_hash,
            'store_id': gateway.store_id,
            'split_percentage': gateway.split_percentage or 4.0
        }
        
        payment_gateway = GatewayFactory.create_gateway('paradise', credentials)
        
        if payment_gateway:
            print("✅ Gateway criado com sucesso")
            
            # Testar consulta via gateway
            api_status = payment_gateway.get_payment_status(payment.gateway_transaction_id)
            
            if api_status:
                print(f"✅ Gateway retornou: {api_status}")
                
                if api_status.get('status') == 'paid':
                    print("🎉 PAGAMENTO APROVADO VIA GATEWAY!")
                else:
                    print(f"📊 Status via gateway: {api_status.get('status')}")
            else:
                print("❌ Gateway retornou None")
        else:
            print("❌ Falha ao criar gateway")

if __name__ == '__main__':
    test_paradise_fix()
