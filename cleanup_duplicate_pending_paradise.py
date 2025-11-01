#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para marcar como failed os payments pending duplicados após paid
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Payment
from sqlalchemy import func

with app.app_context():
    print("=" * 80)
    print("LIMPEZA: Marcar duplicados pending como failed")
    print("=" * 80)
    
    # Buscar todos os payments Paradise
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
    
    # Encontrar grupos problemáticos
    to_mark_failed = []
    for tx_id, payments in by_tx_id.items():
        if len(payments) > 1:
            statuses = [p.status for p in payments]
            if 'paid' in statuses and 'pending' in statuses:
                # Ordenar por data de criação
                payments_sorted = sorted(payments, key=lambda x: x.created_at)
                
                # Encontrar o primeiro paid
                first_paid_idx = None
                for idx, p in enumerate(payments_sorted):
                    if p.status == 'paid':
                        first_paid_idx = idx
                        break
                
                if first_paid_idx is not None:
                    # Todos os pending DEPOIS do first paid são duplicados
                    for p in payments_sorted[first_paid_idx + 1:]:
                        if p.status == 'pending':
                            to_mark_failed.append(p)
    
    print(f"\n📊 Payments a marcar como failed: {len(to_mark_failed)}")
    
    for p in to_mark_failed[:20]:
        print(f"   Payment ID: {p.payment_id}")
        print(f"      Hash: {p.gateway_transaction_hash}")
        print(f"      Status atual: {p.status}")
        print(f"      Valor: R$ {p.amount:.2f}")
        print(f"      Criado: {p.created_at}")
        print()
    
    if to_mark_failed:
        confirm = input("\n❓ Marcar como failed? (sim/não): ")
        
        if confirm.lower() == 'sim':
            for p in to_mark_failed:
                p.status = 'failed'
            
            db.session.commit()
            print(f"✅ {len(to_mark_failed)} payments marcados como failed!")
        else:
            print("❌ Cancelado")
    else:
        print("\n✅ Nenhum payment para corrigir")
    
    print("\n" + "=" * 80)

