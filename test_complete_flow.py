#!/usr/bin/env python3
"""
Teste COMPLETO do fluxo de pagamento Paradise
Simula o clique em "Verificar Pagamento"
"""

import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Payment, Gateway, Bot as BotModel
from gateway_factory import GatewayFactory
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def simulate_verify_payment():
    """Simula o clique em 'Verificar Pagamento'"""
    
    with app.app_context():
        # Pegar último pagamento Paradise pendente
        payment = Payment.query.filter_by(
            gateway_type='paradise',
            status='pending'
        ).order_by(Payment.id.desc()).first()
        
        if not payment:
            print("❌ Nenhum pagamento pendente encontrado")
            return
        
        print("=" * 80)
        print("SIMULAÇÃO: CLIQUE EM 'VERIFICAR PAGAMENTO'")
        print("=" * 80)
        
        print(f"\n📊 ANTES DA VERIFICAÇÃO:")
        print(f"   Payment ID: {payment.payment_id}")
        print(f"   Status: {payment.status}")
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
            print("❌ Gateway não encontrado")
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
        
        print(f"\n🔍 CONSULTANDO API PARADISE...")
        api_status = payment_gateway.get_payment_status(payment.gateway_transaction_id)
        
        print(f"\n📋 RESPOSTA DA API:")
        if api_status:
            print(f"   Status: {api_status.get('status')}")
            print(f"   Transaction ID: {api_status.get('gateway_transaction_id')}")
            print(f"   Amount: R$ {api_status.get('amount', 0):.2f}")
        else:
            print("   ❌ None")
            return
        
        # Simular atualização do banco (como no bot_manager.py)
        if api_status.get('status') == 'paid':
            print(f"\n✅ PAGAMENTO CONFIRMADO! Atualizando banco...")
            
            payment.status = 'paid'
            payment.paid_at = datetime.now()
            
            # Atualizar estatísticas
            payment.bot.total_sales += 1
            payment.bot.total_revenue += payment.amount
            payment.bot.owner.total_sales += 1
            payment.bot.owner.total_revenue += payment.amount
            
            db.session.commit()
            
            print(f"💾 Banco atualizado!")
        else:
            print(f"\n⏳ Status ainda é: {api_status.get('status')}")
        
        # Recarregar do banco para confirmar
        db.session.refresh(payment)
        
        print(f"\n📊 DEPOIS DA VERIFICAÇÃO:")
        print(f"   Payment ID: {payment.payment_id}")
        print(f"   Status: {payment.status}")
        print(f"   Paid At: {payment.paid_at}")
        print(f"   Bot Total Sales: {payment.bot.total_sales}")
        print(f"   Bot Total Revenue: R$ {payment.bot.total_revenue:.2f}")
        
        print("\n" + "=" * 80)
        if payment.status == 'paid':
            print("✅ SUCESSO! Pagamento foi identificado e confirmado!")
        else:
            print("❌ FALHA! Pagamento ainda está pendente")
        print("=" * 80)

if __name__ == '__main__':
    simulate_verify_payment()

