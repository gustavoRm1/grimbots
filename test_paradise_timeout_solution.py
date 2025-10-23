#!/usr/bin/env python3
"""
TESTE DA SOLUÇÃO CRÍTICA - Paradise Timeout
===========================================
Testa se o timeout maior resolve o problema
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

def test_paradise_timeout_solution():
    """Testa a solução de timeout do Paradise"""
    
    with app.app_context():
        print("=" * 80)
        print("TESTE DA SOLUÇÃO CRÍTICA - PARADISE TIMEOUT")
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
            description="Teste Timeout Solution",
            payment_id=999997,
            customer_data={
                'name': 'Teste Timeout',
                'email': 'teste@timeout.com',
                'phone': '11999999999',
                'document': '12345678901'
            }
        )
        
        if not test_result:
            print("❌ Falha ao criar transação de teste")
            return
        
        transaction_id = test_result.get('transaction_id')
        print(f"✅ Transação criada: {transaction_id}")
        
        # Testar consulta com timeout maior
        print(f"\n🔍 TESTANDO CONSULTA COM TIMEOUT MAIOR:")
        
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
        
        # Testar consulta direta com timeout maior
        print(f"\n🔍 TESTANDO CONSULTA DIRETA COM TIMEOUT MAIOR:")
        
        check_url = f"https://multi.paradisepags.com/api/v1/check_status.php?hash={transaction_id}"
        headers = {
            'X-API-Key': gateway.api_key,
            'Accept': 'application/json'
        }
        
        try:
            print(f"   URL: {check_url}")
            print(f"   Timeout: 30 segundos")
            
            response = requests.get(check_url, headers=headers, timeout=30)
            
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get('payment_status') != 'not_found':
                    print("   ✅ CONSULTA FUNCIONANDO COM TIMEOUT MAIOR!")
                else:
                    print("   ❌ AINDA RETORNA NOT_FOUND")
                    
        except Exception as e:
            print(f"   ❌ Erro na consulta: {e}")

if __name__ == '__main__':
    test_paradise_timeout_solution()
