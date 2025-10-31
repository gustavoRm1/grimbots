#!/usr/bin/env python3
"""
🔍 DIAGNÓSTICO COMPLETO: Meta Pixel Purchase Events
Análise rigorosa de TODOS os pools e vendas
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Payment, PoolBot

with app.app_context():
    print("=" * 80)
    print("🔍 DIAGNÓSTICO COMPLETO: Meta Pixel Purchase Events")
    print("=" * 80)
    
    # 1. TODAS as vendas de HOJE (qualquer gateway)
    hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    todos_pagamentos_hoje = Payment.query.filter(
        Payment.status == 'paid',
        Payment.paid_at >= hoje
    ).all()
    
    print(f"\n1️⃣ TODAS AS VENDAS HOJE: {len(todos_pagamentos_hoje)}")
    
    sem_meta = []
    com_meta = []
    sem_pool = []
    
    for p in todos_pagamentos_hoje:
        pool_bot = PoolBot.query.filter_by(bot_id=p.bot_id).first()
        if not pool_bot:
            sem_pool.append(p)
            continue
            
        if not p.meta_purchase_sent:
            sem_meta.append(p)
        else:
            com_meta.append(p)
    
    print(f"   ❌ SEM Meta Purchase: {len(sem_meta)}")
    print(f"   ✅ COM Meta Purchase: {len(com_meta)}")
    print(f"   ⚠️ SEM Pool: {len(sem_pool)}")
    
    # 2. Análise por POOL
    print(f"\n2️⃣ ANÁLISE POR POOL:")
    # Buscar pools via PoolBot (todos os pools que têm bots)
    from sqlalchemy import distinct
    pool_ids = db.session.query(distinct(PoolBot.pool_id)).all()
    pool_ids = [pid[0] for pid in pool_ids]
    
    # Importar RedirectPool dinamicamente
    from models import RedirectPool
    pools = RedirectPool.query.filter(RedirectPool.id.in_(pool_ids)).all() if pool_ids else []
    
    for pool in pools:
        # Buscar bots do pool
        pool_bots = [pb.bot_id for pb in PoolBot.query.filter_by(pool_id=pool.id).all()]
        
        # Vendas de hoje deste pool
        vendas_pool = Payment.query.filter(
            Payment.status == 'paid',
            Payment.paid_at >= hoje,
            Payment.bot_id.in_(pool_bots) if pool_bots else False
        ).all()
        
        sem_meta_pool = [p for p in vendas_pool if not p.meta_purchase_sent]
        
        print(f"\n   📊 Pool: {pool.name} (ID: {pool.id})")
        print(f"      Total vendas hoje: {len(vendas_pool)}")
        print(f"      SEM Meta Purchase: {len(sem_meta_pool)}")
        print(f"      ✅ COM Meta Purchase: {len(vendas_pool) - len(sem_meta_pool)}")
        
        # Configuração do pool
        print(f"      Tracking: {pool.meta_tracking_enabled}")
        print(f"      Purchase: {pool.meta_events_purchase}")
        print(f"      Pixel ID: {'✅' if pool.meta_pixel_id else '❌'}")
        print(f"      Access Token: {'✅' if pool.meta_access_token else '❌'}")
        
        if sem_meta_pool:
            print(f"\n      ⚠️ Pagamentos SEM Meta Purchase:")
            for p in sem_meta_pool[:5]:
                print(f"         - Payment {p.id} ({p.payment_id}) | R$ {p.amount:.2f} | Paid: {p.paid_at.strftime('%H:%M:%S')}")
            
            # Verificar por que não foi enviado
            if not pool.meta_tracking_enabled:
                print(f"      ❌ PROBLEMA: Tracking DESABILITADO no pool!")
            if not pool.meta_events_purchase:
                print(f"      ❌ PROBLEMA: Evento Purchase DESABILITADO no pool!")
            if not pool.meta_pixel_id:
                print(f"      ❌ PROBLEMA: Pixel ID NÃO CONFIGURADO!")
            if not pool.meta_access_token:
                print(f"      ❌ PROBLEMA: Access Token NÃO CONFIGURADO!")
    
    # 3. Análise temporal (quando foi pago vs quando deveria ter sido enviado)
    print(f"\n3️⃣ ANÁLISE TEMPORAL:")
    agora = datetime.now()
    
    for p in sem_meta[:10]:
        tempo_desde_pagamento = (agora - p.paid_at).total_seconds() / 3600  # horas
        print(f"   Payment {p.id}: Pago há {tempo_desde_pagamento:.1f}h | {p.paid_at.strftime('%H:%M:%S')}")
    
    # 4. Verificar se função foi chamada (via logs indiretos)
    print(f"\n4️⃣ VERIFICAÇÕES DE LOGS:")
    print(f"   📋 Execute para ver se função foi chamada:")
    print(f"      sudo journalctl -u grimbots --since 'today' | grep -E 'Meta Pixel Purchase disparado|Purchase enfileirado' | tail -20")
    print(f"   📋 Execute para ver erros no Celery:")
    print(f"      sudo journalctl -u celery --since 'today' | grep -E 'FAILED|ERROR|Purchase' | tail -20")
    
    # 5. Resumo crítico
    print(f"\n5️⃣ RESUMO CRÍTICO:")
    print(f"   ⚠️ {len(sem_meta)} venda(s) SEM Meta Purchase de {len(todos_pagamentos_hoje)} total")
    print(f"   📊 Taxa de sucesso: {((len(com_meta) / len(todos_pagamentos_hoje)) * 100) if todos_pagamentos_hoje else 0:.1f}%")
    
    if sem_meta:
        print(f"\n   🔧 AÇÃO IMEDIATA:")
        print(f"      python reenviar_meta_purchase.py")
        print(f"   ⚠️ CRÍTICO: Isso afeta otimização de campanhas Meta Ads!")
    
    print("\n" + "=" * 80)
    print("✅ Diagnóstico completo concluído!")
    print("=" * 80)

