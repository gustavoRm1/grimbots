#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verifica se novos PIX Paradise estão sendo gerados corretamente
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Payment

with app.app_context():
    from datetime import datetime, timedelta
    
    # Buscar payments Paradise das últimas 2 horas
    desde = datetime.now() - timedelta(hours=2)
    
    payments = Payment.query.filter(
        Payment.gateway_type == 'paradise',
        Payment.created_at >= desde
    ).order_by(Payment.created_at.desc()).all()
    
    print("=" * 80)
    print(f"📊 PAYMENTS PARADISE (últimas 2h): {len(payments)}")
    print("=" * 80)
    
    for p in payments:
        print(f"\nPayment ID: {p.payment_id}")
        print(f"  ID DB: {p.id}")
        print(f"  Valor: R$ {p.amount:.2f}")
        print(f"  Status: {p.status}")
        print(f"  Gateway Transaction ID: {p.gateway_transaction_id}")
        print(f"  Gateway Transaction Hash: {p.gateway_transaction_hash}")
        print(f"  Customer User ID: {p.customer_user_id}")
        print(f"  Criado: {p.created_at}")
        print(f"  Produto: {p.product_name}")
    
    # Buscar especificamente o #156196
    print("\n" + "=" * 80)
    print("🔍 BUSCANDO PAYMENT #156196:")
    print("=" * 80)
    
    # Tentar buscar por transaction_id
    payment_156196 = Payment.query.filter(
        (Payment.gateway_transaction_id == '156196') |
        (Payment.gateway_transaction_id.like('%156196%')) |
        (Payment.gateway_transaction_hash.like('%156196%'))
    ).first()
    
    if payment_156196:
        print(f"✅ Encontrado: {payment_156196.payment_id}")
        print(f"  Transaction ID: {payment_156196.gateway_transaction_id}")
        print(f"  Transaction Hash: {payment_156196.gateway_transaction_hash}")
        print(f"  Status: {payment_156196.status}")
    else:
        print("❌ Payment #156196 NÃO encontrado no banco")
        print("   Isso significa que foi criado apenas na Paradise, não no nosso sistema")
    
    print("\n" + "=" * 80)

