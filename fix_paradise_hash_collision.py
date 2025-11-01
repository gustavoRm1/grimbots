#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para identificar e corrigir colisões de gateway_transaction_hash do Paradise
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Payment
from sqlalchemy import func

with app.app_context():
    print("=" * 80)
    print("CORREÇÃO: Colisões de gateway_transaction_hash Paradise")
    print("=" * 80)
    
    # Buscar payments Paradise com mesmo gateway_transaction_hash
    duplicated_hashes = db.session.query(
        Payment.gateway_transaction_hash,
        Payment.gateway_transaction_id,
        func.count(Payment.id).label('count'),
        func.min(Payment.created_at).label('first_created'),
        func.max(Payment.created_at).label('last_created')
    ).filter(
        Payment.gateway_type == 'paradise',
        Payment.gateway_transaction_hash.isnot(None)
    ).group_by(
        Payment.gateway_transaction_hash,
        Payment.gateway_transaction_id
    ).having(
        func.count(Payment.id) > 1
    ).order_by(
        func.count(Payment.id).desc()
    ).all()
    
    print(f"\n📊 Hashes DUPLICADOS: {len(duplicated_hashes)}")
    
    total_affected = 0
    
    for hash_val, tx_id, count, first_created, last_created in duplicated_hashes[:20]:
        print(f"\n🔍 Hash: {hash_val} | TX ID: {tx_id} | Usado {count} vezes")
        print(f"   Primeira ocorrência: {first_created}")
        print(f"   Última ocorrência: {last_created}")
        
        # Buscar TODOS os payments com este hash
        payments = Payment.query.filter_by(
            gateway_transaction_hash=hash_val
        ).order_by(Payment.created_at.asc()).all()
        
        print(f"   📋 Payments ({len(payments)}):")
        
        # ✅ ESTRATÉGIA: Manter APENAS o primeiro payment (o mais antigo)
        # Os outros serão marcados como duplicados com hash único
        
        first_payment = payments[0]
        duplicates = payments[1:]
        
        print(f"      ✅ PRIMEIRO (manter): Payment ID {first_payment.payment_id} | Status: {first_payment.status}")
        
        for dup in duplicates:
            print(f"      ❌ DUPLICADO (corrigir): Payment ID {dup.payment_id} | Status: {dup.status}")
            
            # ✅ Gerar hash único baseado no payment_id
            import time
            unique_hash = f"{dup.payment_id.replace('_', '-')}_{int(time.time())}"
            
            # Atualizar
            dup.gateway_transaction_hash = unique_hash
            total_affected += 1
            
            print(f"         → Hash corrigido: {unique_hash}")
    
    if total_affected > 0:
        print(f"\n📝 Salvando {total_affected} correções no banco...")
        db.session.commit()
        print(f"✅ Correções salvas!")
    else:
        print(f"\n✅ Nenhuma correção necessária")
    
    print("\n" + "=" * 80)
    print("RESUMO:")
    print(f"   Hashes duplicados: {len(duplicated_hashes)}")
    print(f"   Payments corrigidos: {total_affected}")
    print("=" * 80)

