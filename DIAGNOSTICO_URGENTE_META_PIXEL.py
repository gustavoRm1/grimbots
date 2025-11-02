#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚨 DIAGNÓSTICO URGENTE: Meta Pixel Purchase não está chegando no Gerenciador
Verifica TODOS os pontos críticos do fluxo
"""

import os
import sys
from datetime import datetime, timedelta

venv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'venv')
if os.path.exists(venv_path):
    activate_script = os.path.join(venv_path, 'bin', 'activate_this.py')
    if os.path.exists(activate_script):
        exec(open(activate_script).read(), {'__file__': activate_script})

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from app import app, db
    from models import Payment, PoolBot, RedirectPool
    from celery_app import celery_app, send_meta_event
    import redis
    import requests
except ImportError as e:
    print("=" * 80)
    print("❌ ERRO: Dependências não instaladas!")
    print("=" * 80)
    print(f"Erro: {e}")
    sys.exit(1)

print("=" * 80)
print("🚨 DIAGNÓSTICO URGENTE: Meta Pixel Purchase")
print("=" * 80)

with app.app_context():
    # ============================================================================
    # 1. VERIFICAR VENDAS HOJE
    # ============================================================================
    hoje_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    
    vendas_hoje = Payment.query.filter(
        Payment.status == 'paid',
        Payment.paid_at >= hoje_inicio
    ).order_by(Payment.paid_at.desc()).all()
    
    vendas_paradise = [v for v in vendas_hoje if v.gateway_type == 'paradise']
    
    print(f"\n📊 VENDAS HOJE (desde {hoje_inicio.strftime('%Y-%m-%d %H:%M')}):")
    print(f"   Total de vendas PAID: {len(vendas_hoje)}")
    print(f"   Vendas Paradise: {len(vendas_paradise)}")
    
    # ============================================================================
    # 2. VERIFICAR STATUS META PIXEL
    # ============================================================================
    print("\n" + "=" * 80)
    print("📊 STATUS META PIXEL DAS VENDAS:")
    print("=" * 80)
    
    com_meta_enviado = [v for v in vendas_hoje if v.meta_purchase_sent]
    sem_meta_enviado = [v for v in vendas_hoje if not v.meta_purchase_sent]
    
    print(f"\n   ✅ Com Meta Pixel enviado: {len(com_meta_enviado)}")
    print(f"   ❌ SEM Meta Pixel enviado: {len(sem_meta_enviado)}")
    
    if sem_meta_enviado:
        print(f"\n⚠️ {len(sem_meta_enviado)} VENDAS SEM META PIXEL ENVIADO!")
        print("\n   Primeiras 10 vendas sem Meta Pixel:")
        for v in sem_meta_enviado[:10]:
            pool_bot = PoolBot.query.filter_by(bot_id=v.bot_id).first()
            pool = pool_bot.pool if pool_bot else None
            
            print(f"\n   Payment: {v.payment_id}")
            print(f"      Valor: R$ {v.amount:.2f}")
            print(f"      Pago em: {v.paid_at.strftime('%Y-%m-%d %H:%M:%S') if v.paid_at else 'N/A'}")
            print(f"      Bot: {v.bot.name if v.bot else 'N/A'}")
            
            if not pool_bot:
                print(f"      ❌ PROBLEMA: Bot não associado a pool!")
            elif not pool:
                print(f"      ❌ PROBLEMA: Pool não encontrado!")
            elif not pool.meta_tracking_enabled:
                print(f"      ❌ PROBLEMA: Meta tracking DESABILITADO")
            elif not pool.meta_pixel_id:
                print(f"      ❌ PROBLEMA: Pixel ID não configurado")
            elif not pool.meta_access_token:
                print(f"      ❌ PROBLEMA: Access Token não configurado")
            elif not pool.meta_events_purchase:
                print(f"      ❌ PROBLEMA: Purchase Event DESABILITADO")
            else:
                print(f"      ⚠️ CONFIGURAÇÃO OK - Por que não foi enviado?")
    
    # ============================================================================
    # 3. VERIFICAR VENDAS COM META ENVIADO MAS NÃO CHEGOU
    # ============================================================================
    print("\n" + "=" * 80)
    print("🔍 VENDAS COM META ENVIADO (mas não chegou no Gerenciador):")
    print("=" * 80)
    
    if com_meta_enviado:
        print(f"\n   {len(com_meta_enviado)} vendas marcadas como enviadas")
        
        # Verificar uma venda específica
        v = com_meta_enviado[0]
        pool_bot = PoolBot.query.filter_by(bot_id=v.bot_id).first()
        pool = pool_bot.pool if pool_bot else None
        
        if pool:
            print(f"\n   📋 Exemplo: {v.payment_id}")
            print(f"      Meta Event ID: {v.meta_event_id}")
            print(f"      Pixel ID: {pool.meta_pixel_id}")
            print(f"      Enviado em: {v.meta_purchase_sent_at.strftime('%Y-%m-%d %H:%M:%S') if v.meta_purchase_sent_at else 'N/A'}")
            
            # Verificar se token está válido
            from utils.encryption import decrypt
            try:
                access_token = decrypt(pool.meta_access_token)
                
                # Validar token
                url = f"https://graph.facebook.com/v18.0/debug_token"
                params = {
                    'input_token': access_token,
                    'access_token': access_token
                }
                
                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    token_data = data.get('data', {})
                    is_valid = token_data.get('is_valid', False)
                    
                    if is_valid:
                        print(f"      ✅ Access Token: VÁLIDO")
                    else:
                        print(f"      ❌ Access Token: INVÁLIDO!")
                        print(f"         Erro: {token_data.get('error', 'Unknown')}")
                else:
                    print(f"      ⚠️ Erro ao validar token: HTTP {response.status_code}")
            except Exception as e:
                print(f"      ❌ Erro ao descriptografar/validar token: {e}")
    
    # ============================================================================
    # 4. VERIFICAR CELERY
    # ============================================================================
    print("\n" + "=" * 80)
    print("🔍 STATUS DO CELERY:")
    print("=" * 80)
    
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        r.ping()
        print("   ✅ Redis: ONLINE")
        
        # Verificar fila
        queue_length = r.llen('celery') if r.exists('celery') else 0
        print(f"   📊 Tasks na fila: {queue_length}")
    except Exception as e:
        print(f"   ❌ Redis: OFFLINE - {e}")
    
    try:
        inspect = celery_app.control.inspect()
        active = inspect.active()
        if active:
            print("   ✅ Celery Worker: ATIVO")
            for worker, tasks in active.items():
                meta_tasks = [t for t in tasks if 'meta' in t.get('name', '').lower()]
                print(f"      Tasks Meta ativas: {len(meta_tasks)}")
        else:
            print("   ❌ Celery Worker: NÃO ENCONTRADO")
    except Exception as e:
        print(f"   ⚠️ Erro ao verificar Celery: {e}")
    
    # ============================================================================
    # 5. RESUMO E AÇÕES
    # ============================================================================
    print("\n" + "=" * 80)
    print("📋 RESUMO:")
    print("=" * 80)
    
    print(f"\n   Total vendas hoje: {len(vendas_hoje)}")
    print(f"   Com Meta enviado: {len(com_meta_enviado)}")
    print(f"   SEM Meta enviado: {len(sem_meta_enviado)}")
    
    if len(sem_meta_enviado) > 0:
        print("\n   ❌ PROBLEMA IDENTIFICADO: Vendas não estão sendo enviadas!")
        print("\n   💡 PRÓXIMOS PASSOS:")
        print("      1. Verificar logs do app.py para 'Purchase enfileirado'")
        print("      2. Verificar logs do Celery em /var/log/celery/")
        print("      3. Verificar se pool tem configuração correta")
        print("      4. Reenviar vendas não enviadas")
    
    print("\n" + "=" * 80)

