#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔧 CORREÇÃO: Adicionar transaction_hash para pagamentos Paradise antigos
Corrige pagamentos que não têm gateway_transaction_hash salvo (problema antigo)
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Payment, Gateway
from gateway_factory import GatewayFactory

with app.app_context():
    print("=" * 80)
    print("🔧 CORREÇÃO: Transaction Hash para pagamentos Paradise antigos")
    print("=" * 80)
    
    # Buscar pagamentos Paradise sem hash (problema antigo)
    pagamentos_sem_hash = Payment.query.filter(
        Payment.gateway_type == 'paradise',
        Payment.gateway_transaction_hash == None,
        Payment.gateway_transaction_id != None,
        Payment.status == 'pending'
    ).order_by(Payment.created_at.desc()).limit(50).all()
    
    print(f"\n📊 Pagamentos Paradise SEM hash (pendentes): {len(pagamentos_sem_hash)}")
    
    corrigidos = 0
    erros = 0
    
    for p in pagamentos_sem_hash:
        try:
            print(f"\n🔄 Payment {p.id} ({p.payment_id}):")
            print(f"   Transaction ID: {p.gateway_transaction_id}")
            print(f"   Valor: R$ {p.amount:.2f}")
            
            # ✅ CORREÇÃO: Usar transaction_id como hash (fallback)
            # Como não temos o hash original, vamos usar transaction_id
            # O reconciliador tentará primeiro com hash, depois com transaction_id
            if p.gateway_transaction_id:
                # Para pagamentos antigos, usar transaction_id como hash temporário
                # O ideal seria consultar a API Paradise, mas por ora usar transaction_id
                p.gateway_transaction_hash = str(p.gateway_transaction_id)
                db.session.commit()
                corrigidos += 1
                print(f"   ✅ Hash definido: {p.gateway_transaction_hash}")
            else:
                print(f"   ⚠️ Sem transaction_id - não é possível corrigir")
                erros += 1
                
        except Exception as e:
            print(f"   ❌ Erro: {e}")
            db.session.rollback()
            erros += 1
    
    print("\n" + "=" * 80)
    print(f"📊 RESUMO:")
    print(f"   ✅ Corrigidos: {corrigidos}")
    print(f"   ❌ Erros: {erros}")
    print(f"   📦 Total processado: {len(pagamentos_sem_hash)}")
    
    if corrigidos > 0:
        print(f"\n✅ {corrigidos} pagamento(s) corrigido(s)!")
        print(f"💡 Os pagamentos agora podem ser consultados no reconciliador Paradise")
    
    print("=" * 80)

