#!/usr/bin/env python3
"""
TESTE COM TRANSAÇÃO RECENTE - Paradise
=====================================
Testa com uma transação criada há menos de 30 minutos
"""

import sys
import os
from datetime import datetime, timedelta

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

def test_recent_transaction():
    """Testa com transação recente"""
    
    with app.app_context():
        print("=" * 80)
        print("TESTE COM TRANSAÇÃO RECENTE - PARADISE")
        print("=" * 80)
        
        # Buscar transação criada nos últimos 30 minutos
        cutoff_time = datetime.now() - timedelta(minutes=30)
        
        recent_payment = Payment.query.filter(
            Payment.gateway_type == 'paradise',
            Payment.status == 'pending',
            Payment.created_at >= cutoff_time
        ).order_by(Payment.id.desc()).first()
        
        if not recent_payment:
            print("❌ Nenhuma transação recente encontrada")
            print("   Criando uma nova transação para teste...")
            
            # Buscar gateway
            gateway = Gateway.query.filter_by(
                gateway_type='paradise',
                is_verified=True
            ).first()
            
            if not gateway:
                print("❌ Gateway Paradise não encontrado")
                return
            
            # Criar instância do gateway
            credentials = {
                'api_key': gateway.api_key,
                'product_hash': gateway.product_hash,
                'offer_hash': gateway.offer_hash,
                'store_id': gateway.store_id,
                'split_percentage': gateway.split_percentage or 4.0
            }
            
            payment_gateway = GatewayFactory.create_gateway('paradise', credentials)
            
            if not payment_gateway:
                print("❌ Não foi possível criar gateway")
                return
            
            # Gerar PIX de teste
            print("🔧 Gerando PIX de teste...")
            pix_result = payment_gateway.generate_pix(
                amount=1.00,  # R$ 1,00 para teste
                description="Teste Paradise",
                payment_id=999999,  # ID fictício
                customer_data={
                    'name': 'Teste',
                    'email': 'teste@teste.com',
                    'phone': '11999999999',
                    'document': '12345678901'
                }
            )
            
            if pix_result:
                print("✅ PIX gerado com sucesso!")
                print(f"   Transaction ID: {pix_result.get('transaction_id')}")
                print(f"   PIX Code: {pix_result.get('pix_code')[:50]}...")
                
                # Testar consulta imediatamente
                transaction_id = pix_result.get('transaction_id')
                print(f"\n🔍 Testando consulta imediata...")
                
                # Aguardar 5 segundos
                import time
                time.sleep(5)
                
                api_status = payment_gateway.get_payment_status(transaction_id)
                
                if api_status:
                    print(f"✅ API retornou: {api_status}")
                else:
                    print("❌ API retornou None")
                
            else:
                print("❌ Falha ao gerar PIX")
                return
        
        else:
            print(f"✅ Transação recente encontrada:")
            print(f"   Payment ID: {recent_payment.payment_id}")
            print(f"   Transaction ID: {recent_payment.gateway_transaction_id}")
            print(f"   Amount: R$ {recent_payment.amount:.2f}")
            print(f"   Created: {recent_payment.created_at}")
            
            # Testar consulta
            bot = recent_payment.bot
            gateway = Gateway.query.filter_by(
                user_id=bot.user_id,
                gateway_type='paradise',
                is_verified=True
            ).first()
            
            if gateway:
                credentials = {
                    'api_key': gateway.api_key,
                    'product_hash': gateway.product_hash,
                    'offer_hash': gateway.offer_hash,
                    'store_id': gateway.store_id,
                    'split_percentage': gateway.split_percentage or 4.0
                }
                
                payment_gateway = GatewayFactory.create_gateway('paradise', credentials)
                
                if payment_gateway:
                    print(f"\n🔍 Testando consulta...")
                    api_status = payment_gateway.get_payment_status(recent_payment.gateway_transaction_id)
                    
                    if api_status:
                        print(f"✅ API retornou: {api_status}")
                    else:
                        print("❌ API retornou None")

if __name__ == '__main__':
    test_recent_transaction()
