#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análise: Verificar se grupos Paradise têm paid e pending misturados
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Payment
from sqlalchemy import func

with app.app_context():
    print("=" * 80)
    print("ANÁLISE: Grupos Paradise com paid + pending misturados")
    print("=" * 80)
    
    # Buscar payments Paradise ordenados por gateway_transaction_id
    all_payments = Payment.query.filter(
        Payment.gateway_type == 'paradise',
        Payment.gateway_transaction_id.isnot(None)
    ).order_by(Payment.gateway_transaction_id, Payment.created_at).all()
    
    # Agrupar por gateway_transaction_id
    by_tx_id = {}
    for p in all_payments:
        tx_id = p.gateway_transaction_id
        if tx_id not in by_tx_id:
            by_tx_id[tx_id] = []
        by_tx_id[tx_id].append(p)
    
    # Verificar grupos problemáticos
    mixed_groups = []
    for tx_id, payments in by_tx_id.items():
        if len(payments) > 1:
            statuses = [p.status for p in payments]
            if 'paid' in statuses and 'pending' in statuses:
                mixed_groups.append((tx_id, payments))
    
    print(f"\n📊 Grupos com paid + pending: {len(mixed_groups)}")
    
    for tx_id, payments in mixed_groups[:10]:
        print(f"\n🔍 Transaction ID: {tx_id} | {len(payments)} payments")
        
        for p in payments:
            print(f"   Payment ID: {p.payment_id}")
            print(f"      Hash: {p.gateway_transaction_hash}")
            print(f"      Status: {p.status}")
            print(f"      Valor: R$ {p.amount:.2f}")
            print(f"      Criado: {p.created_at}")
    
    print("\n" + "=" * 80)

