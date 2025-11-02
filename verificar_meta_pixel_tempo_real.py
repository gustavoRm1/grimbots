#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verifica Meta Pixel Purchase para payments Paradise RECENTES (últimas 2 horas)
e verifica se Celery está processando
"""

import os
import sys

venv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'venv')
if os.path.exists(venv_path):
    activate_script = os.path.join(venv_path, 'bin', 'activate_this.py')
    if os.path.exists(activate_script):
        exec(open(activate_script).read(), {'__file__': activate_script})

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app import app, db
    from models import Payment, PoolBot
    from celery_app import celery_app
    import redis
    from datetime import datetime, timedelta
except ImportError as e:
    print("=" * 80)
    print("❌ ERRO: Dependências não instaladas!")
    print("=" * 80)
    print(f"Erro: {e}")
    print("\n💡 SOLUÇÃO:")
    print("   1. Ative o venv: source venv/bin/activate")
    print("   2. Instale dependências: pip install -r requirements.txt")
    print("=" * 80)
    sys.exit(1)

with app.app_context():
    print("=" * 80)
    print("🔍 VERIFICAÇÃO TEMPO REAL: Meta Pixel Purchase - Paradise")
    print("=" * 80)
    
    # Buscar payments Paradise PAID das últimas 2 horas
    agora = datetime.now()
    desde = agora - timedelta(hours=2)
    
    payments = Payment.query.filter(
        Payment.gateway_type == 'paradise',
        Payment.status == 'paid',
        Payment.paid_at >= desde
    ).order_by(Payment.paid_at.desc()).all()
    
    print(f"\n📊 Payments Paradise PAID (últimas 2 horas): {len(payments)}")
    
    # Verificar Celery
    print("\n🔍 STATUS DO CELERY:")
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        r.ping()
        print("   ✅ Redis: ONLINE")
    except Exception as e:
        print(f"   ❌ Redis: OFFLINE - {e}")
        r = None
    
    try:
        inspect = celery_app.control.inspect()
        active = inspect.active()
        if active:
            print("   ✅ Celery Worker: ATIVO")
            for worker, tasks in active.items():
                meta_tasks = [t for t in tasks if 'meta' in t.get('name', '').lower()]
                print(f"   Tasks Meta ativas: {len(meta_tasks)}")
        else:
            print("   ❌ Celery Worker: NÃO ENCONTRADO")
    except Exception as e:
        print(f"   ⚠️ Erro ao verificar Celery: {e}")
    
    # Verificar cada payment
    sem_meta = []
    com_meta = []
    
    for p in payments:
        pool_bot = PoolBot.query.filter_by(bot_id=p.bot_id).first()
        
        if not p.meta_purchase_sent:
            sem_meta.append(p)
        else:
            com_meta.append(p)
    
    print("\n" + "=" * 80)
    print("📋 RESUMO:")
    print("=" * 80)
    print(f"   ✅ Com Meta Pixel enviado: {len(com_meta)}")
    print(f"   ❌ Sem Meta Pixel enviado: {len(sem_meta)}")
    
    if sem_meta:
        print("\n⚠️ PAYMENTS SEM META PIXEL:")
        for p in sem_meta[:5]:
            pool_bot = PoolBot.query.filter_by(bot_id=p.bot_id).first()
            pool = pool_bot.pool if pool_bot else None
            
            print(f"\n   Payment: {p.payment_id}")
            print(f"   Valor: R$ {p.amount:.2f}")
            print(f"   Pago em: {p.paid_at.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Bot: {p.bot.name if p.bot else 'N/A'}")
            
            if not pool_bot:
                print(f"   ❌ PROBLEMA: Bot não associado a nenhum pool!")
            elif not pool:
                print(f"   ❌ PROBLEMA: Pool não encontrado!")
            elif not pool.meta_tracking_enabled:
                print(f"   ❌ PROBLEMA: Meta tracking DESABILITADO no pool")
            elif not pool.meta_pixel_id:
                print(f"   ❌ PROBLEMA: Meta Pixel ID não configurado")
            elif not pool.meta_access_token:
                print(f"   ❌ PROBLEMA: Meta Access Token não configurado")
            elif not pool.meta_events_purchase:
                print(f"   ❌ PROBLEMA: Purchase Event DESABILITADO no pool")
            else:
                print(f"   ⚠️ CONFIGURAÇÃO OK - Meta Pixel deveria ter sido enviado!")
                print(f"   💡 Verificar logs do Celery para este payment")
    
    print("\n" + "=" * 80)
    print("💡 PRÓXIMOS PASSOS:")
    print("=" * 80)
    if sem_meta:
        print("1. Ver logs do Celery para erros:")
        print("   journalctl -u celery -n 100 --no-pager | grep -i 'Meta Event'")
        print("\n2. Verificar se Celery está processando:")
        print("   systemctl status celery")
    else:
        print("✅ Todos os payments recentes têm Meta Pixel enviado!")
        print("💡 Se não aparecer na Meta, verificar:")
        print("   1. Token do Access Token está válido?")
        print("   2. Pixel ID está correto?")
        print("   3. Test Event Code (se houver) está correto?")
    print("=" * 80)

