#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnóstico completo: Por que Meta Pixel Purchase não está sendo enviado para Paradise
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import Payment, PoolBot, RedirectPool, Bot

with app.app_context():
    from datetime import datetime, timedelta
    
    print("=" * 80)
    print("🔍 DIAGNÓSTICO META PIXEL PURCHASE - PARADISE")
    print("=" * 80)
    
    # Buscar payments Paradise PAID das últimas 24h
    desde = datetime.now() - timedelta(hours=24)
    
    payments = Payment.query.filter(
        Payment.gateway_type == 'paradise',
        Payment.status == 'paid',
        Payment.paid_at >= desde
    ).order_by(Payment.paid_at.desc()).all()
    
    print(f"\n📊 PAYMENTS PARADISE PAID (últimas 24h): {len(payments)}")
    
    if not payments:
        print("❌ Nenhum payment Paradise paid encontrado nas últimas 24h")
        print("   Verifique se há pagamentos sendo confirmados")
    else:
        for p in payments[:10]:  # Mostrar os 10 mais recentes
            print(f"\n" + "-" * 80)
            print(f"Payment ID: {p.payment_id}")
            print(f"  ID DB: {p.id}")
            print(f"  Bot ID: {p.bot_id}")
            print(f"  Valor: R$ {p.amount:.2f}")
            print(f"  Pago em: {p.paid_at}")
            print(f"  Meta Purchase Sent: {p.meta_purchase_sent}")
            print(f"  Meta Purchase Sent At: {p.meta_purchase_sent_at}")
            print(f"  Meta Event ID: {p.meta_event_id}")
            
            # Verificar bot
            if p.bot:
                print(f"  Bot: {p.bot.name} (User ID: {p.bot.user_id})")
                
                # Verificar pool
                pool_bot = PoolBot.query.filter_by(bot_id=p.bot_id).first()
                if pool_bot:
                    pool = pool_bot.pool
                    print(f"  ✅ Pool encontrado: {pool.name} (ID: {pool.id})")
                    print(f"     Meta Tracking Enabled: {pool.meta_tracking_enabled}")
                    print(f"     Meta Pixel ID: {pool.meta_pixel_id or '❌ NÃO CONFIGURADO'}")
                    print(f"     Meta Access Token: {'✅ Configurado' if pool.meta_access_token else '❌ NÃO CONFIGURADO'}")
                    print(f"     Meta Events Purchase: {pool.meta_events_purchase}")
                else:
                    print(f"  ❌ PROBLEMA: Bot {p.bot_id} NÃO está associado a nenhum pool!")
                    print(f"     Isso impede o envio do Meta Pixel Purchase")
            else:
                print(f"  ❌ PROBLEMA: Bot {p.bot_id} não encontrado no banco!")
    
    print("\n" + "=" * 80)
    print("📋 RESUMO DOS PROBLEMAS ENCONTRADOS:")
    print("=" * 80)
    
    problemas = {
        'sem_pool': 0,
        'tracking_desabilitado': 0,
        'sem_pixel_id': 0,
        'sem_access_token': 0,
        'purchase_desabilitado': 0,
        'meta_sent': 0,
        'meta_nao_sent': 0
    }
    
    for p in payments:
        if not p.meta_purchase_sent:
            problemas['meta_nao_sent'] += 1
            
            if p.bot:
                pool_bot = PoolBot.query.filter_by(bot_id=p.bot_id).first()
                if not pool_bot:
                    problemas['sem_pool'] += 1
                else:
                    pool = pool_bot.pool
                    if not pool.meta_tracking_enabled:
                        problemas['tracking_desabilitado'] += 1
                    if not pool.meta_pixel_id:
                        problemas['sem_pixel_id'] += 1
                    if not pool.meta_access_token:
                        problemas['sem_access_token'] += 1
                    if not pool.meta_events_purchase:
                        problemas['purchase_desabilitado'] += 1
        else:
            problemas['meta_sent'] += 1
    
    print(f"  Payments sem Meta Pixel enviado: {problemas['meta_nao_sent']}")
    print(f"  Payments com Meta Pixel enviado: {problemas['meta_sent']}")
    print(f"\n  Causas identificadas:")
    print(f"    - Bot sem pool associado: {problemas['sem_pool']}")
    print(f"    - Tracking desabilitado no pool: {problemas['tracking_desabilitado']}")
    print(f"    - Pixel ID não configurado: {problemas['sem_pixel_id']}")
    print(f"    - Access Token não configurado: {problemas['sem_access_token']}")
    print(f"    - Evento Purchase desabilitado: {problemas['purchase_desabilitado']}")
    
    print("\n" + "=" * 80)

