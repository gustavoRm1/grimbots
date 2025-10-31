#!/usr/bin/env python3
"""
🔍 DIAGNÓSTICO: Meta Pixel Purchase Events
Verifica por que eventos Purchase não estão sendo enviados para Meta
"""

import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Payment, PoolBot, Pool
import subprocess

with app.app_context():
    print("=" * 80)
    print("🔍 DIAGNÓSTICO: Meta Pixel Purchase Events")
    print("=" * 80)
    
    # 1. Verificar pagamentos PAID de hoje sem Meta Purchase enviado
    hoje = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    pagamentos_paid_hoje = Payment.query.filter(
        Payment.status == 'paid',
        Payment.paid_at >= hoje,
        Payment.gateway_type == 'pushynpay'
    ).all()
    
    print(f"\n1️⃣ PAGAMENTOS PAID HOJE (PushynPay): {len(pagamentos_paid_hoje)}")
    
    sem_meta = []
    com_meta = []
    
    for p in pagamentos_paid_hoje:
        if not p.meta_purchase_sent:
            sem_meta.append(p)
        else:
            com_meta.append(p)
    
    print(f"   ❌ SEM Meta Purchase enviado: {len(sem_meta)}")
    print(f"   ✅ COM Meta Purchase enviado: {len(com_meta)}")
    
    if sem_meta:
        print(f"\n   📋 Pagamentos SEM Meta Purchase:")
        for p in sem_meta[:10]:  # Mostrar até 10
            pool_bot = PoolBot.query.filter_by(bot_id=p.bot_id).first()
            pool_name = pool_bot.pool.name if pool_bot and pool_bot.pool else "N/A"
            print(f"      - Payment {p.id} ({p.payment_id}) | R$ {p.amount:.2f} | Pool: {pool_name} | Paid: {p.paid_at}")
    
    # 2. Verificar se pagamentos têm pool configurado
    print(f"\n2️⃣ VERIFICAÇÃO DE POOLS:")
    for p in sem_meta[:5]:  # Verificar primeiros 5
        pool_bot = PoolBot.query.filter_by(bot_id=p.bot_id).first()
        if not pool_bot:
            print(f"   ❌ Payment {p.id}: Bot {p.bot_id} NÃO está em nenhum pool!")
            continue
        
        pool = pool_bot.pool
        print(f"   Payment {p.id}:")
        print(f"      Pool: {pool.name} (ID: {pool.id})")
        print(f"      Tracking habilitado: {pool.meta_tracking_enabled}")
        print(f"      Purchase habilitado: {pool.meta_events_purchase}")
        print(f"      Pixel ID: {pool.meta_pixel_id is not None}")
        print(f"      Access Token: {pool.meta_access_token is not None}")
        
        if not pool.meta_tracking_enabled:
            print(f"      ⚠️ PROBLEMA: Tracking desabilitado!")
        if not pool.meta_events_purchase:
            print(f"      ⚠️ PROBLEMA: Evento Purchase desabilitado!")
        if not pool.meta_pixel_id:
            print(f"      ⚠️ PROBLEMA: Pixel ID não configurado!")
        if not pool.meta_access_token:
            print(f"      ⚠️ PROBLEMA: Access Token não configurado!")
    
    # 3. Verificar Celery
    print(f"\n3️⃣ STATUS DO CELERY:")
    try:
        result = subprocess.run(['pgrep', '-f', 'celery.*worker'], 
                              capture_output=True, text=True)
        if result.returncode == 0:
            pids = result.stdout.strip().split('\n')
            print(f"   ✅ Celery worker rodando (PIDs: {', '.join(pids)})")
        else:
            print(f"   ❌ Celery worker NÃO está rodando!")
            print(f"   🔧 Iniciar com: celery -A celery_app worker --loglevel=info")
    except Exception as e:
        print(f"   ⚠️ Erro ao verificar Celery: {e}")
    
    # 4. Verificar Redis
    print(f"\n4️⃣ STATUS DO REDIS:")
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        print(f"   ✅ Redis está rodando")
        
        # Verificar tasks pendentes
        try:
            pending_tasks = r.llen('celery')
            print(f"   📋 Tasks pendentes no Redis: {pending_tasks}")
        except:
            pass
    except ImportError:
        print(f"   ⚠️ Redis não instalado (pip install redis)")
    except Exception as e:
        print(f"   ❌ Redis não está rodando: {e}")
        print(f"   🔧 Iniciar com: sudo systemctl start redis")
    
    # 5. Verificar logs recentes
    print(f"\n5️⃣ RECOMENDAÇÕES:")
    if sem_meta:
        print(f"   ⚠️ {len(sem_meta)} pagamento(s) paid sem Meta Purchase enviado")
        print(f"   📋 Verificar logs:")
        print(f"      sudo journalctl -u grimbots -f | grep -E 'Meta Pixel Purchase|Purchase enfileirado|ERRO.*Celery'")
        print(f"      sudo journalctl -u celery -f")
        
        # Verificar se send_meta_pixel_purchase_event foi chamado
        print(f"\n   🔍 Verificar se função foi chamada para estes pagamentos:")
        for p in sem_meta[:5]:
            print(f"      Payment {p.id} ({p.payment_id}): paid_at={p.paid_at}")
    else:
        print(f"   ✅ Todos os pagamentos paid têm meta_purchase_sent=True")
    
    print("\n" + "=" * 80)
    print("✅ Diagnóstico concluído!")
    print("=" * 80)

