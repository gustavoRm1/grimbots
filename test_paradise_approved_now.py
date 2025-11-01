#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste: Verificar se reconciliação está funcionando para IDs duplicados Paradise
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Payment, Gateway
from gateway_factory import GatewayFactory
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

with app.app_context():
    print("=" * 80)
    print("TESTE: Verificar reconciliação Paradise para ID #155925")
    print("=" * 80)
    
    # Buscar payment pelo ID duplicado
    payment = Payment.query.filter_by(gateway_transaction_id='155925').first()
    
    if payment:
        print(f"\n✅ Payment encontrado:")
        print(f"   ID: {payment.id}")
        print(f"   Payment ID: {payment.payment_id}")
        print(f"   Gateway Hash: {payment.gateway_transaction_hash}")
        print(f"   Gateway Transaction ID: {payment.gateway_transaction_id}")
        print(f"   Status ATUAL: {payment.status}")
        print(f"   Valor: R$ {payment.amount:.2f}")
        print(f"   Criado: {payment.created_at}")
        
        # Buscar gateway
        gateway = Gateway.query.filter_by(
            user_id=payment.bot.user_id,
            gateway_type='paradise',
            is_active=True,
            is_verified=True
        ).first()
        
        if gateway:
            creds = {
                'api_key': gateway.api_key,
                'product_hash': gateway.product_hash,
                'offer_hash': gateway.offer_hash,
                'store_id': gateway.store_id,
                'split_percentage': gateway.split_percentage or 2.0
            }
            g = GatewayFactory.create_gateway('paradise', creds)
            
            if g:
                hash_or_id = payment.gateway_transaction_hash or payment.gateway_transaction_id
                print(f"\n🔍 Consultando Paradise com: {hash_or_id}")
                
                result = g.get_payment_status(str(hash_or_id))
                
                if result:
                    print(f"✅ Paradise retornou:")
                    print(f"   Status: {result.get('status')}")
                    print(f"   Transaction ID: {result.get('gateway_transaction_id')}")
                    print(f"   Amount: R$ {result.get('amount', 0):.2f if result.get('amount') else 0}")
                    
                    if result.get('status') == 'paid':
                        print(f"\n✅ PAGAMENTO ESTÁ PAID NA PARADISE!")
                        print(f"   Status no sistema: {payment.status}")
                        print(f"   RECONCILIADOR DEVERIA ter atualizado!")
                    else:
                        print(f"\n⚠️ Pagamento ainda {result.get('status')} na Paradise")
                else:
                    print(f"❌ Paradise não retornou resultado - transação não encontrada")
            else:
                print("❌ Erro ao criar gateway Paradise")
        else:
            print("❌ Gateway Paradise não encontrado")
    else:
        print("❌ Payment não encontrado")
    
    print("\n" + "=" * 80)
    
    # Verificar se reconcilia
    print("\n🔧 VERIFICANDO SE RECONCILIADOR EXECUTOU:")
    
    # Buscar payments recentes do mesmo hash
    payments_same_hash = Payment.query.filter_by(
        gateway_transaction_hash='BOT4-1761957211-d485e326'
    ).order_by(Payment.created_at.desc()).all()
    
    print(f"📊 Payments com mesmo hash: {len(payments_same_hash)}")
    
    for p in payments_same_hash:
        print(f"   Payment ID: {p.payment_id} | Status: {p.status} | Criado: {p.created_at}")

