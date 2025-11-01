#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Teste: Verificar colisões de ID Paradise
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Payment
from sqlalchemy import func

with app.app_context():
    print("=" * 80)
    print("TESTE: Verificar colisões de ID Paradise")
    print("=" * 80)
    
    # Buscar payments com mesmo gateway_transaction_hash
    duplicated_hashes = db.session.query(
        Payment.gateway_transaction_hash,
        func.count(Payment.id).label('count')
    ).filter(
        Payment.gateway_type == 'paradise',
        Payment.gateway_transaction_hash.isnot(None)
    ).group_by(Payment.gateway_transaction_hash).having(
        func.count(Payment.id) > 1
    ).all()
    
    print(f"\n📊 Hashes DUPLICADOS: {len(duplicated_hashes)}")
    
    for hash_val, count in duplicated_hashes[:10]:
        print(f"\n🔍 Hash: {hash_val} - usado {count} vezes")
        
        payments = Payment.query.filter_by(gateway_transaction_hash=hash_val).order_by(Payment.created_at.desc()).all()
        
        for p in payments:
            print(f"   Payment ID: {p.payment_id} | Status: {p.status} | Valor: R$ {p.amount:.2f} | Criado: {p.created_at}")
    
    # Verificar ID 155925 especificamente
    print(f"\n" + "=" * 80)
    print("VERIFICANDO ID #155925:")
    
    payments_155925 = Payment.query.filter_by(gateway_transaction_id='155925').all()
    
    print(f"📊 Payments com transaction_id='155925': {len(payments_155925)}")
    
    for p in payments_155925:
        print(f"   ID: {p.id}")
        print(f"   Payment ID: {p.payment_id}")
        print(f"   Hash: {p.gateway_transaction_hash}")
        print(f"   Status: {p.status}")
        print(f"   Valor: R$ {p.amount:.2f}")
        print(f"   ---")

