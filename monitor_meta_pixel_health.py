#!/usr/bin/env python3
"""
🔍 MONITOR DE SAÚDE: Meta Pixel Purchase Events
Verifica saúde do sistema de tracking Meta Pixel em tempo real
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Payment, PoolBot

with app.app_context():
    print("=" * 80)
    print("🔍 MONITOR DE SAÚDE: Meta Pixel Purchase Events")
    print("=" * 80)
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Última hora
    uma_hora_atras = datetime.now() - timedelta(hours=1)
    
    # Todas as vendas da última hora
    vendas_ultima_hora = Payment.query.filter(
        Payment.status == 'paid',
        Payment.paid_at >= uma_hora_atras
    ).all()
    
    print(f"📊 VENDAS ÚLTIMA HORA: {len(vendas_ultima_hora)}")
    
    sem_meta = [p for p in vendas_ultima_hora if not p.meta_purchase_sent]
    com_meta = [p for p in vendas_ultima_hora if p.meta_purchase_sent]
    
    taxa_sucesso = (len(com_meta) / len(vendas_ultima_hora) * 100) if vendas_ultima_hora else 0
    
    print(f"   ✅ COM Meta Purchase: {len(com_meta)}")
    print(f"   ❌ SEM Meta Purchase: {len(sem_meta)}")
    print(f"   📈 Taxa de sucesso: {taxa_sucesso:.1f}%")
    
    if sem_meta:
        print(f"\n⚠️ ALERTA: {len(sem_meta)} venda(s) sem Meta Purchase na última hora!")
        print("   Execute: python reenviar_meta_purchase.py")
    else:
        print(f"\n✅ SISTEMA SAUDÁVEL: 100% de vendas com Meta Purchase enviado")
    
    # Verificar pools com problemas
    print(f"\n📋 VERIFICAÇÃO DE POOLS:")
    pools_problema = []
    
    from sqlalchemy import distinct
    pool_ids = db.session.query(distinct(PoolBot.pool_id)).all()
    pool_ids = [pid[0] for pid in pool_ids]
    
    from models import RedirectPool
    pools = RedirectPool.query.filter(RedirectPool.id.in_(pool_ids)).all() if pool_ids else []
    
    for pool in pools:
        problemas = []
        if not pool.meta_tracking_enabled:
            problemas.append("Tracking desabilitado")
        if not pool.meta_events_purchase:
            problemas.append("Purchase desabilitado")
        if not pool.meta_pixel_id:
            problemas.append("Pixel ID não configurado")
        if not pool.meta_access_token:
            problemas.append("Access Token não configurado")
        
        if problemas:
            pools_problema.append((pool, problemas))
            print(f"   ⚠️ Pool '{pool.name}' (ID: {pool.id}): {', '.join(problemas)}")
    
    if not pools_problema:
        print(f"   ✅ Todos os pools configurados corretamente")
    
    # Resumo final
    print("\n" + "=" * 80)
    if len(sem_meta) == 0 and len(pools_problema) == 0:
        print("✅ STATUS: SISTEMA 100% OPERACIONAL")
    else:
        print("⚠️ STATUS: ATENÇÃO NECESSÁRIA")
    print("=" * 80)

